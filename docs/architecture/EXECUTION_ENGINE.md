# Execution Engine Architecture

**Target:** Man1Lab v1.3 foundation  
**Status:** Phase 1 foundation under implementation and audit
**Audience:** Architects and Execution Engine implementers  
**Canonical model specification:** [EXECUTION_MODEL.md](EXECUTION_MODEL.md)

---

## 1. Motivation

Man1Lab can currently analyze a paper, discover resources, commit an engineering strategy, and produce an `ExecutionGraph`. Those artifacts describe a reproducible course of action, but they do not make that course of action happen.

Planning answers:

> What should happen?

Execution answers:

> How does it actually happen in a specific workspace, with a specific backend, while recording every observable outcome?

The distinction is architectural, not merely procedural. Planning may decide that a repository must be prepared before a dataset and that evaluation follows training. It must not clone the repository, install packages, download data, start a process, retry a failed task, or claim that an output exists. Those are execution concerns.

The existing `ExecutionGraph` is therefore an immutable planning handoff. It contains stage intent, dependencies, resource bindings, asset references, and rationale. It deliberately does not contain backend commands, mutable task state, attempts, process handles, logs, or produced artifacts. The Execution Engine translates that handoff into executable tasks and observes their lifecycle without changing the planning decision.

The v1.3 foundation must establish four properties before adding broad automation:

- **Separation:** Planning and Discovery remain read-only upstream capabilities.
- **Artifact first:** Every completed stage has inspectable, addressable evidence.
- **Resume first:** Durable state, not in-memory scheduler state, determines what can resume.
- **Backend independence:** Scheduling and reporting do not assume local Python processes.

### Existing architecture assessment

The Execution Engine can reuse these existing abstractions:

| Existing abstraction | Reuse | Constraint |
|---|---|---|
| `ExecutionGraph` / `ExecutionGraphNode` | Canonical planning input and dependency topology | Read-only; it is not a runtime task graph and its nodes must not acquire mutable status |
| `ExecutionGraphStageType` | Source vocabulary for initial decomposition rules | Map explicitly to execution task types; do not couple executors to planning enums forever |
| `DecisionTrace` | Pattern for immutable, persisted, human-readable trace artifacts | Reuse the pattern, not the model; execution events have different semantics |
| `WorkspaceArtifactStore` | Existing precedent for canonical JSON plus Markdown persistence and cross-session hydration | Extend through a narrow injected persistence service; the engine must not import session internals |
| `RuntimeSession` / `SessionWorkspace` | Session lifetime and current-workspace context | Execution state must survive the session and must not exist only in session fields |
| `RuntimeResourceManager` / `RuntimeInfrastructure` | Runtime-owned configuration, logging/resource access, and application composition pattern | Inject only the services the engine needs; the engine must not resolve arbitrary resources itself |
| `WorkflowOrchestrator` / `PipelineStage` | Outer business-stage sequencing and history envelope | The workflow invokes one engine operation; it must not schedule individual execution tasks |
| `Runner` decomposition | Useful precedent: coordinator, environment preparation, invocation planning, process execution | Treat as legacy execution capability to adapt behind the new backend contract, not as the new engine |
| `ExecutionPlan` | Useful backend-level concept: exact command, working directory, environment | It is a local invocation detail, not the canonical task or graph model |
| Existing `ExecutionResult` | Captures one command's exit code, streams, duration, and workspace | It is a legacy command result and is too narrow for canonical task/run results |
| Frozen Pydantic domain models and schema versions | Project convention for canonical artifacts | New execution artifacts should follow the convention during implementation |

The most important non-reusable assumption is the current fixed `scripts/train.py` flow. It is a legacy local-run convention, not an Execution Engine boundary.

---

## 2. Architecture Position

```text
Analysis
   ↓
Discovery
   ↓
Execution Planning
   ↓  ExecutionGraph (immutable handoff)
Execution Engine
   ↓  ExecutionReport + ExecutionTrace + artifacts
Results / Verification / Reporting
```

The Execution Engine is a business capability below Planning and above result consumers. It is **not** part of Platform Runtime. Runtime owns the process, session, infrastructure resources, and workspace persistence services; the engine uses those services to perform a bounded execution run.

### Recommended location

The capability belongs in the existing top-level `execution/` package. That package should evolve from its current local `ExecutionPlanner` utility into the Execution Engine capability root. Creating a competing `execution_engine/` package would leave two ambiguous execution layers.

Conceptual future ownership:

