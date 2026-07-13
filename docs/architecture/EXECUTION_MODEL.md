# Execution Model Architecture

**Target:** Man1Lab v1.3 foundation  
**Status:** Phase 1 canonical contracts under implementation and audit
**Engine architecture:** [EXECUTION_ENGINE.md](EXECUTION_ENGINE.md)

---

## 1. Model Goals

The execution model describes what Man1Lab attempted and what happened without embedding a local-process implementation. It must be:

- **Canonical:** all backends emit the same task, result, trace, and report semantics.
- **Immutable at rest:** state changes produce persisted replacements/events rather than in-place historical mutation.
- **Serializable and versioned:** artifacts can be loaded across sessions and migrated deliberately.
- **Artifact first:** outputs are referenced explicitly and can be inspected or validated.
- **Resume first:** task and attempt identity are stable enough to reconcile interrupted runs.
- **Backend neutral:** Docker IDs, process IDs, cluster job IDs, and robot handles remain optional backend details.

This specification describes conceptual fields and invariants. It is not Python code.

### Identity hierarchy

```text
ExecutionGraph.graph_id
        ↓ decomposes into
ExecutionRun.run_id
        ├── ExecutionTask.id (stable within the run)
        │       └── attempt_id (new for every dispatch/retry)
        ├── ExecutionTrace.trace_id
        └── ExecutionReport.report_id
```

A resume continues the same `run_id`. A deliberate rerun creates a new `run_id` and records the prior run as lineage. Task IDs remain stable across resume; attempt IDs do not.

---

## 2. ExecutionTask

`ExecutionTask` is the canonical, backend-neutral unit of scheduling. It is produced by Task Decomposition from a planning graph node and contains declared intent, not process implementation.

### Required fields

| Field | Meaning | Rules |
|---|---|---|
| `id` | Stable task identity within an execution run | Non-empty, unique, deterministic for the same graph/decomposition version |
| `name` | Short human-readable task label | Descriptive; not used as identity or dispatch policy |
| `type` | Canonical `ExecutionTaskType` | Determines handler capability and validation, not planning strategy |
| `description` | Human-readable intended action | Must preserve planning intent; not executable shell text |
| `dependencies` | IDs of prerequisite tasks | Known IDs only; no self-edge; whole task graph must be acyclic |
| `inputs` | Declared artifact/resource references consumed by the task | References, never embedded secrets; required inputs must resolve before `READY` |
| `outputs` | Declared artifact expectations produced by the task | Success requires required outputs to be registered and validated |
| `status` | Current canonical `ExecutionTaskStatus` | Written only by scheduler state transitions |
| `metadata` | Versioned extension/provenance map | Must include source graph/node provenance; must remain bounded and serializable |

### Input and output references

`inputs` and `outputs` should be structured references rather than arbitrary dictionaries or bare filesystem paths.

An input reference conceptually identifies:

- Artifact/resource ID.
- Expected role/type.
- Whether it is required.
- Optional integrity/version expectation.
- A Runtime-resolved location handle, not a credential.

An output declaration conceptually identifies:

- Stable logical name and artifact type.
- Required versus optional.
- Expected location scope (repository, runtime run, external).
- Optional validation rule such as presence or backend-provided digest.

Concrete locations belong in the artifact manifest after resolution. This prevents task models from hard-coding local paths and enables future remote backends.

### Metadata contract

The minimum provenance metadata should carry:

- `source_graph_id`.
- `source_node_id`.
- Decomposition rule/schema version.
- Planning stage/binding/asset references when applicable.
- Backend capability requirements.
- Optional idempotency/retry classification.

Metadata must not carry plaintext secrets, unbounded logs, mutable scheduler internals, or a second hidden dependency graph.

---

## 3. Task Status

The canonical statuses are:

| Status | Meaning | Terminal |
|---|---|---|
| `PENDING` | Task exists but prerequisites or scheduling evaluation are incomplete | No |
| `READY` | All dependencies succeeded and required inputs are available; task may be dispatched | No |
| `RUNNING` | A persisted attempt has been dispatched and has not reached a reconciled terminal state | No |
| `SUCCESS` | Executor succeeded and all required result/artifact records were durably validated | Yes |
| `FAILED` | An attempt reached a definitive failure and policy selected no further retry | Yes |
| `SKIPPED` | Task will not run because dependency/policy makes it inapplicable for this run | Yes |
| `CANCELLED` | Execution was cancelled before successful completion | Yes |

