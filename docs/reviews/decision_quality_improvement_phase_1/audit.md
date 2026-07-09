# Decision Quality Improvement — Phase 1 Audit

**Project:** Man1Lab  
**Phase:** Decision Quality Improvement Phase 1  
**Scope:** Discovery Intelligence + Planning Intelligence only  
**Date:** 2026-07-09  
**Status:** Implemented

---

## 1. Objective

Improve decision quality across Discovery and Execution Planning so that:

1. Discovery produces evidence-backed repository selection committed in `ResearchResourceDiscovery.selection`.
2. Planning fully consumes Discovery selections through the Decision Foundation pipeline.
3. Incorrect GREENFIELD decisions are eliminated when a verified repository has been discovered and selected.
4. Planning outputs are execution-oriented (bindings, reuse, generation targets, readiness diagnostics) — not risk summaries alone.
5. A Golden Benchmark suite detects decision regressions automatically.

**Out of scope (per constraints):** Runtime, Console, Provider redesign; Execution implementation; new user-facing features; public API changes.

---

## 2. Architecture Impact

### 2.1 Discovery Layer

| Change | Location | Impact |
|--------|----------|--------|
| **Real selection stage** | `discovery/selection.py` (new) | Replaces skeleton selection in `discovery/workflow.py`. Consumes `RankingResult`, verification, and evidence to commit `primary_candidate_id`, fallbacks, confidence, and verification snapshots per resource need. |
| **Gap coherence** | `discovery/selection.py` | Emits `discovery_gaps` when no eligible candidate exists; closes analysis gaps when selection succeeds. Fixes metadata `selection_count` / `status` inconsistency. |
| **Workflow wiring** | `discovery/workflow.py` | Selection stage passes candidates, verification, and evidence into `run_selection()`; updates candidate status markers after selection. |
| **Candidate normalization** | `services/discovery/candidate_merge.py` | `normalize_candidate_identity()` ensures `identity.normalized_url` is set during merge. |

Discovery internal layering is unchanged:

```text
DiscoveryWorkflow → Services → Providers → Builder → ResearchResourceDiscovery
```

Selection is native Discovery logic (no new provider port, no public API change).

### 2.2 Execution Planning Layer

| Change | Location | Impact |
|--------|----------|--------|
| **OFFICIAL_USABLE posture** | `strategy_decision.py` | Official repository with PARTIAL verification and no required gaps routes to `OFFICIAL_REPOSITORY` (`rule:official_usable`) instead of incorrect GREENFIELD. |
| **COMMUNITY_FORK posture** | `strategy_decision.py` | Verified community repository without required gaps routes to `COMMUNITY_FORK` (`rule:community`). |
| **Explicit GREENFIELD rationale** | `strategy_decision.py` | When GREENFIELD is chosen despite a usable repository, rejection reasons and rationale document why. |
| **PARTIAL repository binding** | `providers/embedded/decision_foundation/binding_decision.py` | Primary repository binding accepts PASS or PARTIAL verification, enabling reuse/adaptation downstream. |
| **COMMUNITY_FORK reuse** | `providers/embedded/decision_foundation/reuse_decision.py` | Maps COMMUNITY_FORK posture to `ReuseMode.AS_IS`. |
| **Selection confidence in facts** | `providers/embedded/decision_foundation/facts.py` | `SelectedResourceFact.selection_confidence` propagated from discovery selection records. |

No changes to `ExecutionPlanningWorkflow` stage order, service interfaces, or canonical `ExecutionStrategy` schema.

---

## 3. Information-Flow Audit

### 3.1 Before Phase 1 (defect)

```text
Discovery: Collection → Evidence → Verification → Ranking → Selection (skeleton)
                                                              ↓
                                                    primary_candidate_id = null
                                                              ↓
Planning: build_observed_facts() → selected_repository = None → GREENFIELD
```

**Root cause:** Selection stage discarded ranking output and never committed selections, so Planning could not observe discovered repositories.

### 3.2 After Phase 1 (fixed)

```text
Discovery: Collection → Evidence → Verification → Ranking → Selection
                                                              ↓
                              primary_candidate_id, confidence, verification_snapshot
                                                              ↓
Planning: build_observed_facts() → selected_repository + verification status
              ↓
         evaluate_dimensions()
              ↓
    Strategy → Binding → Reuse → Adaptation → Generation → Risk
```

### 3.3 Stage consumption matrix

| Planning stage | Discovery inputs consumed | Phase 1 fix |
|----------------|---------------------------|-------------|
| **Strategy** | `selection.primary_candidate_id`, verification status, `discovery_gaps` | Selection population enables REUSE / COMMUNITY_FORK / HYBRID rules |
| **Binding** | Selected repository/checkpoint/dataset + verification | PARTIAL binding for repository |
| **Reuse** | Bindings derived from selections | No longer NOT_APPLICABLE when repo selected |
| **Adaptation** | Gaps + partial verification triggers | Triggered when HYBRID or partial bind |
| **Generation** | Gaps + reuse mode | Greenfield only when no usable selection |
| **Risk** | All prior stages + readiness | Readiness breakdown in notes; blocking risks from discovery gaps |

