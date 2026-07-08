# Embedded Strategy Provider Audit — Phase 6.1

**Date:** 2026-07-08  
**Scope:** `providers/embedded/strategy.py` — first real Execution Planning engineering decision  
**Verdict:** **Ready for Embedded Resource Binding Provider**

---

## Files Modified

| File | Change |
|------|--------|
| `providers/embedded/strategy.py` | Replaced skeleton with deterministic rule-based strategy decision |

## Files Added

| File | Purpose |
|------|---------|
| `tests/test_execution_planning_strategy_provider.py` | Provider tests (11 tests) |
| `docs/reviews/execution_planning_strategy_provider_phase_6_1/audit.md` | This audit |

## Files Unchanged (per phase scope)

| File | Notes |
|------|-------|
| `execution_planning/workflow.py` | Ordering and orchestration unchanged |
| `execution_planning/builder.py` | Assembly unchanged |
| `models/execution_planning_runtime.py` | Runtime contracts unchanged |
| `models/execution_strategy.py` | Canonical artifact unchanged |
| Other embedded providers | Still skeleton |
| `StrategyService` | Unchanged except consuming real embedded provider |

---

## Architecture

```text
ExecutionPlanningWorkflow
        ↓
StrategyService.execute(...)
        ↓
EmbeddedStrategyProvider.execute(...)
        ↓
StrategyDecisionSnapshot
        ↓
(later stages unchanged)
        ↓
ExecutionStrategyBuilder.build(...)
        ↓
ExecutionStrategy
```

Only the Strategy stage provider gained real engineering decision logic.

---

## Decision Policy

Deterministic rule priority (first match wins):

| Rule | Condition | Posture (canonical) | Scope (canonical) | Invocation factor |
|------|-----------|-------------------|-------------------|-------------------|
| **1 — REUSE** | Verified selected official repository AND no blocking/degraded discovery gaps | `OFFICIAL_REPOSITORY` | `NARROWED_SCOPE` | `invocation_reason:discovery_complete` |
| **2 — HYBRID** | Usable repository selection (PASS/PARTIAL verification) AND required gaps remain | `HYBRID` | `PARTIAL_REPRODUCTION` | `invocation_reason:discovery_partial` |
| **3 — GREENFIELD** | No usable repository selection | `GREENFIELD` | `FULL_REPRODUCTION` | `invocation_reason:insufficient_discovery` |

### Spec → canonical mapping

| Spec term | Canonical enum |
|-----------|----------------|
| REUSE | `StrategyPosture.OFFICIAL_REPOSITORY` |
| HYBRID | `StrategyPosture.HYBRID` |
| GREENFIELD | `StrategyPosture.GREENFIELD` |
| MINIMAL | `ScopeCommitment.NARROWED_SCOPE` |
| MODERATE | `ScopeCommitment.PARTIAL_REPRODUCTION` |
| FULL | `ScopeCommitment.FULL_REPRODUCTION` |
| DISCOVERY_SUFFICIENT | `invocation_reason:discovery_complete` in `deciding_factors` |
| PARTIAL_RESOURCE_AVAILABILITY | `invocation_reason:discovery_partial` |
| INSUFFICIENT_DISCOVERY | `invocation_reason:insufficient_discovery` |

No probabilities. No LLM. No inferred data beyond Discovery artifacts.

---

## Inputs

| Input | Used signals |
|-------|--------------|
| `PaperReproductionAnalysis` | Read-only (not mutated); not used for inference in this phase |
| `ResearchResourceDiscovery` | Selection (`primary_candidate_id` for code repository), verification status, discovery gaps (blocking/degraded), candidate officiality and resource type, discovery metadata status |

Provider does **not** infer selection from ranking when `SelectionRecord.primary_candidate_id` is absent.

---

## Outputs

| Field | Population |
|-------|------------|
| `primary_posture` | Rule outcome |
| `scope_commitment` | Rule outcome |
| `scope_narrowing_rationale` | Set when `NARROWED_SCOPE` (validation requirement) |
| `rationale` | Deterministic human-readable string |
| `deciding_factors` | `provider:embedded_strategy`, `rule:*`, `invocation_reason:*` |
| `decision_notes` | Step-by-step provenance (candidate, verification, gaps, posture) |
| `warnings` | When discovery status is not `COMPLETE` |
| `started_at` / `completed_at` | Populated |
| `alternative_postures_rejected` | Deterministic per rule |

Provider does **not** produce bindings, reuse, adaptation, generation, or risk outputs.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| No bindings / reuse / adaptation / generation / risks | ✅ |
| No Builder / Workflow calls | ✅ |
| No Discovery / Analysis mutation | ✅ tested |
| No network / GitHub / LLM | ✅ |
| Service merge policy unchanged | ✅ |
| Provider order Embedded → NoOp unchanged | ✅ |

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `providers/embedded/strategy.py` | `models.execution_planning_runtime`, `models.execution_strategy`, `models.paper_reproduction_analysis`, `models.research_resource_discovery` only |

No imports from: workflow, builder, services, agents, llm, providers.github, httpx.

---

## Test Coverage

**File:** `tests/test_execution_planning_strategy_provider.py`

| Test | Coverage |
|------|----------|
| `test_reuse_decision` | Rule 1 — OFFICIAL_REPOSITORY |
| `test_hybrid_decision` | Rule 2 — HYBRID |
| `test_greenfield_decision` | Rule 3 — GREENFIELD |
| `test_rationale_generation` | Human-readable rationale |
| `test_decision_notes` | Provenance notes |
| `test_stage_runtime_metadata` | Timestamps, warnings |
| `test_deterministic_execution` | Repeatable output |
| `test_service_integration` | StrategyService.default() |
| `test_provider_ordering_prefers_embedded` | Embedded wins merge |
| `test_workflow_integration` | End-to-end ExecutionStrategy |
| `test_immutable_analysis_and_discovery` | Input ownership |

Updated: `tests/test_execution_planning_services.py` (embedded factor assertions)

**Full suite:** 455 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Embedded Resource Binding Provider | Phase 6.2 |
| Embedded Reuse / Adaptation / Generation / Risk providers | Subsequent phases |
| Discovery selection stage producing `primary_candidate_id` for embedded E2E REUSE without handcrafted fixtures | Discovery enhancement |
| Migrate `execution_planning/stages.py` legacy logic into providers | Ongoing migration |
| `PlanningInvocationReason` enum extension for explicit invocation codes | Optional canonical model update |

---

## Verdict

**Ready for Embedded Resource Binding Provider**

Execution Planning now performs its first real engineering decision at the Strategy stage. Architecture, workflow ordering, builder, and canonical models remain unchanged. Subsequent stages still use skeleton providers until their embedded implementations land.
