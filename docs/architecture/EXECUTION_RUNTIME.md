# Execution Runtime Architecture

**Status:** Phase 1 + Phase 2 implemented; Phase 1–2 audit remediation complete (2026-07-13)
**Target:** Man1Lab v1.3 Execution Runtime Integration
**Audience:** Architects and implementers

This document defines the Runtime-owned persistence boundary for the Execution Engine. It complements [EXECUTION_ENGINE.md](EXECUTION_ENGINE.md), [EXECUTION_MODEL.md](EXECUTION_MODEL.md), and [RUNTIME.md](RUNTIME.md).

---

## 1. Purpose

The Execution Engine already models runs, tasks, attempts, state transitions, traces, artifacts, reports, scheduling, and in-memory resume. Cross-process recovery additionally requires durable state with explicit crash-consistency rules.

`WorkspaceArtifactStore` is insufficient for this purpose. It stores low-frequency, canonical snapshots produced by Analysis, Discovery, and Planning. Those artifacts explain what was understood and decided. Execution persistence records a live state machine: repeated task transitions, attempts, backend identities, append-only events, artifact validity, and recovery decisions.

| Store | Primary concern | Update pattern | Recovery role |
|-------|-----------------|----------------|---------------|
| `WorkspaceArtifactStore` | Analysis, discovery, planning, and decision snapshots | Stage-level replacement | Rehydrate upstream inputs |
| `ExecutionStore` | Execution run state and history | Frequent transitions plus append-only events | Reconstruct and safely resume a run |

The two stores may share low-level filesystem utilities in the future, but they must not become one business API.

---

## 2. Architecture

```text
PlatformRuntime                         ← process lifecycle owner
└── RuntimeContext                      ← infrastructure ownership container
    ├── RuntimeResourceManager          ← configuration, prompts, LLM resources
    ├── WorkspaceArtifactStore          ← upstream canonical snapshots
    ├── ExecutionStore                  ← durable execution state
    └── ResourceManager                 ← execution resource/capacity service

Application composition                ← selects workspace and injects ports
        │
        ▼
ExecutionEngine                         ← execution semantics and scheduling
        │ uses narrow persistence port
        ▼
ExecutionStore
```

Ownership is deliberately split:

- The Execution Engine owns execution semantics: legal transitions, scheduling, attempt meaning, artifact requirements, reporting, and resume policy.
- Runtime owns durable infrastructure: store lifetime, workspace-relative location, file access, locking, atomic replacement, and resource availability.
- Application composition obtains the Runtime-provided store and injects it through an Execution-owned port. The Engine never imports Runtime internals.
- `RuntimeSession` may retain a selected `run_id` as a convenience reference, but it does not own the run. A run outlives both a session and a process.
- `RuntimeResourceManager` may expose an `ExecutionStore` service or factory. Individual `ExecutionRun` objects are persisted data, not Runtime resources.

The concrete persistence adapter may understand canonical execution models, but Runtime lifecycle core must not import the scheduler, engine, workflows, or planning services.

---

## 3. ExecutionStore Responsibilities

`ExecutionStore` persists and retrieves:

| Record | Purpose |
|--------|---------|
| `ExecutionRun` | Run identity, graph provenance, status, revisions, timestamps, compatibility metadata |
| `ExecutionTask` | Task definitions and latest durable states |
| `TaskAttempt` | Attempt identity, backend operation reference, timing, outcome, result, and error history |
| `ExecutionTrace` | Ordered lifecycle and recovery events |
| `ArtifactManifest` | Artifact identity, producer, location, integrity metadata, and availability state |
| `ExecutionReport` | Latest/final aggregate view of the run |

It also owns persistence-level operations for creating a run, committing a state transition, appending trace events, recording artifacts, loading a consistent snapshot, and enumerating resumable runs. These operations must expose domain intent, not filesystem paths, to the Engine.

`ExecutionStore` does **not** store or own:

- application configuration or secrets;
- LLM providers, clients, prompts, or lifecycle;
- workspace creation, selection, cleanup, or root-path policy;
- Runtime or session lifecycle;
- planning decisions as duplicated mutable objects.

Execution records retain only immutable provenance references and fingerprints such as `execution_graph_id`, strategy identifier, schema version, and relevant redacted policy snapshot. Large artifact bytes remain in backend/workspace artifact locations; the store records their manifest and integrity evidence.

