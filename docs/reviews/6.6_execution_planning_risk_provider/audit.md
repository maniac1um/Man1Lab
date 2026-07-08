# Embedded Risk Provider Audit — Phase 6.6

**Date:** 2026-07-08  
**Scope:** Embedded Risk Provider — final engineering decision provider  
**Verdict:** **Execution Planning Embedded Providers Complete**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/embedded/decision_foundation/risk_decision.py` | Execution readiness + risk decision |
| `tests/test_execution_planning_risk_provider.py` | Risk provider and foundation tests (15 tests) |
| `docs/reviews/execution_planning_risk_provider_phase_6_6/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/risk.py` | Replaced skeleton with foundation-based provider |
| `providers/embedded/decision_foundation/__init__.py` | Export readiness and risk decision APIs |
| `ports/risk_provider.py` | Accept analysis, discovery, generation_result |
| `services/execution_planning/risk_service.py` | Pass analysis and discovery to providers |
| `services/execution_planning/protocols.py` | Updated `RiskService` protocol |
| `execution_planning/workflow.py` | Pass analysis and discovery to risk service |
| `providers/noop/risk.py` | Updated signature |
| `tests/test_execution_planning_workflow.py` | Updated risk service call assertion |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/builder.py` | Assembly unchanged |
| Canonical / runtime models | Unchanged |
| Strategy, binding, reuse, adaptation, generation providers | Behavior unchanged |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
RiskService.execute(analysis, discovery, generation_result)
        ↓
EmbeddedRiskProvider
        ↓
Decision Foundation
    ObservedFacts → DecisionDimensions → ExecutionReadiness → decide_risk(...)
        ↓
RiskAssessmentSnapshot
        ↓
ExecutionStrategyBuilder.build(...)
```

Risk evaluates the completed engineering plan. It never modifies or replaces planning decisions.

---

## Execution Readiness (internal)

Before risk generation, deterministic readiness dimensions are evaluated:

| Dimension | Levels |
|-----------|--------|
| Resource Ready | READY / PARTIAL / NOT_READY / UNKNOWN |
| Engineering Ready | READY / PARTIAL / NOT_READY / UNKNOWN |
| Dependency Ready | READY / PARTIAL / NOT_READY / UNKNOWN |
| Execution Ready | READY / PARTIAL / NOT_READY / UNKNOWN |

Readiness is internal to the decision foundation — not exposed as canonical models.

---

## Risk Policy

Risk evaluates only completed planning outputs:

| Condition | Typical outcome |
|-----------|-----------------|
| Greenfield posture | Engineering implementation risk (degraded) |
| Hybrid reuse | Integration risk (degraded) |
| Official repository AS_IS | Informational reduced-risk record |
| Archived repository | Sustainability risk (degraded) |
| Missing generation targets | Execution preparation risk (degraded) |
| Blocking discovery gaps | Blocking risks |
| Supporting-only reuse | Maintenance / verification risk (degraded) |

Every risk originates from existing planning outputs or observed facts — no invented assumptions.

---

## Fallback Strategy Policy

Deterministic fallbacks reference existing bindings only:

| Fallback | Trigger |
|----------|---------|
| Use supporting repository | Primary execution fails |
| Generate missing configuration | Generation plan committed |
| Reduce reproduction scope | Hybrid integration fails |
| Manual engineering required | Greenfield posture |

Never invents new repositories or re-queries Discovery.

---

## Decision Foundation Reuse

- `build_observed_facts()` — shared
- `evaluate_dimensions()` — shared
- New `evaluate_execution_readiness()` — internal readiness assessment
- New `decide_risk()` — risk-specific decision

No duplicated facts extraction or dimension evaluation.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No planning decision mutation | ✅ |
| No code/file generation | ✅ |
| No binding / reuse / adaptation / generation mutation | ✅ tested |
| No Builder / Workflow calls from provider | ✅ |
| No network / GitHub / LLM | ✅ |
| Workflow ordering unchanged | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `risk_decision.py` | `decision_foundation`, runtime snapshots, canonical risk types |
| `providers/embedded/risk.py` | `decision_foundation`, runtime models |
| `risk_service.py` | ports, providers, merge policy |

No imports from: workflow, builder, agents, llm, httpx.

---

## Test Coverage

**`tests/test_execution_planning_risk_provider.py`**

| Test | Coverage |
|------|----------|
| `test_execution_readiness_assessment` | Readiness dimensions |
| `test_decide_risk_uses_shared_facts_and_dimensions` | Foundation reuse |
| `test_greenfield_produces_implementation_risks` | Greenfield policy |
| `test_hybrid_produces_integration_risks` | Hybrid integration risk |
| `test_official_repository_produces_reduced_risks` | AS_IS reduced risk |
| `test_archived_repository_risk` | Archived repository |
| `test_missing_generation_targets` | Generation gap risk |
| `test_blocking_risk_creation` | Blocking risks |
| `test_fallback_strategy_generation` | Fallback strategies |
| `test_deterministic_execution` | Determinism |
| `test_rationale_generation` | Assessment rationale |
| `test_decision_notes` | Notes and diagnostics |
| `test_immutable_inputs` | Input ownership |
| `test_service_integration` | `RiskService` |
| `test_workflow_integration` | End-to-end `ExecutionStrategy` |
| `test_provider_matches_decide_risk` | Provider ↔ foundation parity |

---

## Remaining Work

| Item | Notes |
|------|-------|
| Remove `execution_planning/stages.py` legacy | Post provider migration cleanup |
| Optional document sync | ADR-0017, CURRENT_STATUS |

---

## Verdict

**Execution Planning Embedded Providers Complete**

All six embedded engineering decision providers now use the shared Decision Foundation:

```text
Strategy → Binding → Reuse → Adaptation → Generation → Risk → Builder → ExecutionStrategy
```

Risk decisions evaluate the completed engineering plan without modifying prior planning stages.