```text
execution/                 Execution Engine capability (Phase 1 foundation)
  engine.py                public coordinator
  decomposition.py         ExecutionGraph → ExecutionTask set
  scheduling.py            readiness and state transitions
  validation.py            graph/task DAG validation
  trace.py                 append-only ExecutionTrace builder
  report.py                ExecutionReport assembly
  resume.py                resume foundation logic
  errors.py                domain errors
  ports/                   executor, artifact tracker, input resolver, reconciliation contracts
  backends/                fake/in-memory adapters (tests)
  artifacts/               in-memory artifact tracker (tests)
  execution_planner.py     legacy local command planner (Runner)

models/
  execution_engine.py      canonical execution models
  execution.py             legacy local command ExecutionResult

application/               composition and Runtime-to-engine adapters (future)
workflow/                  invokes the engine as one pipeline stage (future)
runtime/                   owns process/session/resources/persistence implementations
interfaces/                calls the Platform Facade only
```

Phase 1 implements pure engine foundation only. Runtime persistence adapters, local subprocess backend, workflow/facade integration, and CLI changes remain future phases.

### Ownership boundaries

| Layer | Owns | Must not own |
|---|---|---|
| Analysis | Paper-stated reproduction facts and gaps | Resource search, strategy, execution |
| Discovery | External candidates, evidence, verification, ranking, selection | Execution commands or task state |
| Execution Planning | Strategy, resource binding, planning rationale, `ExecutionGraph` | Runtime task status or side effects |
| Execution Engine | Decomposition, readiness, dispatch, task lifecycle, artifact registration, execution reporting | Planning decisions, Runtime lifecycle, LLM lifecycle |
| Platform Runtime | Process/session lifecycle, configuration, logging, resources, workspace/persistence services | Business scheduling or execution policy |
| Workflow | Ordering of platform capabilities and high-level history | Per-task scheduling or backend control |
| Application | Composition, dependency injection, facade boundary | Execution algorithms |
| Interfaces | User input/output through the facade | Direct engine, workflow, or Runtime access |

The engine may reject an invalid or unsupported graph. It may not repair it by adding a new scientific or engineering decision. A required change to intent must return to Planning and produce a new graph/version.

---

## 3. Component Design

```text
ExecutionGraph
      ↓
Task Decomposition
      ↓
Task Scheduler
      ↓
Executor (selected backend)
      ↓
Artifact Tracker
      ↓
Execution Report

ExecutionTrace and durable run state observe the entire flow.
```

### 3.1 ExecutionGraph

**Responsibility**

- Serve as the immutable, versioned planning handoff.
- Express intended stages, dependency edges, asset/binding references, and rationale.
- Provide provenance through `graph_id` and `strategy_id`.

**Input**

- `ExecutionStrategy` and discovery assets during Execution Planning.

**Output**

- A validated `ExecutionGraph` consumed read-only by Task Decomposition.

**Forbidden responsibilities**

- Mutable runtime status, attempts, timestamps, backend selection, commands, credentials, logs, metrics, or artifact paths.
- Scheduler policy, retry policy, or process control.
- Silent mutation after execution starts.

### 3.2 Task Decomposition

**Responsibility**

- Deterministically translate every supported graph node into one or more `ExecutionTask` records.
- Preserve dependency topology and source-node provenance.
- Resolve task type and declared input/output contracts without performing work.
- Fail validation when a graph node cannot be mapped safely.

**Input**

- Immutable `ExecutionGraph`.
- Read-only bound resource descriptors needed to interpret graph references.
- Backend capability description, only to validate support—not to perform dispatch.

**Output**

- A validated task set/DAG with stable IDs, explicit dependencies, declared artifacts, and initial `PENDING` state.
- `TaskCreated` events.

**Forbidden responsibilities**

- Executing commands, downloading resources, inspecting success artifacts, or mutating planning artifacts.
- Inventing missing repositories, datasets, checkpoints, evaluation criteria, or training policy.
- Choosing a different planning posture because a backend lacks a capability.

One planning node may decompose into multiple execution tasks, but the mapping must remain traceable through metadata such as `source_graph_id` and `source_node_id`. Conversely, merging unrelated graph nodes into an opaque task is forbidden because it destroys resume granularity and auditability.

### 3.3 Task Scheduler

**Responsibility**

