# Embedded Resource Binding Provider Audit — Phase 6.2

**Date:** 2026-07-08  
**Scope:** Shared Decision Foundation + Embedded Resource Binding Provider  
**Verdict:** **Ready for Embedded Reuse Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/embedded/decision_foundation/__init__.py` | Internal foundation exports |
| `providers/embedded/decision_foundation/facts.py` | Observed facts builder |
| `providers/embedded/decision_foundation/dimensions.py` | Decision dimension evaluation |
| `providers/embedded/decision_foundation/strategy_decision.py` | Strategy engineering decision |
| `providers/embedded/decision_foundation/binding_decision.py` | Resource binding decision |
| `tests/test_execution_planning_binding_provider.py` | Foundation + binding tests (15 tests) |
| `docs/reviews/execution_planning_binding_provider_phase_6_2/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/strategy.py` | Refactored to use decision foundation (behavior preserved) |
| `providers/embedded/resource_binding.py` | Replaced skeleton with foundation-based binding |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/workflow.py` | Orchestration unchanged |
| `execution_planning/builder.py` | Assembly unchanged |
| Canonical / runtime models | Unchanged |
| Other embedded providers | Still skeleton |
| `StrategyService` / `ResourceBindingService` | Merge policy and ordering unchanged |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
StrategyService.execute / ResourceBindingService.execute
        ↓
EmbeddedStrategyProvider / EmbeddedResourceBindingProvider
        ↓
Decision Foundation
    ObservedFacts → DecisionDimensions → Engineering Decision
        ↓
Runtime Snapshot (StrategyDecisionSnapshot / ResourceBindingSnapshot)
        ↓
ExecutionStrategyBuilder.build(...)
        ↓
ExecutionStrategy
```

The decision foundation is **internal only** — not exported through canonical artifacts or public APIs.

---

## Decision Foundation

### Observed Facts (`facts.py`)

Immutable dataclasses representing objective state only:

| Fact | Source |
|------|--------|
| `selected_repository` / `selected_checkpoint` / `selected_dataset` | Discovery selections with resolved candidates |
| `supplementary_resources` | Fallback candidate IDs from selections |
| `required_resource_gaps` | Blocking + degraded discovery gaps |
| `repository_available` / `repository_official` / `repository_verified` | Derived from selection + verification |
| `repository_archived` | Gap type or candidate status |
| `checkpoint_available` / `dataset_available` | Verified PASS on selected resources |
| `repository_usable` | PASS or PARTIAL verification on repository |

No engineering decisions in facts.

### Decision Dimensions (`dimensions.py`)

| Dimension | Levels |
|-----------|--------|
| Resource Sufficiency | LOW / MEDIUM / HIGH / UNKNOWN |
| Resource Reliability | LOW / MEDIUM / HIGH / UNKNOWN |
| Engineering Commitment | LOW / MEDIUM / HIGH / UNKNOWN |
| Reuse Opportunity | LOW / MEDIUM / HIGH / UNKNOWN |
| Adaptation Requirement | LOW / MEDIUM / HIGH / UNKNOWN |
| Generation Requirement | LOW / MEDIUM / HIGH / UNKNOWN |

No numeric scoring. No probabilities.

### Engineering Decisions

| Module | Output |
|--------|--------|
| `strategy_decision.py` | `StrategyDecision` (posture, scope, rationale, factors) |
| `binding_decision.py` | `BindingDecision` (bindings, anchor, notes) |

---

## Strategy Refactor

`EmbeddedStrategyProvider` now executes:

```text
build_observed_facts → evaluate_dimensions → decide_strategy
```

Phase 6.1 rule behavior preserved:

| Rule | Condition | Posture |
|------|-----------|---------|
| REUSE | Official + verified + no required gaps | `OFFICIAL_REPOSITORY` |
| HYBRID | Usable repository + required gaps | `HYBRID` |
| GREENFIELD | Otherwise | `GREENFIELD` |

`deciding_factors` now include explicit `dimension:*` entries in addition to `rule:*` and `invocation_reason:*`. Observable strategy outcomes unchanged — all Phase 6.1 tests pass.

---

## Binding Policy

Bindings originate **only** from Discovery selections. No invented bindings.

| Selection | Verification | Role |
|-----------|--------------|------|
| Code repository (primary) | PASS | `PRIMARY_REPOSITORY` |
| Checkpoint (primary) | PASS | `CHECKPOINT` |
| Dataset (primary) | PASS | `DATASET` |
| Fallback / supplementary | PASS | `FALLBACK_REPOSITORY` or `SUPPORTING_ASSET` |
| Any primary | Not PASS | Not bound as primary |
| Greenfield posture | — | No bindings |

Binding uses the same `ObservedFacts` and `DecisionDimensions` as strategy.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No reuse / adaptation / generation / risk logic | ✅ |
| No Discovery / Analysis mutation | ✅ tested |
| No Builder / Workflow calls | ✅ |
| No network / GitHub / LLM | ✅ |
| Foundation not in public API | ✅ |
| Workflow ordering unchanged | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `decision_foundation/*` | `models.*`, `dataclasses`, `enum` only |
| `providers/embedded/strategy.py` | `decision_foundation`, runtime models |
| `providers/embedded/resource_binding.py` | `decision_foundation`, runtime models |

No imports from: workflow, builder, services (except via provider contract), agents, llm, httpx.

---

## Test Coverage

**`tests/test_execution_planning_binding_provider.py`**

| Test | Coverage |
|------|----------|
| `test_build_observed_facts_from_discovery` | Shared foundation |
| `test_evaluate_dimensions_produces_enum_levels` | Dimensions |
| `test_strategy_provider_behavior_unchanged_*` | Strategy refactor preservation |
| `test_decide_strategy_matches_provider_output` | Foundation ↔ provider parity |
| `test_primary_repository_binding` | PRIMARY_REPOSITORY |
| `test_checkpoint_binding` | CHECKPOINT |
| `test_dataset_binding` | DATASET |
| `test_supporting_resource_binding` | FALLBACK_REPOSITORY |
| `test_unverified_resources_not_primary` | Verification gate |
| `test_deterministic_bindings` | Determinism |
| `test_binding_rationale_and_notes` | Metadata |
| `test_immutable_inputs` | Input ownership |
| `test_service_integration` | ResourceBindingService |
| `test_workflow_integration` | End-to-end ExecutionStrategy |

**Full suite:** 470 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded Reuse Provider | Phase 6.3 |
| Embedded Adaptation Provider | Subsequent |
| Embedded Generation Provider | Subsequent |
| Embedded Risk Provider | Subsequent |
| Remove `execution_planning/stages.py` legacy | After provider migration |

---

## Verdict

**Ready for Embedded Reuse Provider**

Execution Planning now has a shared Decision Foundation (Facts → Dimensions → Decisions) used by both Strategy and Resource Binding providers. Architecture, workflow, builder, and canonical models remain unchanged. Future embedded providers can reuse the foundation without independent rule systems.