### Allowed transitions

```text
PENDING → READY
PENDING → FAILED     (pre-dispatch validation/input-resolution failure only)
PENDING → SKIPPED
PENDING → CANCELLED

READY → RUNNING
READY → FAILED       (readiness invalidated before dispatch only)
READY → SKIPPED
READY → CANCELLED

RUNNING → SUCCESS
RUNNING → FAILED
RUNNING → CANCELLED
```

Retry does not transition a terminal task directly back to `READY`. A retry policy records a new attempt under the same stable task identity and only exposes the canonical terminal task state after attempts are exhausted or one succeeds. The implementation model may keep an internal attempt state while the trace preserves every dispatch.

On resume, a task persisted as `RUNNING` is **indeterminate**, not automatically failed and not automatically dispatched again. The engine must ask the backend to reconcile the attempt through `ReconciliationPort` when possible. Reconciliation results: `STILL_RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `LOST`, `UNKNOWN`. If reconciliation is impossible or returns `STILL_RUNNING`, policy records interruption (`INTERRUPTED` / `RECONCILIATION_REQUIRED`) and determines whether a new attempt is safe.

### Dependency propagation

- A task becomes `READY` only when all required dependencies are `SUCCESS` and its required input artifacts resolve.
- A failed or cancelled prerequisite prevents readiness.
- A downstream task prevented by dependency failure becomes `SKIPPED`, with a structured reason linked to the blocking task.
- Independent branches may continue only if the explicit scheduler policy permits it.
- `SKIPPED` never means success and must remain visible in the run report.

---

## 4. Task Types

The initial taxonomy is intentionally domain-oriented:

| Type | Responsibility | Typical outputs | Must not imply |
|---|---|---|---|
| `Repository` | Prepare or validate the reproduction repository/workspace | Repository reference, revision identity, preparation manifest | Source-code generation or planning changes |
| `Environment` | Prepare an isolated runnable environment | Environment manifest, dependency lock/snapshot, preparation logs | Global host mutation |
| `Dataset` | Acquire, validate, or stage dataset inputs | Dataset artifact reference, integrity/license/provenance metadata | Choosing a different dataset |
| `Checkpoint` | Acquire, validate, or stage model weights | Checkpoint artifact reference and integrity metadata | Selecting a substitute model |
| `Configuration` | Materialize or validate reproduction configuration | Configuration artifact reference and schema metadata | Choosing hyperparameters or planning changes |
| `Training` | Execute the declared training workload | Checkpoints, training logs, metrics, telemetry references | Deciding hyperparameters or evaluation criteria |
| `Evaluation` | Execute the declared evaluation workload | Evaluation metrics, predictions, evaluation logs | Judging scientific validity or changing benchmarks |
| `Report` | Collect/normalize execution outputs into an execution-level summary | Result bundle, metric summary, artifact index | Platform reporting conclusions or plan mutation |

Canonical serialized values should be stable and language-neutral, preferably lowercase strings, even if display labels use title case.

### Planning graph mapping

The initial explicit mapping is:

| `ExecutionGraphStageType` | `ExecutionTaskType` |
|---|---|
| `clone_repository` | `Repository` |
| `prepare_environment` | `Environment` |
| `download_dataset` | `Dataset` |
| `download_checkpoints` | `Checkpoint` |
| `training` | `Training` |
| `evaluation` | `Evaluation` |
| `comparison` | `Report` |
| `generate_config` | `Configuration` |

**Decision (v1.3 Phase 1):** `generate_config` maps to canonical `Configuration`. Configuration tasks declare a required configuration artifact output; they do not silently reuse `Environment` or `Training` semantics.

Task types describe what kind of effect is requested. Backend handlers decide how that effect is carried out. They must not become a registry of planning decisions.

---

## 5. ExecutionResult

`ExecutionResult` is the immutable outcome of one canonical task after its attempt history reaches the state reported to the scheduler. It is not only a subprocess return value.

### Core fields

| Field | Meaning |
|---|---|
| `result_id` | Stable result artifact identity |
| `run_id` | Owning execution run |
| `task_id` | Task whose outcome is represented |
| `status` | Terminal canonical task status represented by this result |
| `attempts` | Ordered references/summaries for every attempt |
| `started_at` / `completed_at` | Lifecycle timestamps; nullable when never started |
| `duration` | Derived/recorded execution duration with explicit unit |
| `backend` | Backend kind and non-secret backend identity/version |
| `task_result` | Bounded backend-neutral outcome summary |
| `logs` | Structured log references and bounded excerpts/summaries |
| `artifacts` | IDs/references of registered inputs and produced outputs |
| `errors` | Ordered structured errors, empty on clean success |
| `metrics` | Typed metric observations or references to metric artifacts |
| `metadata` | Bounded schema-versioned extension data |

The five user-facing concerns—task result, logs, artifacts, errors, and metrics—are all first-class. None should be inferred later by scraping a combined stdout string.

### Task result

The task-result section records the backend-neutral completion evidence:

- Completion/termination reason.
- Optional exit code where meaningful.
- Optional backend job/operation reference.
- Bounded output summary.
- Cancellation/timeout/resource-limit indication.

An exit code is optional because remote, simulation, and robot backends may not use process exit semantics. Exit code zero alone is insufficient for `SUCCESS` when required outputs are missing.

### Logs

Logs should be represented by descriptors containing stream/category, location, size, timestamps, and optional bounded excerpt. Full training output should live in an artifact/log store, not inside the canonical JSON result. Every record is correlated by `run_id`, `task_id`, and `attempt_id`.

### Artifacts

Artifact records should contain:

- `artifact_id`, logical name, and type.
- Producer run/task/attempt.
- Location reference and ownership scope.
- Size and integrity/digest when available.
- Creation timestamp and availability state.
- Optional media/schema/version metadata.

The canonical result references artifact records; it does not duplicate large artifact contents.

### Errors

Errors are structured records rather than only text:

- Stable category/code.
- Human-readable message.
- Phase (validation, dispatch, execution, collection, artifact validation, cancellation, reconciliation).
- Retryability as an observation/advice, not an automatic action.
- Backend details with secret redaction.
- Optional causal task/attempt/artifact reference.

### Metrics

Metric observations should preserve name, value, unit, step/epoch/split where applicable, timestamp, and source artifact. The engine records metrics; it does not decide whether they reproduce the paper. That comparison belongs to Verification and higher-level Reporting.

### Legacy model distinction

The current `models.execution.ExecutionResult` contains `exit_code`, `stdout`, `stderr`, command, duration, and workspace path for one local command. It remains the **legacy local command result** used by `Runner`, `EnvironmentService`, `ExecutionService`, Verification, and the current facade `execute()` path.

The canonical task/run result is `models.execution_engine.TaskExecutionResult` with its own `schema_version`. Persisted execution-run JSON must not silently reuse the legacy `ExecutionResult` schema. Application and facade layers may adapt between legacy command results and canonical task results during migration; the execution engine core emits only canonical models.

---

## 6. ExecutionTrace

`ExecutionTrace` answers:

> What happened during execution?

This complements, but does not replace, `DecisionTrace`, which answers:

> Why did we choose this approach?

| Concern | `DecisionTrace` | `ExecutionTrace` |
|---|---|---|
| Subject | Engineering choices | Observed execution lifecycle |
| Source | Discovery/planning rules and rationale | Scheduler, executor, artifact tracker, Runtime events |
| Mutability model | Immutable ordered decision records | Append-oriented immutable lifecycle events |
| May change plan? | Records decisions already made | No |
| Typical consumer | Audit/explanation | Resume, diagnostics, report, verification |

### Trace fields

| Field | Meaning |
|---|---|
| `trace_id` | Trace identity |
| `run_id` | Owning execution run |
| `graph_id` / `strategy_id` | Planning provenance |
| `created_at` / `updated_at` | Trace envelope timestamps |
| `events` | Ordered lifecycle events |
| `schema_version` | Serialization contract version |

Every event should include:

- Unique `event_id`.
- Event type.
- `run_id`, and task/attempt identity when applicable.
- Timestamp and monotonically increasing run-local sequence number.
- Actor/source (`scheduler`, backend, artifact tracker, Runtime adapter, operator).
- Structured payload bounded by the event schema.
- Optional correlation/causation event IDs.

Wall-clock timestamps alone must not determine event order; a persisted sequence number is required.

### Required lifecycle events

#### `TaskCreated`

Recorded when decomposition creates and validates a task. Payload includes task identity/type, dependencies, declared inputs/outputs, and source graph/node IDs. It does not mean the task is ready.

#### `TaskStarted`

Recorded after attempt identity and `RUNNING` state are durably established and dispatch begins. Payload includes `attempt_id`, selected backend, and start timestamp. A backend operation reference may be attached later if dispatch is asynchronous.

#### `TaskCompleted`

Recorded only after successful backend outcome, durable result persistence, and validation/registration of required artifacts. Payload references the result and produced artifacts. It corresponds to `SUCCESS`.

#### `TaskFailed`

Recorded when an attempt or task reaches a definitive failure observation. Payload references structured errors, phase, attempt, partial artifacts, and whether policy permits another attempt. If a retry follows, history remains; the failed event is never removed.

### Recommended foundation events

The minimum trace becomes much more useful for resume and operations with these additional events:

- `TaskReady` — readiness criteria became satisfied.
- `TaskBlocked` — a required input or pre-dispatch validation rule failed before an attempt existed.
- `TaskSkipped` — dependency/policy prevented execution.
- `TaskCancelled` — cancellation reached the task.
- `ArtifactRegistered` / `ArtifactInvalidated` — artifact manifest changed.
- `RunStarted`, `RunPaused`/`RunInterrupted`, `RunResumed`, `RunCompleted`, `RunFailed`, `RunCancelled` — run envelope lifecycle.

These additions do not change the four required task lifecycle events; they remove ambiguity around readiness, cancellation, and resume.

### Trace invariants

- Events are append-only and never rewritten to conceal a prior failure.
- Each event is persisted before a later event that causally depends on it.
- `TaskCompleted` requires a corresponding started attempt unless a future explicitly modeled cached-result event exists.
- At most one unreconciled `RUNNING` attempt exists per task in the v1.3 sequential foundation.
- Secrets, raw credentials, and unbounded logs never enter event payloads.
- The trace records facts, not inferred planning rationale.

---

## 7. Execution Run and Execution Report

Although the requested core models center on tasks, results, and trace, resume and final reporting require explicit run-level envelopes.

### ExecutionRun

Conceptual fields:

- `run_id`, `graph_id`, and `strategy_id`.
- Workspace identity/reference.
- Selected backend and immutable configuration/policy snapshot with secrets removed.
- Created/started/completed timestamps.
- Run status (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`, `INTERRUPTED`, `RECONCILIATION_REQUIRED`).
- Task IDs and trace ID.
- Parent/prior run lineage for deliberate reruns.
- Schema/engine/decomposition versions.

