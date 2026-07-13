# Man1Lab v1.3 Execution Platform Roadmap

**Status:** Materialization foundation and reproduction orchestration implemented; full Planning graph coverage and E2E controlled fixture pending
**Last updated:** 2026-07-13

This document tracks the implementation sequence for Runtime-owned execution persistence. The broader product roadmap remains at [../ROADMAP.md](../ROADMAP.md).

| Order | Phase | Deliverable | Current status |
|-------|-------|-------------|----------------|
| 1 | ExecutionStore | Execution persistence port; Runtime-owned workspace file adapter; journal-first recovery before snapshot validation; idempotent full re-materialization; revision-tagged snapshots; enforced O_EXCL writer ownership | ✅ Implemented (audit remediated) |
| 2 | Runtime injection | `ExecutionStoreFactory` on `RuntimeContext`; application wiring; per-transition durable commits; cross-process resume; artifact verification | ✅ Implemented (audit remediated) |
| 3 | LocalExecutor | First real backend with durable attempts, logs, artifacts, and conservative restart handling | ✅ Implemented |
| 4 | Platform integration | `PlatformExecutionService`, Facade and Console execution/status/report delegation | ✅ Implemented |
| 5 | Planning-to-Execution Materialization | Typed executable specs, resolvers, template registry, readiness report and decomposition projection | 🚧 Foundation implemented; preparation-stage templates incomplete |
| 6 | One-command reproduction | Application orchestration for Analyze → Discover → Plan → Materialize → Execute → Report | 🚧 Orchestration implemented; unsupported graphs stop at the readiness gate |
| 7 | End-to-end reproduction | Controlled paper fixture with executable graph, forced interruption, safe resume, artifacts and report | ❌ Not implemented |

## v1.3 Completion Gate

v1.3 Execution Runtime Integration is complete only when:

- execution runs and every task attempt survive process restart;
- trace events are append-only and snapshot updates are crash-consistent;
- a persisted `RUNNING` attempt is reconciled before redispatch;
- successful tasks are reused only after required artifact validation;
- one real LocalExecutor workflow resumes with the same `run_id` and produces an `ExecutionReport`;
- Runtime owns the concrete store while Execution owns state semantics and the facade remains the public boundary;
- automated tests cover persistence round trips, partial writes, incompatible schemas, missing artifacts, writer conflicts, and crash/resume behavior.
- ordinary Planning output passes a deterministic Materialization readiness gate before an `ExecutionRun` is created;
- `reproduce <paper.pdf>` delegates to one application orchestration service and produces a final execution report for a controlled fixture.

Architecture: [architecture/EXECUTION_RUNTIME.md](architecture/EXECUTION_RUNTIME.md) and [architecture/EXECUTION_MATERIALIZATION.md](architecture/EXECUTION_MATERIALIZATION.md).
