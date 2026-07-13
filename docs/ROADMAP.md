# Man1Lab v1.3 Execution Runtime Roadmap

**Status:** Phase 1–2 implemented with audit remediation; Phase 3+ pending
**Last updated:** 2026-07-13

This document tracks the implementation sequence for Runtime-owned execution persistence. The broader product roadmap remains at [../ROADMAP.md](../ROADMAP.md).

| Order | Phase | Deliverable | Current status |
|-------|-------|-------------|----------------|
| 1 | ExecutionStore | Execution persistence port; Runtime-owned workspace file adapter; journal-first recovery before snapshot validation; idempotent full re-materialization; revision-tagged snapshots; enforced O_EXCL writer ownership | ✅ Implemented (audit remediated) |
| 2 | Runtime injection | `ExecutionStoreFactory` on `RuntimeContext`; application wiring; per-transition durable commits; cross-process resume; artifact verification | ✅ Implemented (audit remediated) |
| 3 | LocalExecutor | First real backend with durable attempts, logs, artifacts, cancellation, and reconciliation | ❌ Not implemented |
| 4 | Console integration | Facade operations for create, inspect, resume, cancel, and report; console consumes facade only | ❌ Not implemented |
| 5 | End-to-end reproduction | Bounded reproduction with forced process interruption, safe resume, artifact inspection, and final report | ❌ Not implemented |

## v1.3 Completion Gate

v1.3 Execution Runtime Integration is complete only when:

- execution runs and every task attempt survive process restart;
- trace events are append-only and snapshot updates are crash-consistent;
- a persisted `RUNNING` attempt is reconciled before redispatch;
- successful tasks are reused only after required artifact validation;
- one real LocalExecutor workflow resumes with the same `run_id` and produces an `ExecutionReport`;
- Runtime owns the concrete store while Execution owns state semantics and the facade remains the public boundary;
- automated tests cover persistence round trips, partial writes, incompatible schemas, missing artifacts, writer conflicts, and crash/resume behavior.

Architecture: [architecture/EXECUTION_RUNTIME.md](architecture/EXECUTION_RUNTIME.md).