The run is the durable resume unit. Session identity may be recorded for provenance but cannot own the run lifetime.

### ExecutionReport

Conceptual fields:

- `report_id`, `run_id`, `graph_id`, `strategy_id`.
- Overall terminal/latest status and timing.
- Backend and policy summary.
- Ordered task results/status counts.
- Artifact manifest reference and key outputs.
- Aggregated metric references.
- Structured failures/cancellations/skips.
- Resume/attempt lineage and trace reference.
- Human-readable summary plus schema version.

An incomplete/interrupted run may have a latest report, but only a terminal report is final. The report is descriptive and cannot overwrite task results or execution history.

---

## 8. Resume Semantics

Resume is a model invariant, not a scheduler convenience.

### Completed tasks

A prior `SUCCESS` task may be reused only when:

1. Its canonical result is readable and schema-compatible.
2. Every required output artifact is still available.
3. Required integrity checks pass under the current policy.
4. Its task definition and relevant inputs match the persisted task fingerprint/decomposition version.

If any check fails, the scheduler records invalidation and applies an explicit re-execution or failure policy.

### Partial recovery

- Persist task/attempt identity before backend dispatch.
- Persist artifact candidates without declaring task success until validation completes.
- Preserve partial artifacts on failure when safe and label them partial/unverified.
- Reconcile interrupted backend work before retrying.
- Never infer success solely from files found in a conventional directory.

