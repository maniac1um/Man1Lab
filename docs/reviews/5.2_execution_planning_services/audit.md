# Execution Planning Services Audit — Phase 5.2

**Date:** 2026-07-08  
**Scope:** Service / Port / Provider foundation for Execution Planning  
**Verdict:** **Ready for Embedded Execution Planning Providers**

---

## Files Added

| File | Purpose |
|------|---------|
| `ports/strategy_provider.py` | Strategy provider port |
| `ports/resource_binding_provider.py` | Resource binding provider port |
| `ports/reuse_provider.py` | Reuse provider port |
| `ports/adaptation_provider.py` | Adaptation provider port |
| `ports/generation_provider.py` | Generation provider port |
| `ports/risk_provider.py` | Risk provider port |
| `services/execution_planning/strategy_service.py` | Strategy service |
| `services/execution_planning/resource_binding_service.py` | Resource binding service |
| `services/execution_planning/reuse_service.py` | Reuse service |
| `services/execution_planning/adaptation_service.py` | Adaptation service |
| `services/execution_planning/generation_service.py` | Generation service |
| `services/execution_planning/risk_service.py` | Risk service |
| `services/execution_planning/*_merge.py` | Per-stage merge policies (6 files) |
| `providers/embedded/execution_planning_skeleton.py` | Shared deterministic skeleton helpers |
| `providers/embedded/strategy.py` … `risk.py` | Embedded skeleton providers (6) |
| `providers/noop/strategy.py` … `risk.py` | NoOp providers (6) |
| `tests/test_execution_planning_services.py` | Service layer tests (14 tests) |
| `docs/reviews/execution_planning_services_phase_5_2/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `execution_planning/workflow.py` | Removed placeholders; calls `service.execute()` only |
| `services/execution_planning/protocols.py` | Renamed services; `plan` → `execute` |
| `services/execution_planning/__init__.py` | Exports concrete services |
| `tests/test_execution_planning_workflow.py` | Updated for `execute()` convention |

---

## Architecture

Mirrors Discovery capability layering:

```text
ExecutionPlanningWorkflow
        ↓
Services.execute(...)
        ↓
Ports (Provider protocols)
        ↓
Providers (Embedded, NoOp)
        ↓
Runtime Models
        ↓
ExecutionStrategyBuilder.build(...)
        ↓
ExecutionStrategy
```

| Layer | Responsibility |
|-------|----------------|
| Workflow | Stage ordering, timestamps, builder envelope |
| Services | Provider orchestration, ordering, merge |
| Ports | Provider contracts (`execute`) |
| Providers | Deterministic skeleton or empty defaults |
| Builder | Canonical assembly (unchanged) |

---

## Naming Convention

All Execution Planning service and provider methods use **`execute(...)`** (permanent convention).

| Stage | Service | Provider port |
|-------|---------|---------------|
| Strategy Decision | `StrategyService` | `StrategyProvider` |
| Resource Binding | `ResourceBindingService` | `ResourceBindingProvider` |
| Reuse Planning | `ReuseService` | `ReuseProvider` |
| Adaptation Planning | `AdaptationService` | `AdaptationProvider` |
| Generation Planning | `GenerationService` | `GenerationProvider` |
| Risk Assessment | `RiskService` | `RiskProvider` |

---

## Provider Hierarchy

Default provider order (mirrors Discovery):

```text
Embedded*Provider  →  NoOp*Provider
```

| Provider type | Behavior |
|---------------|----------|
| Embedded | Deterministic skeleton runtime results (`deciding_factors=["embedded"]`) |
| NoOp | Empty/default runtime results |

No engineering reasoning in any provider. No paper interpretation. No discovery-derived decisions.

---

## Workflow Simplification

Removed from `execution_planning/workflow.py`:

- `_run_*_stage()` private methods
- `_Placeholder*Service` adapters
- All `plan(...)` calls

`ExecutionPlanningWorkflow.default()` now wires:

```python
StrategyService.default()
ResourceBindingService.default()
ReuseService.default()
AdaptationService.default()
GenerationService.default()
RiskService.default()
```

---

## Dependency Audit

| Rule | Status |
|------|--------|
| Workflow → Services only | ✅ |
| Workflow ↛ Providers | ✅ AST verified |
| Services → Ports + Providers | ✅ |
| Providers ↛ Workflow | ✅ |
| Builder independent | ✅ |
| No LLM / Planner / Coder / Runner | ✅ |
| No GitHub / Repository Understanding | ✅ |
| No Discovery mutation | ✅ |

---

## Boundary Verification

| Requirement | Test |
|-------------|------|
| `execute()` interface | `ExecutionPlanningServiceInterfaceTest` |
| Provider ordering | `ExecutionPlanningProviderOrderingTest` |
| Embedded skeleton | `ExecutionPlanningEmbeddedProviderTest` |
| NoOp empty defaults | `ExecutionPlanningNoOpProviderTest` |
| No workflow placeholders | `ExecutionPlanningWorkflowSimplificationTest` |
| Workflow imports services only | `ExecutionPlanningWorkflowBoundaryTest` |
| Runtime chain preserved | `ExecutionPlanningRuntimePreservationTest` |
| Deterministic execution | `ExecutionPlanningDeterminismTest` |

**Full suite:** 444 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded providers with real paper/discovery interpretation | Embedded Providers phase |
| Engineering reasoning in providers (not services/workflow) | Provider phase |
| Migrate `execution_planning/stages.py` legacy logic into providers | Provider phase |
| Remove `execution_planning/stages.py` dead code | After provider migration |
| Additional provider types (e.g. policy-driven) | Future |

---

## Verdict

**Ready for Embedded Execution Planning Providers**

The Service / Port / Provider architecture is complete. Workflow delegates exclusively through `service.execute(...)`. Embedded and NoOp providers return deterministic skeletons. Business reasoning is deferred to the next provider implementation phase.
