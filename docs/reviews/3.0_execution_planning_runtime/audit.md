# Runtime Stage Models Audit — Phase 3

**Date:** 2026-06-29  
**Scope:** `models/execution_planning_runtime.py` workflow-internal stage contracts  
**Verdict:** **Ready for ExecutionStrategyBuilder**

---

## Files Added

| File | Purpose |
|------|---------|
| `models/execution_planning_runtime.py` | Frozen Pydantic runtime stage result models |
| `tests/test_execution_planning_runtime.py` | Runtime model tests (11 tests) |
| `docs/reviews/execution_planning_runtime_phase_3/audit.md` | This audit |

---

## Runtime Contracts Implemented

### Shared infrastructure

| Type | Responsibility |
|------|----------------|
| `StageRuntimeStatus` | Per-stage outcome enum (`success`, `partial`, `degraded`, `skipped`) |
| `PlanningStageRuntimeBase` | Stage metadata, timing, diagnostics, warnings, errors |

### Stage output snapshots (intermediate only)

Each snapshot maps to a canonical `ExecutionStrategy` module without duplicating the root artifact:

| Snapshot | Canonical module |
|----------|------------------|
| `StrategyDecisionSnapshot` | `strategy` |
| `ResourceBindingSnapshot` | `resource_bindings` |
| `ReusePlanSnapshot` | `reuse_plan` |
| `AdaptationPlanSnapshot` | `adaptation_plan` |
| `GenerationPlanSnapshot` | `generation_plan` |
| `RiskAssessmentSnapshot` | `risk_assessment` |

### Cumulative stage results

Aligned with `docs/design/execution-planning-workflow.md` §4.3 pass-through semantics:

```text
ExecutionPlanningWorkflow
        ↓
StrategyDecisionResult
        ↓
ResourceBindingResult
        ↓
ReusePlanResult
        ↓
AdaptationPlanResult
        ↓
GenerationPlanResult
        ↓
RiskAssessmentResult
        ↓
ExecutionStrategyBuilder   (next phase)
        ↓
ExecutionStrategy          (canonical — leaves capability)
```

| Result | Stage | New outputs | Pass-through |
|--------|-------|-------------|--------------|
| `StrategyDecisionResult` | 1 — Strategy Decision | `strategy` | — |
| `ResourceBindingResult` | 2 — Resource Binding | `resource_bindings` | `strategy` |
| `ReusePlanResult` | 3 — Reuse Planning | `reuse_plan` | `strategy`, `resource_bindings` |
| `AdaptationPlanResult` | 4 — Adaptation Planning | `adaptation_plan` | prior stages |
| `GenerationPlanResult` | 5 — Generation Planning | `generation_plan` | prior stages |
| `RiskAssessmentResult` | 6 — Risk Assessment | `risk_assessment` | prior stages (unchanged by stage 6) |

---

## Relationship to Canonical Artifact

| Principle | Status |
|-----------|--------|
| Runtime models are not published downstream | Yes |
| No `ExecutionStrategy` root duplication | Yes |
| Snapshots reuse canonical nested types (`ResourceBinding`, `RiskRecord`, etc.) | Yes |
| `strategy` pass-through is required on cumulative results (workflow supplies prior stage state) | Yes |
| New-stage snapshots with all-default fields use `default_factory` | Yes |
| Only `ExecutionStrategy` leaves the capability after builder + validation | Yes (by design) |

---

## Stage Isolation

| Constraint | Status |
|------------|--------|
| No workflow implementation | Yes |
| No builder implementation | Yes |
| No planner implementation | Yes |
| No business or validation logic in runtime models | Yes |
| Frozen Pydantic (`ConfigDict(frozen=True)`) | Yes |
| `Field()` descriptions on all fields | Yes |
| `default_factory` for mutable collections | Yes |
| Timing metadata (`started_at`, `completed_at`) on base only | Yes |

---

## Architecture Compliance

| Constraint | Status |
|------------|--------|
| No imports from Planner | Yes |
| No imports from Workflow | Yes |
| No imports from Providers | Yes |
| No Hydra imports | Yes |
| No MLflow imports | Yes |
| No Discovery service imports | Yes |
| Depends only on `models.execution_strategy` canonical types | Yes |

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| `ExecutionStrategyBuilder` — assemble snapshots → canonical artifact | Next phase |
| `ExecutionPlanningWorkflow` — populate stage results | Workflow phase |
| Cross-artifact validation against linked `ResearchResourceDiscovery` | Builder / workflow |
| Package-level re-export from `models/__init__.py` | Optional cosmetic |
| Semantic coherence rules (ES-10–ES-23) at assembly time | Builder validation stage |

---

## Test Results

```text
pixi run test tests/test_execution_planning_runtime.py
262 passed in 9.57s
```

New tests (`tests/test_execution_planning_runtime.py`): **11**

Coverage includes:

- Stage runtime metadata defaults (`stage_name`, `stage_status`, warnings, errors, diagnostics, timing)
- Snapshot defaults for fully-defaultable modules
- Construction for each cumulative result type
- Cumulative pass-through chain through `RiskAssessmentResult`
- Frozen immutability
- JSON round-trip (`StrategyDecisionResult`, `RiskAssessmentResult`)
- Nested snapshot serialization

---

## Architecture Compliance Summary

| Principle | Compliant |
|-----------|-----------|
| Runtime-only contracts | **Yes** |
| Frozen Pydantic models | **Yes** |
| No canonical artifact duplication | **Yes** |
| Cumulative stage pass-through | **Yes** |
| Import boundary respected | **Yes** |
| No workflow behavior | **Yes** |

---

## Verdict

**Ready for ExecutionStrategyBuilder**

Runtime stage result models are complete and test-covered. The builder can consume `RiskAssessmentResult` (full cumulative state), map snapshots to canonical modules, and emit `ExecutionStrategy` through the existing validation layer.