### Resume

- Resume retains the same `run_id`, task IDs, prior events, and prior attempts.
- A `RunResumed` event records the new session/process context and cause.
- The scheduler recomputes readiness from durable canonical state and validated artifacts.
- Resume never changes the source `ExecutionGraph` or planning provenance.
- A changed graph, changed task meaning, or changed required input starts a new run or requires an explicit migration; it is not resume.

---

## 9. Validation and Versioning

### Structural validation

- Required identities and schema versions are present.
- Task IDs and event IDs are unique in scope.
- Dependencies refer to known tasks and form an acyclic graph.
- Status/event/result combinations satisfy lifecycle invariants.
- Result task/run identities match their owning records.
- Required artifacts and error records follow bounded canonical schemas.

### Semantic validation

- Every task maps to a source graph node and supported decomposition rule.
- Backend capabilities cover every task before side effects begin.
- `SUCCESS` has completion evidence and valid required artifacts.
- `FAILED` contains at least one structured failure cause.
- `SKIPPED`/`CANCELLED` contain a reason and causal reference where applicable.
- Trace event sequence is consistent with task/result state.

### Versioning

Each top-level canonical model has its own `schema_version`. Persisted runs also record engine and decomposition versions. Readers should reject unsupported future major versions and use explicit migration for supported older versions. Unknown enum values must not be coerced to a different known task/status type.