- Validate the task DAG before any side effect: unique IDs, known dependencies, acyclic topology, and supported task types.
- Derive readiness from dependency terminal states and declared artifact availability.
- Persist state transitions before and after dispatch.
- Dispatch ready tasks according to configured concurrency and fail/continue policy.
- Support cancellation, retry as a new attempt, and resume from durable state.
- On resume, reconcile indeterminate `RUNNING` tasks through `ReconciliationPort` before any new dispatch; `STILL_RUNNING` blocks the run (`INTERRUPTED`), `UNKNOWN`/`LOST` do not auto-dispatch.
- Evaluate readiness from dependency terminal states **and** resolved required inputs via `InputResolverPort`.
- Route all task status changes through the unified transition helper.

**Input**

- Validated `ExecutionTask` set.
- Durable prior run state and artifact manifest when resuming.
- Cancellation signal, scheduler policy, and backend capability information supplied by Runtime/application wiring.

**Output**

- Ordered dispatch requests to an Executor.
- Persisted task state transitions and execution events.
- Terminal run status for report assembly.

**Forbidden responsibilities**

- Running subprocesses or backend APIs directly.
- Editing task meaning, dependency edges, planning rationale, or declared outputs.
- Treating in-memory completion as durable completion.
- Marking a task `SUCCESS` until its result and required artifacts are durably recorded.

The scheduler is the sole writer of canonical task status. Executors report outcomes; they do not mutate task objects. For v1.3 the default policy should be deterministic, sequential scheduling. Concurrency is an extension of the scheduler policy, not a change to task semantics.

### 3.4 Executor

**Responsibility**

- Execute exactly one dispatched task attempt through a selected backend.
- Translate the canonical task contract into backend-specific operations.
- Stream or capture logs, observe exit/termination state, and return produced artifact candidates and metrics.
- Declare backend capabilities before dispatch.

**Input**

- Immutable task snapshot plus attempt identity.
- Resolved input artifact references.
- Runtime-provided workspace, configuration, logging, resource lease, secrets handle, and cancellation signal.

**Output**

- Backend-neutral task outcome containing status evidence, logs, artifact candidates, errors, metrics, and timing.

**Forbidden responsibilities**

- Choosing the next task or changing dependency state.
- Mutating `ExecutionGraph`, `ExecutionStrategy`, `DecisionTrace`, or task declarations.
- Creating `PlatformRuntime`, `RuntimeSession`, or arbitrary global infrastructure.
- Calling an LLM or Discovery service to improvise a fix.
- Reporting success merely because a command was launched.

The executor is a port. Local process execution, Docker, remote GPU, cluster, simulation, and robot control are adapters behind that port.

### 3.5 Artifact Tracker

**Responsibility**

- Register immutable metadata for declared inputs and observed outputs.
- Give every artifact a stable ID, producer run/attempt, type, location reference, integrity metadata, and creation time.
- Distinguish **registered** (`PENDING`) from **validated** (`VALID`) artifact state.
- Verify required output existence scoped by `run_id`, `task_id`, `attempt_id`, logical name, type, scope, and supported validation rules before scheduler success is committed.
- Unsupported validation rules fail closed (not pass).
- Expose manifests for resume, report generation, and later verification.

**Input**

- Task input/output declarations.
- Executor-produced artifact candidates.
- Runtime-provided workspace/artifact persistence service.

**Output**

- Durable artifact manifest and artifact references attached to task results.
- Artifact validation failures when declared outputs are absent or invalid.

**Forbidden responsibilities**

- Producing scientific outputs itself.
- Deciding that an undeclared substitute artifact satisfies planning intent.
- Owning repository source artifacts that belong to `WorkspaceManager`.
- Embedding credentials or unbounded log payloads in canonical metadata.

Artifact first means task success is evidenced by an inspectable result and manifest, not only an exit code. Repository artifacts remain owned by `WorkspaceManager`; runtime artifacts remain owned by execution services as established by ADR-0006. The tracker records them without taking over their production.

### 3.6 Execution Report

**Responsibility**

- Assemble the immutable run-level outcome after the scheduler reaches a terminal state.
- Summarize graph/run identity, backend, task results, artifacts, metrics, errors, timing, resume lineage, and trace location.
- Provide a stable input to Verification and platform Reporting.

**Input**

- Final durable task states, `ExecutionResult` records, artifact manifest, and `ExecutionTrace`.

**Output**

- Canonical `ExecutionReport` in machine-readable form and a human-readable summary.

**Forbidden responsibilities**

- Changing statuses, retrying work, suppressing failures, modifying artifacts, or making planning decisions.
- Claiming scientific reproducibility; Verification owns objective checks and broader reporting communicates conclusions.

---

## 4. Relationship With Runtime

