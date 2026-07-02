# GitHub Ranking Provider Audit — Phase 4

**Date:** 2026-06-29  
**Scope:** `providers/github/ranking.py`, RankingService wiring  
**Verdict:** **GitHub Discovery Provider Complete**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `providers/github/ranking.py` | `GitHubRankingProvider` — deterministic ranking from collected artifacts only |
| `tests/test_github_ranking_provider.py` | Ranking provider tests (15 tests) |
| `docs/reviews/github_ranking_provider_phase_4/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/github/__init__.py` | Exported `GitHubRankingProvider` |
| `services/discovery/ranking_service.py` | Registered GitHub between Embedded and NoOp |
| `tests/conftest.py` | Offline GitHub ranking stub for non-GitHub tests |

---

## Scoring Model

Deterministic weighted sum — no ML, embeddings, or LLM. Each candidate receives `total_score`, `factor_scores`, and `ranking_factors` (with per-signal summaries).

| Signal | Weight | Source |
|--------|--------|--------|
| Verification PASS | 100.0 | `VerificationRecord.status` |
| Verification PARTIAL | 70.0 | `VerificationRecord.status` |
| Verification FAIL | 30.0 | `VerificationRecord.status` |
| Verification SKIPPED | 20.0 | `VerificationRecord.status` |
| Verification ERROR | 10.0 | `VerificationRecord.status` |
| Identity match | 50.0 | `repository_identity_match` check PASS |
| Paper URL match | 40.0 | `paper_url_match` check PASS |
| Not archived | 30.0 | metadata `archived == false` |
| Metadata completeness PASS | 25.0 | `repository_metadata_completeness` PASS |
| Metadata completeness PARTIAL | 10.0 | `repository_metadata_completeness` PARTIAL |
| README present | 20.0 | `readme_present` check PASS |
| License present | 15.0 | `repository_license_present` check PASS |
| Description present | 10.0 | `repository_description_present` check PASS |
| Topics present | 5.0 | `repository_topics_present` check PASS |
| Stars | 0–10.0 | `min(10, stars / 100)` from metadata evidence |
| Forks | 0–10.0 | `min(10, forks / 50)` from metadata evidence |
| Latest push | 0–10.0 | Recency from `latest_push` ISO timestamp |

GitHub-specific signals apply only to candidates with `DiscoveryProvider.GITHUB`.

---

## Ranking Signals (Priority Order)

1. Verification overall status — PASS > PARTIAL > FAIL (via status weight)
2. Identity match
3. Paper URL match
4. Repository archived (non-archived preferred)
5. Repository metadata completeness
6. README present
7. License present
8. Description present
9. Topics present
10. Stars
11. Forks
12. Latest push

---

## Tie-Breaking

When `total_score` is equal within a group:

1. Identity match (PASS preferred)
2. Paper URL match (PASS preferred)
3. Higher stars
4. More recent `latest_push` (lexicographic ISO compare)
5. Original collection order (stable)

Eligible candidates (PASS, PARTIAL) are always ordered before ineligible (FAIL, SKIPPED, ERROR). FAIL candidates remain visible but ranked after eligible candidates.

---

## RankList Output

One `RankList` per `ResourceNeed` in `collection_result.resource_needs`:

| Field | Population |
|-------|------------|
| `rank_list_id` | `rank-{need_id}` |
| `ordered_candidate_ids` | Eligible first (by score + tie-break), then ineligible |
| `eligible_candidate_ids` | PASS and PARTIAL only |
| `scores` | `RankScore` per candidate with breakdown |
| `ranking_factors_summary` | Human-readable summary of scoring approach |
| `created_at` | Provider invocation timestamp |

---

## RankingService Integration

```text
EmbeddedRankingProvider
        ↓
GitHubRankingProvider
        ↓
NoOpRankingProvider
```

Registered in `RankingService._default_providers()`. Merge strategy unchanged — GitHub participates via `merge_rank_lists` like embedded/noop providers.

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `ranking.py` | ports, canonical models only |
| `ranking_service.py` | `GitHubRankingProvider` only |

No HTTP, `GitHubClient`, collection, evidence creation, verification creation, workflow, planner, execution_planning, Hydra, or MLflow imports.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| No networking | Yes |
| No GitHubClient | Yes |
| Consumes `CollectionProviderResult` + `EvidenceProviderResult` + `VerificationProviderResult` only | Yes |
| Produces `RankingProviderResult` | Yes |
| Never throws | Yes |
| Never removes candidates | Yes |
| Always returns RankList per need | Yes |
| No new evidence / verification / candidates | Yes |
| Workflow unchanged | Yes |
| Only GitHub candidates scored with GitHub signals | Yes |

---

## Test Coverage

```text
pixi run test
355 passed
```

New tests (`tests/test_github_ranking_provider.py`): **15**

| Area | Covered |
|------|---------|
| PASS > PARTIAL > FAIL ordering | Yes |
| Identity tie-break | Yes |
| Paper URL tie-break | Yes |
| Archived penalty | Yes |
| Metadata completeness | Yes |
| README influence | Yes |
| Stars influence | Yes |
| Forks influence | Yes |
| Latest push influence | Yes |
| Stable ordering on tie | Yes |
| Score breakdown populated | Yes |
| RankingService integration | Yes |
| Default provider order | Yes |
| Workflow integration (offline mocks) | Yes |

---

## GitHub Discovery Provider — End-to-End

```text
Collection (GitHubCollectionProvider — HTTP)
        ↓
Evidence (GitHubEvidenceProvider — HTTP)
        ↓
Verification (GitHubVerificationProvider — offline)
        ↓
Ranking (GitHubRankingProvider — offline)
```

All four stages are registered in their respective discovery services. Networking is confined to Collection and Evidence only.

---

## Remaining Work

| Item | Status |
|------|--------|
| GitHub Search API | Out of scope |
| Caching / retry | Out of scope |
| Selection provider | Future phase |
| Hydra composition-root wiring | Optional |

---

## Verdict

**GitHub Discovery Provider Complete**

Discovery now executes Collection → Evidence → Verification → Ranking for GitHub production candidates. Ranking is deterministic, provider-isolated, consumes only existing discovery artifacts, and performs no networking.
