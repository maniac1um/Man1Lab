# Embedded Generation Provider Audit — Phase 6.5

**Date:** 2026-07-08  
**Scope:** Embedded Generation Provider on shared Decision Foundation  
**Verdict:** **Ready for Embedded Risk Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/embedded/decision_foundation/generation_decision.py` | Generation engineering decision |
| `tests/test_execution_planning_generation_provider.py` | Generation provider and foundation tests (13 tests) |
| `docs/reviews/execution_planning_generation_provider_phase_6_5/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/generation.py` | Replaced skeleton with foundation-based provider |
| `providers/embedded/decision_foundation/__init__.py` | Export `GenerationDecision`, `decide_generation` |
| `ports/generation_provider.py` | Accept analysis, discovery, adaptation_result |
| `services/execution_planning/generation_service.py` | Pass discovery to providers |
| `services/execution_planning/protocols.py` | Updated `GenerationService` protocol |
| `execution_planning/workflow.py` | Pass discovery to generation service |
| `providers/noop/generation.py` | Updated signature |
| `tests/test_execution_planning_workflow.py` | Updated generation service call assertion |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/builder.py` | Assembly unchanged |
| Canonical / runtime models | Unchanged |
| Strategy, binding, reuse, adaptation providers | Behavior unchanged |
| Risk provider | Still skeleton |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
GenerationService.execute(analysis, discovery, adaptation_result)
        ↓
EmbeddedGenerationProvider
        ↓
Decision Foundation
    ObservedFacts → DecisionDimensions → decide_generation(...)
        ↓
GenerationPlanSnapshot
        ↓
ExecutionStrategyBuilder.build(...)
```

Generation plans which engineering artifacts must exist. It never creates them.

---

## Generation Policy

Engineering decisions flow from prior stages only:

```text
Facts → Dimensions → Strategy → Bindings → Reuse → Adaptation → Generation
```

| Condition | Outcome |
|-----------|---------|
| Greenfield posture | `generation_required=True`, scope `FULL_CODEBASE`, all scaffolding targets |
| `ReuseMode.AS_IS` + no adaptation | No generation required |
| Hybrid / partial reuse | `MISSING_MODULES` — generate only missing artifacts |
| Supporting resources + adaptation | Integration artifact targets (`STUB_FOR_INTEGRATION`) |

Generation never duplicates reusable components already committed in reuse.

---

## Engineering Artifact Policy

Generation targets use canonical `GenerationTarget` (analysis-module aligned):

| Target module | Intent | Artifact category |
|---------------|--------|-------------------|
| `RESOURCES` | `REPLACE_MISSING_UPSTREAM` / `STUB_FOR_INTEGRATION` | Configuration, deps, env, integration |
| `METHOD` | `STUB_FOR_INTEGRATION` | Training launcher, execution wrapper |
| `EVALUATION` | `STUB_FOR_INTEGRATION` | Evaluation launcher |
| `GOAL` | `STUB_FOR_INTEGRATION` | Inference launcher |

Never generated: `IMPLEMENT_FROM_PAPER` for model/algorithm, architecture redesign, training objective changes, paper reinterpretation, repository restructuring.

Standard constraints recorded in `generation_constraints`.

---

## Decision Foundation Reuse

- `build_observed_facts()` — shared
- `evaluate_dimensions()` — shared
- New `decide_generation()` — generation-specific decision

No duplicated facts extraction or dimension evaluation.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No risk logic | ✅ |
| No code/file generation | ✅ |
| No adaptation / reuse / binding / strategy mutation | ✅ tested |
| No Builder / Workflow calls from provider | ✅ |
| No network / GitHub / LLM | ✅ |
| No direct discovery engineering decisions | ✅ |
| Workflow ordering unchanged | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `generation_decision.py` | `decision_foundation`, runtime snapshots, canonical generation types |
| `providers/embedded/generation.py` | `decision_foundation`, runtime models |
| `generation_service.py` | ports, providers, merge policy |

No imports from: workflow, builder, agents, llm, httpx.

---

## Test Coverage

**`tests/test_execution_planning_generation_provider.py`**

| Test | Coverage |
|------|----------|
| `test_decide_generation_uses_shared_facts_and_dimensions` | Foundation reuse |
| `test_greenfield_generates_engineering_artifacts` | Greenfield policy |
| `test_official_repository_as_is_generates_nothing` | AS_IS policy |
| `test_hybrid_generates_missing_artifacts` | Hybrid missing modules |
| `test_supporting_resources_generate_integration_artifacts` | Supporting integration |
| `test_generation_target_creation` | `GenerationTarget` policy |
| `test_deterministic_execution` | Determinism |
| `test_rationale_generation` | Generation rationale |
| `test_decision_notes` | Notes and diagnostics |
| `test_immutable_inputs` | Input ownership |
| `test_service_integration` | `GenerationService` |
| `test_workflow_integration` | End-to-end `ExecutionStrategy` |
| `test_provider_matches_decide_generation` | Provider ↔ foundation parity |

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded Risk Provider | Phase 6.6 |
| Remove `execution_planning/stages.py` legacy | After provider migration |

---

## Verdict

**Ready for Embedded Risk Provider**

Execution Planning now performs Strategy → Binding → Reuse → Adaptation → Generation using the shared Decision Foundation. Generation decisions determine which engineering artifacts must exist without creating them.