Execution Engine **consumes** Runtime services. Runtime remains the owner of process-level infrastructure and session lifetime.

Required Runtime-facing capabilities are supplied by application composition as narrow contracts:

| Runtime service | Engine use |
|---|---|
| Workspace | Resolve the authorized run root and artifact locations |
| Session | Associate an interactive invocation with a durable run without making the run session-bound |
| Configuration | Read execution/backend/scheduler policy snapshots |
| Logging | Emit structured operational logs correlated by run, task, and attempt |
| Resource management | Acquire/release bounded CPU, GPU, memory, process, or future remote leases |
| Persistence | Store run state, results, trace, manifests, and report atomically enough for resume |
| Cancellation/clock | Observe cancellation and produce consistent lifecycle timestamps |

Dependency injection must follow the existing Runtime model:

```text
PlatformRuntime owns services
        ↓
Application wiring adapts/injects narrow contracts
        ↓
Execution Engine consumes contracts
```

The engine must **not**:

- Create or start Runtime objects.
- Open, close, or replace Runtime sessions.
- Resolve arbitrary Runtime resources through global access.
- Manage LLM providers, prompts, models, or LLM lifecycle.
- Modify planning decisions or call Planning/Discovery to obtain different ones.
- Put canonical resume state only in `SessionWorkspace`.

Runtime must also not import the Execution Engine or contain scheduling logic. A Runtime persistence adapter may know canonical execution models, following the current `WorkspaceArtifactStore` precedent, but business orchestration remains outside Runtime core. Application wiring is the composition boundary that prevents circular dependencies.

### Persistence and resume contract

A durable execution run needs a separate namespace from planning artifacts. Conceptually:

```text
workspace/
  decision/                         planning-owned graph and trace
  execution/
    runs/<run-id>/
      run.json                      identity, policy snapshot, lineage
      tasks.json                    latest canonical task states
      trace.json                    append-oriented lifecycle history
      artifacts.json                artifact manifest
      report.json                   terminal or latest report
      summary.md                    human-readable outcome
      logs/                         log references or bounded logs
```

The exact storage implementation is deferred, but the ownership is not: Runtime supplies persistence; the engine defines execution-state semantics.

Resume uses the same `run_id`, preserves completed attempts, and records a new resume event/lineage marker. Before reusing a `SUCCESS` task, the engine must confirm its required artifact records still resolve and satisfy available integrity checks. A missing or invalid output makes the task non-reusable; it does not silently remain successful.

---

## 5. Future Execution Backends

All backends implement one semantic contract: advertise capabilities, accept one immutable task attempt, honor cancellation where possible, emit correlated logs, and return a backend-neutral outcome. Backend-specific configuration belongs in opaque task metadata or injected backend configuration, never in scheduler branching logic.

### Local execution

- Runs on the host in an authorized workspace.
- Natural first adapter for v1.3 and migration target for current `Runner`, `EnvironmentService`, `ExecutionPlanner`, and `ExecutionService` behavior.
- Must use argument-safe process invocation, bounded output capture, cancellation, and explicit working directories.

### Docker

- Maps task inputs/artifacts into a container and records image identity/digest.
- Container creation, volume mapping, network policy, and teardown stay inside the adapter.
- Scheduler sees capabilities and outcomes, not Docker commands.

### Remote GPU

- Acquires a remote resource lease, stages inputs, launches work, and retrieves outputs.
- Remote job IDs and transport metadata are backend details referenced by attempts.
- Disconnection must be distinguishable from task failure; reconciliation is required before retry.

### Cluster

- Adapts canonical tasks to a cluster job system and observes queued/running/terminal state.
- Queue state does not introduce new canonical task statuses; it remains backend detail under `READY`/`RUNNING` transitions.
- Scheduler policy remains separate from cluster scheduling policy.

### Simulation

- Executes deterministic or stochastic simulator workloads with environment/version/seed provenance.
- Simulation outputs are ordinary tracked artifacts and metrics.
- Simulator lifecycle and reset semantics remain inside the backend adapter.

### Robot environments

- Requires explicit capability, safety envelope, resource lease, emergency stop/cancellation, and operator policy.
- Physical-world side effects must never be inferred from a generic local task.
- A robot backend is opt-in and cannot be selected by fallback from another backend.

### Backend capability negotiation

Before a run begins, decomposition/scheduling validates that the selected backend supports all task types and required capabilities. Unsupported work fails before side effects. Automatic cross-backend migration during a run is forbidden in the foundation because it complicates artifact locality, identity, and resume semantics. A future explicit migration design may add it with preserved lineage.

