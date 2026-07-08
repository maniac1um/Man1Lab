# Discovery Ranking Audit — Phase 2.4

**Date:** 2026-07-02  
**Scope:** RankingService + EmbeddedRankingProvider  
**Verdict:** **Ready for Selection Foundation**

---

## Architecture

```text
PaperReproductionAnalysis
        │
        ▼
DiscoveryWorkflow
        │
        ├── CollectionService → CandidateCollectionResult
        ├── EvidenceService   → EvidenceProviderResult
        ├── VerificationService → VerificationProviderResult
        │
        ▼
RankingService                         ← Discovery ranking entry point
        │
        ├── [1] EmbeddedRankingProvider
        ├── [2] NoOpRankingProvider
        ├── (future) GitHubRankingProvider
        ├── (future) HuggingFaceRankingProvider
        └── (future) CustomRankingStrategyProvider
        │
        ▼ merge
RankingResult
        │
        ▼
Selection → ResearchResourceDiscovery
```

---

## Modified Files

| File | Change |
|------|--------|
| `discovery/workflow.py` | Uses `RankingService` instead of skeleton `_run_ranking_stage` |
| `providers/__init__.py` | Exports `EmbeddedRankingProvider`, `NoOpRankingProvider` |
| `tests/test_discovery_collection.py` | Workflow uses `RankingService.default()` |
| `tests/test_discovery_evidence.py` | Workflow uses `RankingService.default()` |
| `tests/test_discovery_verification.py` | Workflow uses `RankingService.default()` |
| `tests/test_research_resource_discovery.py` | Workflow uses `RankingService` |

## New Files

| File | Purpose |
|------|---------|
| `ports/ranking_provider.py` | Ranking provider port + `RankingProviderResult` |
| `services/discovery/ranking_service.py` | Ranking provider orchestration |
| `services/discovery/ranking_merge.py` | Rank list dedup + stable union merge |
| `providers/embedded/embedded_ranking_provider.py` | Deterministic verification-status ranking |
| `providers/noop/noop_ranking_provider.py` | No-op ranking adapter |
| `providers/noop/ranking.py` | Re-export for noop package consistency |
| `tests/test_discovery_ranking.py` | Ranking layer tests (11 tests) |

---

## RankingService Design

| Responsibility | Owner |
|----------------|-------|
| Provider ordering | `RankingService` constructor / `default()` |
| Invoke providers sequentially | `RankingService.rank()` |
| Merge rank lists | `ranking_merge.merge_rank_lists()` |
| Return canonical result | `RankingResult` |

Default provider order:

1. `EmbeddedRankingProvider`
2. `NoOpRankingProvider`

```python
RankingService.default().rank(analysis, collection, evidence, verification)
```

---

## Ranking Merge Strategy

Documented in `services/discovery/ranking_merge.py`:

| Rule | Behavior |
|------|----------|
| Dedup key | `rank_list_id` (one list per resource need) |
| On duplicate | Keep first `rank_list_id` and `resource_need` |
| `ordered_candidate_ids` | Stable union (keeper order first) |
| `scores` | Prefer higher `total_score` for duplicate candidate IDs |
| `eligible_candidate_ids` | Stable union |
| Summary | Append provenance from duplicate providers |
| Discard policy | **Never** discard lists for distinct resource needs |

---

## EmbeddedRankingProvider

Deterministic ranking using **existing verification results only**:

| Rule | Behavior |
|------|----------|
| Ordering | pass > partial > skipped > fail > error |
| Tie-break | Preserve collection order (stable) |
| Eligibility | pass and partial only in `eligible_candidate_ids` |
| Scope | One `RankList` per `resource_need` |
| Candidates | Only those with `need_id` in `addresses_needs` |
| Scoring | `total_score` = verification status precedence (5–1) |

No networking. No popularity. No new candidates. No verification. No evidence collection.

---

## Workflow Changes

| Before | After |
|--------|-------|
| `_run_ranking_stage(resource_needs)` skeleton | `ranking_service.rank(analysis, collection, evidence, verification)` |
| Empty `ordered_candidate_ids` | Populated from embedded verification status |

Selection stage: **unchanged** (still skeleton).

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| Workflow knows only RankingService | **Yes** |
| Workflow does not know providers | **Yes** |
| Providers do not know workflow | **Yes** |
| No HTTP / GitHub / SDK / GraphQL | **Yes** |
| Ranking consumes verification only | **Yes** |
| Ranking never verifies resources | **Yes** |
| Ranking never collects evidence | **Yes** |
| Ranking never creates candidates | **Yes** |
| Analysis immutable | **Yes** |
| Append-only discovery | **Yes** |
| WorkflowOrchestrator unchanged | **Yes** |

---

## Dependency Audit

| Module | Imports providers? |
|--------|-------------------|
| `discovery/workflow.py` | **No** — only `RankingService` |
| `services/discovery/ranking_service.py` | Yes (composition root) |
| `providers/embedded/embedded_ranking_provider.py` | No workflow |
| `agents/*`, `workflow/orchestrator.py` | No discovery ranking imports |

Note: `services/verification_service.py` (execution layer) is unrelated to Discovery ranking.

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| SelectionService (mirror Collection/Evidence/Verification/Ranking pattern) | Selection Foundation |
| GitHub / HuggingFace ranking providers | External Provider Integration |
| Popularity, stars, forks heuristics | With external providers |
| Hydra-configurable ranking provider list | Optional |

---

## Test Results

```text
pixi run test
220 passed in 8.36s
```

New coverage (`tests/test_discovery_ranking.py`):

- Embedded ranking with pass verification
- Verification status ordering (pass > skipped > fail)
- Stable ordering within equal status
- Ranking merge preserves first rank list ID
- Append-only merge across resource needs
- Stable union preserves keeper order
- Provider ordering
- RankingService default merge
- Workflow end-to-end with ranked candidates
- Empty ranking when no candidates
- NoOp-only service returns empty

---

## Architecture Compliance

| Principle | Compliant |
|-----------|-----------|
| RankingService owns orchestration | **Yes** |
| Workflow provider-agnostic | **Yes** |
| Mirrors Collection/Evidence/Verification service pattern | **Yes** |
| Deterministic embedded ranking | **Yes** |
| Future providers plug into RankingService | **Yes** |

---

## Verdict

**Ready for Selection Foundation**

The fourth Discovery platform capability is complete. The pipeline successfully executes:

```text
PaperReproductionAnalysis → CollectionService → EvidenceService → VerificationService → RankingService → ResearchResourceDiscovery
```

without external APIs. Ranking relies only on deterministic verification results already inside the Discovery platform.
