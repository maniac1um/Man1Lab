# ExecutionPlanningWorkflow Audit — Phase 5.1

**Date:** 2026-07-08  
**Scope:** `execution_planning/workflow.py` skeleton coordinator  
**Verdict:** **Ready for Execution Planning Services**

---

## Files Added

| File | Purpose |
|------|---------|
| `services/execution_planning/protocols.py` | Service contracts (`StrategyService`, etc.) — protocols only |
| `services/execution_planning/__init__.py` | Package exports for service protocols |
| `tests/test_execution_planning_workflow.py` | Workflow skeleton tests (9 tests) |
| `docs/reviews/execution_planning_workflow_phase_5_1/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `execution_planning/workflow.py` | Refactored to service-injected skeleton coordinator |

## Files Unchanged (intentional)

| File | Notes |
|------|-------|
| `execution_planning/builder.py` | Not modified per phase scope |
| `execution_planning/stages.py` | Legacy stage logic retained for future service migration; no longer imported by workflow |
| `models/execution_strategy.py` | Canonical artifact unchanged |
| `models/execution_planning_runtime.py` | Runtime contracts unchanged |

---

## Architecture

`ExecutionPlanningWorkflow` is the permanent coordinator for Execution Planning. It mirrors `DiscoveryWorkflow`:

```text
ExecutionPlanningWorkflow
        ↓
StrategyService.plan()
        ↓
ResourceBindingService.plan()
        ↓
ReusePlanningService.plan()
        ↓
AdaptationPlanningService.plan()
        ↓
GenerationPlanningService.plan()
        ↓
RiskAssessmentService.plan()
        ↓
ExecutionStrategyBuilder.build()
        ↓
ExecutionStrategy
```

| Principle | Status |
|-----------|--------|
| Workflow is orchestration-only | ✅ |
| Services own stage reasoning (future) | ✅ protocols defined, not implemented |
| Builder is sole assembly point | ✅ workflow never constructs `ExecutionStrategy` directly |
| Runtime results stay internal | ✅ `run()` returns `ExecutionStrategy` only |
| Inputs are read-only | ✅ analysis and discovery not mutated |

---

## Pipeline

Fixed stage ordering (permanent):

| Order | Stage | Service call |
|-------|-------|--------------|
| 1 | Strategy Decision | `strategy_service.plan(analysis, discovery)` |
| 2 | Resource Binding | `resource_binding_service.plan(analysis, discovery, strategy_result)` |
| 3 | Reuse Planning | `reuse_planning_service.plan(binding_result)` |
| 4 | Adaptation Planning | `adaptation_planning_service.plan(discovery, reuse_result)` |
| 5 | Generation Planning | `generation_planning_service.plan(analysis, adaptation_result)` |
| 6 | Risk Assessment | `risk_assessment_service.plan(discovery, generation_result)` |
| 7 | Assembly | `builder.build(risk_result, ...)` |

---

## Constructor

Mirrors `DiscoveryWorkflow` dependency injection:

```python
ExecutionPlanningWorkflow(
    strategy_service,
    resource_binding_service,
    reuse_planning_service,
    adaptation_planning_service,
    generation_planning_service,
    risk_assessment_service,
    builder=ExecutionStrategyBuilder,
)
```

`default()` wires temporary `_Placeholder*Service` adapters that delegate to private `_run_*_stage()` functions with deterministic skeleton snapshots.

---

## Dependency Audit

### Allowed imports in `workflow.py`

| Module | Purpose |
|--------|---------|
| `execution_planning.builder` | `ExecutionStrategyBuilder` |
| `models.execution_planning_runtime` | Runtime stage result types |
| `models.execution_strategy` | Output artifact types |
| `models.paper_reproduction_analysis` | Input artifact |
| `models.research_resource_discovery` | Input artifact |
| `services.execution_planning.protocols` | Service contracts |

### Forbidden (verified absent)

| Category | Status |
|----------|--------|
| Providers | ✅ not imported |
| Agents | ✅ not imported |
| Planner / Coder / Runner | ✅ not imported |
| LLM | ✅ not imported |
| Hydra | ✅ not imported |
| MLflow / tracking | ✅ not imported |
| GitHub | ✅ not imported |
| Workflow orchestrator | ✅ not imported |

AST boundary test: `tests/test_execution_planning_workflow.py::ExecutionPlanningWorkflowBoundaryTest`

---

## Boundary Verification

| Requirement | Test |
|-------------|------|
| Workflow construction | `test_workflow_accepts_injected_dependencies` |
| Stage ordering | `test_stage_ordering` |
| Builder invocation | `test_builder_invocation` |
| Immutable analysis input | `test_analysis_and_discovery_remain_immutable` |
| Immutable discovery input | `test_analysis_and_discovery_remain_immutable` |
| Returns `ExecutionStrategy` | `test_returns_execution_strategy` |
| Runtime results never exposed | `test_runtime_results_never_exposed` |
| No provider imports | `test_workflow_imports_no_providers` |
| Deterministic skeleton | `test_default_skeleton_execution_is_deterministic_in_structure` |

**Full suite:** 428 tests passing (including platform integration).

---

## Skeleton Placeholder Behavior

Until services are implemented, `_run_*_stage()` functions return fixed deterministic snapshots:

- Strategy posture: `GREENFIELD`
- Bindings: empty
- Reuse: `NOT_APPLICABLE`
- Adaptation: not required
- Generation: not required
- Risk: `PARTIAL` status hint, confidence `0.5`

No engineering reasoning. No LLM. No discovery-derived decisions in workflow.

---

## Remaining Work

| Item | Phase |
|------|-------|
| `StrategyService` implementation | Services phase |
| `ResourceBindingService` implementation | Services phase |
| `ReusePlanningService` implementation | Services phase |
| `AdaptationPlanningService` implementation | Services phase |
| `GenerationPlanningService` implementation | Services phase |
| `RiskAssessmentService` implementation | Services phase |
| Migrate `execution_planning/stages.py` logic into services | Services phase |
| Embedded Execution Planning providers | Provider phase |
| Remove `_Placeholder*Service` adapters from workflow | After services land |

---

## Verdict

**Ready for Execution Planning Services**

`ExecutionPlanningWorkflow` is the permanent coordinator with fixed six-stage ordering, service injection, builder-only assembly, and orchestration-only skeleton placeholders. Service protocols are defined; business reasoning is deferred to the next phase.
