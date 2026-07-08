# Embedded Adaptation Provider Audit — Phase 6.4

**Date:** 2026-07-08  
**Scope:** Embedded Adaptation Provider on shared Decision Foundation  
**Verdict:** **Ready for Embedded Generation Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/embedded/decision_foundation/adaptation_decision.py` | Adaptation engineering decision |
| `tests/test_execution_planning_adaptation_provider.py` | Adaptation provider and foundation tests (13 tests) |
| `docs/reviews/execution_planning_adaptation_provider_phase_6_4/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/adaptation.py` | Replaced skeleton with foundation-based provider |
| `providers/embedded/decision_foundation/__init__.py` | Export `AdaptationDecision`, `decide_adaptation` |
| `ports/adaptation_provider.py` | Accept analysis, discovery, reuse_result |
| `services/execution_planning/adaptation_service.py` | Pass analysis and discovery to providers |
| `services/execution_planning/protocols.py` | Updated `AdaptationService` protocol |
| `execution_planning/workflow.py` | Pass analysis and discovery to adaptation service |
| `providers/noop/adaptation.py` | Updated signature |
| `tests/test_execution_planning_workflow.py` | Updated adaptation service call assertion |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/builder.py` | Assembly unchanged |
| Canonical / runtime models | Unchanged |
| Strategy, binding, reuse providers | Behavior unchanged |
| Generation, risk providers | Still skeleton |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
AdaptationService.execute(analysis, discovery, reuse_result)
        ↓
EmbeddedAdaptationProvider
        ↓
Decision Foundation
    ObservedFacts → DecisionDimensions → decide_adaptation(strategy, bindings, reuse)
        ↓
AdaptationPlanSnapshot
        ↓
ExecutionStrategyBuilder.build(...)
```

Adaptation authorizes future engineering work only. It never executes adaptation.

---

## Adaptation Policy

Engineering decisions flow from prior stages only:

```text
Facts → Dimensions → Strategy → Bindings → Reuse → Adaptation
```

| Condition | Outcome |
|-----------|---------|
| Greenfield posture | Empty adaptation plan |
| `ReuseMode.NOT_APPLICABLE` | No authorized modifications |
| `ReuseMode.AS_IS` (primary only) | `adaptation_required=False`, scope `NONE` |
| `ReuseMode.AS_IS` + supporting components | `adaptation_required=True`, scope `MINIMAL` |
| `ReuseMode.HYBRID_COMPONENTS` | `adaptation_required=True`, scope `MINIMAL` or `MODERATE` |
| Official repository posture | Prefer `MINIMAL` scope |

---

## Authorized Modification Policy

Permitted classes (deterministic, binding-targeted):

| Component | Authorized classes |
|-----------|-------------------|
| Repository | `CONFIG_PATCH`, `SCRIPT_PATCH` |
| Checkpoint | `CONFIG_PATCH` (path replacement) |
| Dataset | `CONFIG_PATCH` (path replacement) |
| Supporting / fallback | `CONFIG_PATCH`, `SCRIPT_PATCH` |

Never authorized: `FORK`, `FRAMEWORK_PORT` (architecture replacement), algorithm redesign, model redesign, training objective changes.

Standard constraints recorded in `adaptation_constraints`.

---

## Decision Foundation Reuse

- `build_observed_facts()` — shared
- `evaluate_dimensions()` — shared
- New `decide_adaptation()` — adaptation-specific decision

No duplicated facts extraction or dimension evaluation.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No generation / risk logic | ✅ |
| No binding / reuse / strategy mutation | ✅ tested |
| No Builder / Workflow calls from provider | ✅ |
| No network / GitHub / LLM | ✅ |
| No direct discovery engineering decisions | ✅ |
| Workflow ordering unchanged | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `adaptation_decision.py` | `decision_foundation`, runtime snapshots, canonical adaptation types |
| `providers/embedded/adaptation.py` | `decision_foundation`, runtime models |
| `adaptation_service.py` | ports, providers, merge policy |

No imports from: workflow, builder, agents, llm, httpx.

---

## Test Coverage

**`tests/test_execution_planning_adaptation_provider.py`**

| Test | Coverage |
|------|----------|
| `test_decide_adaptation_uses_shared_facts_and_dimensions` | Foundation reuse |
| `test_as_is_produces_no_modifications` | AS_IS policy |
| `test_hybrid_components_produces_authorized_modifications` | HYBRID_COMPONENTS |
| `test_greenfield_posture_produces_empty_adaptation` | Greenfield |
| `test_supporting_resources_produce_limited_adaptation` | Supporting resources |
| `test_authorized_modification_generation` | Modification classes |
| `test_deterministic_execution` | Determinism |
| `test_rationale_generation` | Adaptation rationale |
| `test_decision_notes` | Notes and diagnostics |
| `test_immutable_inputs` | Input ownership |
| `test_service_integration` | `AdaptationService` |
| `test_workflow_integration` | End-to-end `ExecutionStrategy` |
| `test_provider_matches_decide_adaptation` | Provider ↔ foundation parity |

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded Generation Provider | Phase 6.5 |
| Embedded Risk Provider | Subsequent |
| Remove `execution_planning/stages.py` legacy | After provider migration |

---

## Verdict

**Ready for Embedded Generation Provider**

Execution Planning now performs Strategy → Binding → Reuse → Adaptation using the shared Decision Foundation. Adaptation decisions authorize future engineering work only and never execute it.