---

## 6. Dependency Boundaries

### Allowed dependencies

Execution Engine core may depend on:

- Canonical, versioned models in `models/`, including read-only `ExecutionGraph` and execution models.
- Python standard-library abstractions needed for deterministic coordination.
- Engine-local pure validation/decomposition/scheduling policies.
- Narrow engine-owned ports for executor, artifact persistence, run-state persistence, logging, clock, cancellation, and resource leases.
- Values and service implementations injected by the application composition layer.

Backend adapters may additionally depend on the technology they adapt, but those dependencies must not leak into canonical models or core scheduling. v1.3 introduces no new dependency as part of this architecture proposal.

Application may depend on both Runtime and Execution Engine to compose them. Workflow may depend on the engine's public operation and canonical report. Interfaces continue to depend only on the Platform Facade.

### Forbidden dependencies

Execution Engine core must not import or call:

- `analysis/`, `discovery/`, or `execution_planning/` services/providers/builders.
- `workflow/`, `application/`, or `interfaces/`.
- Runtime internals, concrete sessions, resource manager globals, or facade singletons.
- Agents (`Reader`, `Planner`, `Coder`, `Reviewer`, AI coding agents) or LLM/provider/prompt modules.
- Concrete backend SDKs, subprocess APIs, Docker clients, cluster clients, simulator SDKs, or robot SDKs.
- Verification or platform Reporting logic.

Runtime core must not depend on execution scheduling or executors. Planning must not depend on execution models with mutable lifecycle state. Backends must not call upstream decision capabilities.

```text
interfaces → application → workflow → execution public API
               ↓                    → models
             runtime
               ↓ injects adapters/services
         execution ports ← execution core → models
               ↑
       concrete backend adapters
```

Arrows indicate allowed knowledge/use. There is no arrow from execution core back to application, workflow, planning, discovery, or Runtime internals.

---

## 7. Minimal v1.3 Foundation

The minimum useful foundation is intentionally smaller than a complete reproduction system:

1. Validate and load one immutable `ExecutionGraph` plus a durable run identity.
2. Deterministically decompose supported graph stages into canonical tasks.
3. Persist task creation and state before any task runs.
4. Schedule tasks sequentially using dependency readiness.
5. Dispatch through one executor port; a local adapter is the first implementation target.
6. Persist lifecycle events, bounded log references, results, and artifact manifests.
7. Stop safely on failure or cancellation and emit an incomplete/failed report.
8. Resume the same run by revalidating successful task artifacts and continuing eligible work.

Out of scope for the foundation: distributed scheduling, dynamic DAG mutation, automatic debugging, AI-authored fixes, speculative execution, cross-backend migration, experiment sweeps, and robot control.

---

## 8. Architectural Risks and Controls

| Risk | Why it exists now | Required control |
|---|---|---|
| Graph/task semantic collapse | `ExecutionGraph` is already called execution-oriented | Keep graph immutable; introduce explicit decomposition and provenance mapping |
| Missing graph handoff | Current facade planning returns `ExecutionStrategy`, while graph construction/persistence is mainly a console/session side path | Make the graph an explicit, validated engine input and define how facade/workflow load or receive it before integration |
| Legacy/new result collision | `models.execution.ExecutionResult` represents one command only | Version and migrate deliberately; do not silently redefine persisted JSON or public return types |
| Duplicate execution coordinators | `Runner` already coordinates a fixed local flow | Adapt/migrate it behind the new executor boundary; define one public engine coordinator |
| Planning mutation during failure recovery | Missing resources may tempt execution-time improvisation | Fail with structured evidence and require a new planning artifact for changed intent |
| Persistence/runtime coupling | `WorkspaceArtifactStore` imports canonical models directly | Inject a narrow store contract and keep composition in application; avoid engine imports of session internals |
| False resume | A `SUCCESS` flag can outlive deleted/corrupt outputs | Revalidate required artifact references/integrity before skipping |
| Non-atomic state | Crash between side effect and state write creates ambiguity | Persist attempt identity before dispatch; reconcile `RUNNING` attempts on resume; write result/artifact state transactionally where possible |
| Unsafe local execution | Reproduced repositories and dependencies are untrusted | Explicit user policy, authorized workspace boundary, command arguments, time/resource limits, secret isolation, and network policy |
| Unbounded logs/artifacts | Training can produce very large streams/checkpoints | Store references and bounded summaries; apply Runtime quotas and retention policy |
| Resource oversubscription | GPU/CPU/memory needs are not modeled fully today | Runtime-owned leases and capability validation; sequential default in v1.3 |
| Ambiguous task idempotency | Downloads/install/training have different retry behavior | Stable task IDs, attempt IDs, declared outputs, and per-type retry/reconciliation policy |
| Backend leakage | Local command concepts can contaminate canonical models | Keep commands/process handles in backend request/outcome details, not `ExecutionTask` semantics |
| Artifact ownership conflict | Repository and runtime artifacts share a workspace | Preserve ADR-0006 ownership; tracker registers artifacts but does not become their writer |
| Current public API mismatch | Existing `execute()` runs Planner → Coder → Runner and CLI expects a nonexistent result `status` property | Treat current API as legacy during migration and define compatibility explicitly before replacement |