---

## 4. Persistence Model

The initial implementation is a workspace-scoped file store:

```text
workspace/
└── execution/
    └── runs/
        └── <run_id>/
            ├── run.json
            ├── tasks.json
            ├── trace.jsonl
            ├── artifacts.json
            └── report.json
```

| File | Content |
|------|---------|
| `run.json` | Run envelope, status, provenance, schema/engine versions, revision |
| `tasks.json` | Task snapshots plus task-result and attempt history |
| `trace.jsonl` | Append-only ordered execution and recovery events |
| `artifacts.json` | Artifact manifests, checksums/fingerprints, producer attempt, availability |
| `report.json` | Latest materialized execution report; absent until first report is produced |

### Append-only trace

Each trace record has a run-local monotonic sequence, event identifier, timestamp, task/attempt correlation, event type, and redacted payload. Existing events are never edited. A partial final JSONL record caused by a crash is ignored or quarantined during recovery; earlier complete records remain authoritative.

### Atomic state updates

Snapshot files are written to a sibling temporary file, flushed, and atomically replaced on the same filesystem. Every mutation increments a run revision. The store exposes a single logical transition commit so the Engine does not separately coordinate task state and trace writes.

The file adapter uses an explicit durable transition journal (`journal/<transition_id>.journal.json`) plus materialized snapshots. Each commit records transition ID, base/target revision, trace events, and intended run/tasks/artifacts/report payloads before snapshot files are updated. Recovery replays incomplete journals idempotently through states: journal durable → snapshots partial → snapshots complete → committed.

Snapshot files (`tasks.json`, `artifacts.json`, `report.json`) carry `run_id`, `revision`, and `schema_version` metadata; load rejects mixed revisions.

Only one writer may mutate a run at a time. The initial store uses a run-scoped lock or lease and rejects a second writer; distributed concurrent scheduling is outside the first implementation.

### Crash recovery

Recovery loads the last valid snapshots, validates revision and trace ordering, and reconstructs any incomplete journaled transition. Corrupt or incompatible data is never silently overwritten. The store returns a typed recovery condition so the application can require repair, migration, or operator action.

---

## 5. Resume Architecture

```text
load run
   ↓
validate schema and compatibility
   ↓
verify trace and snapshot consistency
   ↓
verify required artifacts
   ↓
reconcile interrupted tasks/attempts
   ↓
recompute READY/PENDING tasks
   ↓
continue scheduler with the same run_id
```

### State handling

| Persisted state | Resume action |
|-----------------|---------------|
| `PENDING` | Re-evaluate dependencies; remain pending or become ready |
| `READY` | Eligible for dispatch after validation |
| `RUNNING` | Must reconcile the recorded backend attempt before any redispatch |
| `SUCCESS` | Reuse only when required output artifacts still validate |
| `FAILED` | Preserve attempt history; retry only under explicit retry/resume policy |
| `SKIPPED` | Preserve reason; reconsider only if policy explicitly permits |
| `CANCELLED` | Remains terminal unless an explicit new attempt policy reopens it |

Reconciliation asks the injected backend adapter about the persisted operation reference. A task may be confirmed still running, completed, failed, cancelled, or lost/unknown. Still-running work is observed rather than duplicated. Lost or unknown work remains reconciliation-required until policy or an operator authorizes a retry.

If a successful task's required artifact is missing or fails integrity validation, success is invalidated through an explicit traceable recovery transition; it is never silently treated as reusable. Downstream tasks are then recalculated from dependency and artifact state.

Backend-specific operation references and reconciliation metadata are persisted without making the store backend-aware. This supports Local, Docker, remote GPU, cluster, simulation, and robot backends behind the same contracts.

---

## 6. Dependency Boundary

The Execution Engine may depend on:

- canonical execution models and state rules;
- Execution-owned ports for persistence, artifact access, execution, input resolution, and reconciliation;
- Runtime-provided implementations injected by application composition.

The Execution Engine must **not**:

- create or start `PlatformRuntime`;
- create, choose, or remove a workspace;
- manage `RuntimeSession` or assume session lifetime equals run lifetime;
- load application configuration or secrets;
- create or own LLM resources;
- derive or modify planning decisions;
- construct concrete filesystem, database, Docker, cluster, or cloud adapters.

