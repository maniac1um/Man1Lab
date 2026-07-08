# Embedded Reuse Provider Audit — Phase 6.3

**Date:** 2026-07-08  
**Scope:** Embedded Reuse Provider on shared Decision Foundation  
**Verdict:** **Ready for Embedded Adaptation Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/embedded/decision_foundation/reuse_decision.py` | Reuse engineering decision from facts, dimensions, bindings |
| `tests/test_execution_planning_reuse_provider.py` | Reuse provider and foundation tests (14 tests) |
| `docs/reviews/execution_planning_reuse_provider_phase_6_3/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/reuse.py` | Replaced skeleton with foundation-based reuse provider |
| `providers/embedded/decision_foundation/__init__.py` | Export `ReuseDecision`, `decide_reuse` |
| `ports/reuse_provider.py` | Accept analysis, discovery, binding_result for foundation reuse |
| `services/execution_planning/reuse_service.py` | Pass analysis and discovery to providers |
| `services/execution_planning/protocols.py` | Updated `ReuseService` protocol |
| `execution_planning/workflow.py` | Pass analysis and discovery to reuse service |
| `providers/noop/reuse.py` | Updated signature |
| `tests/test_execution_planning_workflow.py` | Updated reuse service call assertion |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/builder.py` | Assembly unchanged |
| Canonical / runtime models | Unchanged |
| Strategy / binding providers | Behavior unchanged |
| Adaptation, generation, risk providers | Still skeleton |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
ReuseService.execute(analysis, discovery, binding_result)
        ↓
EmbeddedReuseProvider
        ↓
Decision Foundation
    ObservedFacts → DecisionDimensions → decide_reuse(bindings, strategy)
        ↓
ReusePlanSnapshot
        ↓
ExecutionStrategyBuilder.build(...)
```

Reuse engineering decisions originate from **resource bindings**, not direct discovery rule logic. Facts and dimensions are built via the shared foundation for consistency across providers.

---

## Decision Flow

```text
PaperReproductionAnalysis + ResearchResourceDiscovery
        ↓
build_observed_facts()
        ↓
evaluate_dimensions()
        ↓
decide_reuse(facts, dimensions, bindings, strategy)
        ↓
ReusePlanSnapshot
```

The provider does not embed rule logic — it delegates to `decide_reuse`.

---

## Reuse Policy

Reuse operates only on existing bindings from `ResourceBindingResult`.

| Binding role | Reuse eligibility | Extent |
|--------------|-------------------|--------|
| `PRIMARY_REPOSITORY` | Eligible | `FULL` |
| `CHECKPOINT` | Eligible | `FULL` |
| `DATASET` | Eligible | `FULL` |
| `FALLBACK_REPOSITORY` | Eligible (verified) | `PARTIAL` |
| `SUPPORTING_ASSET` | Eligible (verified) | `ENTRYPOINT_ONLY` |

| Condition | Outcome |
|-----------|---------|
| Greenfield posture or no bindings | `ReuseMode.NOT_APPLICABLE` |
| No eligible bindings | `NOT_APPLICABLE` + exclusions |
| Official repository posture | `AS_IS` |
| Hybrid posture | `HYBRID_COMPONENTS` |
| Supporting-only bindings | `HYBRID_COMPONENTS` |

Unbound discovery selections (from facts, not re-decided from discovery) populate `ExcludedComponent` with deterministic exclusion reasons.

No reusable components are invented — only bound resources are evaluated.

---

## Decision Foundation Reuse

Phase 6.2 foundation reused without duplication:

- `build_observed_facts()` — shared facts extraction
- `evaluate_dimensions()` — shared dimension evaluation
- New `decide_reuse()` — reuse-specific engineering decision

Strategy and binding providers unchanged.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No adaptation / generation / risk logic | ✅ |
| No binding / strategy / discovery / analysis mutation | ✅ tested |
| No Builder / Workflow calls from provider | ✅ |
| No network / GitHub / LLM | ✅ |
| Engineering decisions from bindings | ✅ |
| Workflow ordering unchanged | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `reuse_decision.py` | `decision_foundation`, runtime snapshots, canonical reuse types |
| `providers/embedded/reuse.py` | `decision_foundation`, runtime models, analysis/discovery models |
| `reuse_service.py` | ports, providers, merge policy |

No imports from: workflow, builder, agents, llm, httpx.

---

## Test Coverage

**`tests/test_execution_planning_reuse_provider.py`**

| Test | Coverage |
|------|----------|
| `test_decide_reuse_uses_shared_facts_and_dimensions` | Foundation reuse |
| `test_repository_reuse` | Repository `ReuseComponent` |
| `test_checkpoint_reuse` | Checkpoint reuse |
| `test_dataset_reuse` | Dataset reuse |
| `test_supporting_resource_reuse` | Fallback reuse |
| `test_excluded_component_generation` | `ExcludedComponent` |
| `test_no_reusable_resources` | `NOT_APPLICABLE` |
| `test_deterministic_execution` | Determinism |
| `test_rationale_generation` | `reuse_assumptions` |
| `test_decision_notes` | Notes and diagnostics |
| `test_immutable_inputs` | Input ownership |
| `test_service_integration` | `ReuseService` |
| `test_workflow_integration` | End-to-end `ExecutionStrategy` |
| `test_provider_matches_decide_reuse` | Provider ↔ foundation parity |

**Full suite:** 484 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded Adaptation Provider | Phase 6.4 |
| Embedded Generation Provider | Subsequent |
| Embedded Risk Provider | Subsequent |
| Remove `execution_planning/stages.py` legacy | After provider migration |

---

## Verdict

**Ready for Embedded Adaptation Provider**

Execution Planning now performs Strategy → Binding → Reuse using the shared Decision Foundation. Reuse decisions originate only from existing bindings and foundation dimensions. Architecture, builder, canonical models, and runtime models remain unchanged.