---

## 9. Implementation Roadmap

This roadmap describes future implementation order; it does not authorize code changes in this architecture milestone.

### Phase 1 — Canonical contracts

- Ratify the model semantics in [EXECUTION_MODEL.md](EXECUTION_MODEL.md).
- Decide schema identifiers, version migration, serialization bounds, and legacy `ExecutionResult` naming/compatibility.
- Define executor, state store, artifact store, clock, cancellation, and resource lease ports.

### Phase 2 — Pure engine foundation

- Add graph validation and deterministic decomposition.
- Add sequential scheduler state transitions and failure propagation.
- Add trace construction and report assembly with no real side effects.
- Test DAG validation, transition invariants, and resume decisions using in-memory test adapters.

### Phase 3 — Runtime persistence integration

- Add an execution run namespace through a Runtime-owned persistence adapter.
- Persist attempts/events/results/artifacts and hydrate runs across sessions.
- Define crash reconciliation for tasks left `RUNNING`.

### Phase 4 — Local backend

- Adapt the useful behavior of current environment and execution services behind the executor port.
- Add explicit repository, environment, dataset/checkpoint, training, evaluation, and report handlers only as supported.
- Add cancellation, time/resource bounds, safe argument handling, and artifact collection.

### Phase 5 — Platform integration

- Make Workflow invoke the Execution Engine as one stage.
- Wire dependencies in Application and expose stable facade outcomes.
- Update CLI/SDK/console only through the facade and define compatibility with the current `execute()` path.

### Phase 6 — Verification and extension

- Feed `ExecutionReport`, task results, metrics, and artifacts into Verification and Reporting.
- Add backend contract tests before Docker/remote/cluster/simulation adapters.
- Design automatic debugging, experiment management, and AI coding-agent loops as separate consumers/coordinators, not scheduler responsibilities.

---

## 10. Unresolved Questions

The following require explicit decisions before implementation crosses the named boundary:

1. Is v1.3 execution limited to workspaces already produced by the Implementation/Coder layer, or may repository preparation materialize a workspace directly from a planning binding?
2. Which component owns the durable execution store API: an extension of `WorkspaceArtifactStore` or a dedicated Runtime execution store?
3. How will legacy `models.execution.ExecutionResult`, `ExecuteResult`, `Runner`, and the current public `execute()` contract be versioned or deprecated?
4. What is the minimum artifact integrity policy for resume: existence/size, timestamps, hashes, or backend-provided identities?
5. Which task types are guaranteed in the first local backend, and which must be rejected before dispatch?
6. What default failure policy applies to independent branches: fail-fast, finish-ready-independent, or configurable?
7. What trust policy governs network access, dependency installation, repository scripts, secrets, and user confirmation for local execution?
8. Are metrics merely recorded by the engine, or is metric schema normalization owned by a future experiment-management capability?
9. How are abandoned remote jobs reconciled after process loss without accidentally launching duplicates?
10. Should execution runs be nested under the existing session workspace root or under a separate experiment/workspace identity when multi-run support arrives?

Until resolved, v1.3 should choose conservative defaults: existing workspace only, sequential local execution, fail-fast scheduling, no dynamic graph mutation, explicit unsupported-task failure, and durable per-run state.

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — platform layers and ownership
- [RUNTIME.md](RUNTIME.md) — Platform Runtime lifecycle and dependency rules
- [EXECUTION_PLANNING.md](EXECUTION_PLANNING.md) — planning capability and `ExecutionGraph`
- [EXECUTION_MODEL.md](EXECUTION_MODEL.md) — canonical execution model specification
- [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) — repository/runtime artifact ownership
- [ADR-0007](../adr/ADR-0007-Execution-Capability.md) — current legacy Runner decomposition