Runtime must not schedule tasks, interpret execution states, choose retry policy, or depend on Execution Engine orchestration. Runtime supplies durable and resource infrastructure; the Engine remains the domain authority.

---

## 7. Implementation Roadmap

### Phase 1 — ExecutionStore

**Status:** ✅ Implemented

Define the persistence port and Runtime-owned file adapter; implement schema/version validation, atomic snapshots, append-only trace, run locking, artifact manifests, and crash-consistency tests.

| Deliverable | Status |
|-------------|--------|
| Execution-owned persistence port (`execution/ports/persistence.py`) | ✅ |
| In-memory store for unit tests | ✅ |
| Runtime file adapter (`runtime/execution_store/`) | ✅ |
| Run create/load, atomic snapshots, append-only trace | ✅ |
| Artifact manifest and report persistence | ✅ |
| Run-level single-writer protection | ✅ |
| Crash recovery (stale temps, partial JSONL tail, journal replay) | ✅ |
| Per-file revision metadata and mixed-revision rejection | ✅ |
| Durable transition journal with idempotent replay | ✅ |
| Recovery before mixed-revision validation | ✅ |
| Writer ownership enforced on every mutation | ✅ |
| Live long-running locks protected from age-only eviction | ✅ |
| Resumable-run discovery | ✅ |

### Phase 2 — Runtime injection

**Status:** ✅ Implemented

Expose a workspace-scoped store through Runtime/Application composition; persist every Engine transition; implement cross-process load, artifact verification, and interrupted-attempt reconciliation.

| Deliverable | Status |
|-------------|--------|
| Application wiring (`application/runtime/execution_wiring.py`) | ✅ |
| `RuntimeContext.execution_store_factory` + `execution_store()` | ✅ |
| Engine persistence injection and `load_and_resume_run` | ✅ |
| Durable transition commits via scheduler | ✅ |
| Cross-process load and resume (same `run_id`) | ✅ |
| Artifact verification before reuse | ✅ |
| Reconcile persisted `RUNNING` attempts | ✅ |
| Traceable recovery decisions in trace | ✅ |
| Runtime shutdown releases execution writer locks | ✅ |
| Typed artifact verification (integrity, producer, path safety) | ✅ |

### Phase 3 — LocalExecutor

Add the first real backend with durable operation/attempt identity, log and artifact publication, cancellation, and restart reconciliation.

### Phase 4 — Console integration

Expose create, inspect, resume, cancel, and report operations through the facade and console without giving interfaces direct store access.

### Phase 5 — End-to-end reproduction

Run one bounded repository-preparation-to-evaluation workflow, terminate/restart the process during execution, resume safely, and produce an inspectable report and artifacts.

Each phase must preserve compatibility with future stores and backends; a database or distributed scheduler is not required for v1.3.

---

## Architecture Decisions

1. Use a dedicated Runtime-owned `ExecutionStore`; do not expand `WorkspaceArtifactStore` into execution state storage.
2. Keep state semantics and ports in Execution while Runtime owns the concrete durable adapter.
3. Make the run, not the process or session, the durable recovery unit.
4. Combine atomic materialized snapshots with an append-only recovery trace rather than adopting full event sourcing.
5. Persist backend-neutral operation references so all future backends share resume semantics.

## Alternatives Rejected

- **Extend `WorkspaceArtifactStore`:** its snapshot cadence and ownership semantics do not satisfy attempt-level consistency or reconciliation.
- **Let Execution Engine write files directly:** couples domain behavior to workspace and storage policy.
- **Make `RuntimeSession` own runs:** prevents reliable resume beyond an interaction lifetime.
- **Persist only the final report:** loses the state required after interruption.
- **Adopt a database immediately:** adds operational complexity before single-workspace durability is validated.
- **Use trace-only event sourcing:** raises replay, migration, and debugging cost beyond v1.3 needs.

## Risks

- JSONL and multiple JSON snapshots cannot provide a native multi-file transaction; journaling, revisions, and idempotent replay are mandatory.
- Concurrent processes can duplicate work without strict per-run writer ownership.
- Backend reconciliation quality varies; unknown operations require conservative handling.
- Artifact paths can move or point outside the workspace; manifests need normalized references and integrity checks.
- Schema/model evolution can make old runs unreadable without explicit compatibility and migration policy.
- Serialized metadata or logs can leak secrets unless redaction is enforced before persistence.