Canonical JSON is the machine-readable source of truth. Markdown summaries are projections and must not be parsed to resume execution.

---

## 10. Boundary Rules

- `ExecutionTask` states intent and dependencies; it does not contain executable code or secrets.
- `ExecutionResult` records observed outcomes; it does not decide scientific success.
- `ExecutionTrace` records lifecycle facts; it does not duplicate `DecisionTrace` rationale.
- Artifact records reference content; they do not embed large content in canonical state.
- Backend-specific data is optional, bounded, redacted metadata and never changes core status semantics.
- Runtime/session IDs are provenance only; durable execution is not session-owned.
- Planning models never import or contain execution lifecycle models.
- Verification consumes execution outcomes but does not mutate them.
- AI coding agents and autonomous debugging may propose a new plan/patch/run in future; they cannot rewrite an existing task's history.

---

## 11. Decisions Required Before Coding

1. ~~Resolve `generate_config` by adding `Configuration` to the taxonomy or explicitly mapping it to `Repository` preparation.~~ **Resolved:** `generate_config` → `Configuration` (v1.3 Phase 1).
2. ~~Choose whether canonical `ExecutionResult` replaces, renames, or coexists with the legacy command result, including public API migration.~~ **Resolved for Phase 1:** canonical `TaskExecutionResult` coexists with legacy `models.execution.ExecutionResult`; facade migration deferred.
3. ~~Ratify whether run-level `INTERRUPTED` is a canonical status or only a resume condition derived from unreconciled `RUNNING` work.~~ **Resolved for Phase 1 audit:** `INTERRUPTED` and `RECONCILIATION_REQUIRED` are explicit `ExecutionRunStatus` values for unreconciled work.
4. Define artifact reference and integrity minimums for local v1.3.
5. Define task fingerprint inputs and decomposition-version compatibility for resume.
6. Define bounded log/excerpt limits and retention ownership.
7. Define failure/retry policy representation without embedding scheduler policy in task intent.
8. Define how configuration and secret handles are referenced while ensuring serialized models contain no secret values.

These decisions should be recorded before model implementation to avoid creating persisted contracts that cannot support safe resume or additional backends.

---

## Related Documents

- [EXECUTION_ENGINE.md](EXECUTION_ENGINE.md) — component design and dependency boundaries
- [EXECUTION_PLANNING.md](EXECUTION_PLANNING.md) — source planning graph
- [RUNTIME.md](RUNTIME.md) — Runtime and session ownership
- [ARCHITECTURE.md](ARCHITECTURE.md) — platform-wide layer model