### 3.4 Rule: no ignored valid repository

| Condition | Posture | Rationale recorded |
|-----------|---------|-------------------|
| Official + PASS + no required gaps | `OFFICIAL_REPOSITORY` | `rule:reuse` |
| Community + PASS + no required gaps | `COMMUNITY_FORK` | `rule:community_fork` |
| Usable + required gaps | `HYBRID` | `rule:hybrid` |
| Usable + partial verification, no gaps | `OFFICIAL_REPOSITORY` | `rule:official_usable` |
| No usable selection | `GREENFIELD` | `rule:greenfield` + explicit rejections |

---

## 4. Benchmark Coverage

Golden benchmarks live in `tests/benchmarks/fixtures.py`. Regression runner: `tests/benchmarks/test_decision_quality_benchmarks.py`.

| Benchmark | Paper profile | Validates |
|-----------|---------------|-----------|
| `resnet_official_repo_embedded` | ResNet (1512.03385) — official GitHub repo + dataset | Repository selection, confidence ≥ 0.6, `OFFICIAL_REPOSITORY`, bindings, `AS_IS` reuse, no generation |
| `resnet_hybrid_checkpoint_gap` | ResNet + checkpoint gap | Repository selection, `OFFICIAL_REPOSITORY` or `HYBRID`, no GREENFIELD |
| `no_resources_greenfield` | Analysis with no embedded URLs | `GREENFIELD`, no bindings, `NOT_APPLICABLE` reuse, generation required |

Each benchmark asserts:

- Repository selection (when applicable)
- Selection confidence floor
- Strategy posture
- Binding count
- Reuse mode
- Execution readiness proxy (metadata status + blocking risks)
- **Anti-regression:** no GREENFIELD when a repository was selected

Supporting tests:

- `tests/test_discovery_selection.py` — unit tests for selection logic
- `tests/benchmarks/test_decision_quality_benchmarks.py` — golden suite + partial-verification regression

**Test results (Phase 1):** 804 tests passed (including golden benchmark subtests).

---

## 5. Regression Improvements

| Regression | Detection |
|------------|-----------|
| Skeleton selection (candidates exist, `selection_count=0`) | Golden benchmarks + `test_embedded_workflow_produces_repository_selection` |
| GREENFIELD despite embedded official repo | `resnet_official_repo_embedded` / platform integration tests |
| GREENFIELD with official repo + PARTIAL verification | `OfficialRepoNotGreenfieldRegressionTest` |
| HYBRID not chosen when gaps remain | `resnet_hybrid_checkpoint_gap` benchmark |
| Binding chain broken after selection | Binding count assertions in benchmarks |
| Permissive `{OFFICIAL, HYBRID, GREENFIELD}` integration test | Replaced with exact `OFFICIAL_REPOSITORY` expectation |

---

## 6. Remaining Work

| Item | Priority | Notes |
|------|----------|-------|
| GitHub-backed golden benchmarks | P1 | Current benchmarks use embedded providers only; add network-isolated fixtures with recorded GitHub responses |
| Community fork benchmark case | P2 | `COMMUNITY_FORK` rule implemented; dedicated golden fixture not yet added |
| `analysis` usage in `build_observed_facts()` | P2 | Analysis parameter still unused for cross-checks |
| PARTIAL binding for checkpoint/dataset | P3 | Only repository primary binding accepts PARTIAL |
| Ranking beyond verification precedence | P3 | Embedded ranking still verification-only; GitHub scores not integrated into selection confidence |
| Manual override support | Future | Schema reserved; not implemented |
| Execution stage | Out of scope | Planning outputs execution-ready artifacts; Runner consumption is a later milestone |

---

## 7. Files Changed / Added

### Added

- `discovery/selection.py`
- `tests/benchmarks/fixtures.py`
- `tests/test_discovery_selection.py`

### Modified

- `discovery/workflow.py`
- `services/discovery/candidate_merge.py`
- `providers/embedded/decision_foundation/strategy_decision.py`
- `providers/embedded/decision_foundation/facts.py`
- `providers/embedded/decision_foundation/binding_decision.py`
- `providers/embedded/decision_foundation/reuse_decision.py`
- `providers/embedded/decision_foundation/risk_decision.py`
- `tests/test_discovery_selection.py`
- `tests/test_execution_planning_strategy_provider.py`
- `tests/test_platform_integration.py`
- `docs/CURRENT_STATUS.md`
- `docs/architecture/ARCHITECTURE.md`

---

## 8. Summary

Phase 1 closes the critical Discovery → Planning disconnect by implementing evidence-backed selection and tightening Planning rules so discovered repositories flow through binding, reuse, and readiness assessment. Golden benchmarks guard three representative decision paths and will fail CI on posture, selection, or binding regressions.
