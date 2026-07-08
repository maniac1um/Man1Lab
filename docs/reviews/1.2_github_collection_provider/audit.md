# GitHub Collection Provider Audit — Phase 1.2

**Date:** 2026-06-29  
**Scope:** `providers/github/collection.py`, HTTP `get_repository`, mapper, CollectionService wiring  
**Verdict:** **Ready for GitHub Evidence Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/github/collection.py` | `GitHubCollectionProvider` implementing `CollectionProvider` |
| `tests/test_github_collection_provider.py` | Collection provider tests (15 tests) |
| `tests/conftest.py` | Offline GitHub stub for non-GitHub test modules |
| `docs/reviews/github_collection_provider_phase_1_2/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/github/client.py` | Implemented `get_repository()` via `httpx` |
| `providers/github/mapper.py` | Implemented `repository_to_candidate()` |
| `providers/github/__init__.py` | Exported `GitHubCollectionProvider` |
| `services/discovery/collection_service.py` | Registered GitHub between Embedded and NoOp |
| `pixi.toml` | Added `httpx` dependency |
| `tests/test_github_client.py` | HTTP success / 404 / 401 tests |
| `tests/test_github_mapper.py` | `repository_to_candidate` coverage |
| `tests/test_discovery_collection.py` | Updated default provider outcome expectations |

---

## REST Endpoints Implemented

| Method | Endpoint | Status |
|--------|----------|--------|
| `GET /repos/{owner}/{repo}` | `GitHubClient.get_repository()` | Implemented |
| `GET /repos/{owner}/{repo}/readme` | `GitHubClient.get_readme()` | Not implemented (Phase 2) |
| `GET /search/repositories` | `GitHubClient.search_repositories()` | Not implemented (later phase) |

HTTP is confined to `client.py` using `httpx` with configurable timeout and injectable `http_client` for tests.

---

## Provider Behavior

| Rule | Implementation |
|------|----------------|
| Only explicit paper GitHub URLs | `extract_github_repository_urls()` |
| Sources: `external_resources` (repository-classified), `artifacts.location` | Yes |
| Ignore datasets, model cards, non-repository types | Yes |
| Ignore non-GitHub URLs | Yes |
| One URL → one `get_repository` call | Yes |
| Duplicate URLs → single candidate (`full_name` dedup) | Yes |
| No Search API | `search_repositories` not called |
| No README | Not in scope |
| Exceptions → `ProviderRecord` outcomes | Yes — never raises across boundary |
| CollectionService continues on failure | Yes |

---

## Mapper Implementation

`GitHubMapper.repository_to_candidate()` maps:

| DTO field | Canonical target |
|-----------|------------------|
| `html_url` / `source_url` | `url`, `identity.normalized_url`, `extensions.source_url` |
| `full_name` | `identity.provider_native_id` |
| `owner.login` | `extensions.github_owner` |
| `description` | `notes` |
| `default_branch` | `extensions.github_default_branch` |
| `license` | `extensions.github_license` |
| `archived` | `extensions.github_archived` |
| `topics` | `extensions.github_topics` |
| `fork` | `resource_type`, `officiality` |
| — | `provider=GITHUB`, `confidence=0.95`, `collection_source` with provenance |

---

## Failure Translation

| Exception | Provider outcome |
|-----------|------------------|
| `GitHubNotFoundError` | `FAILED` or `PARTIAL`; per-URL error note |
| `GitHubAuthenticationError` | `FAILED`; stops further resolution |
| `GitHubRateLimitError` / `GitHubTimeoutError` / `GitHubProviderError` | Recorded; continues other URLs |
| No GitHub repository URLs | `SKIPPED` |

---

## CollectionService Integration

```text
EmbeddedResourceProvider
        ↓
GitHubCollectionProvider
        ↓
NoOpCollectionProvider
```

Registered in `CollectionService._default_providers()`. Workflow unchanged — still calls `CollectionService` only.

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `collection.py` | ports, canonical models, `GitHubClient`, `GitHubMapper`, exceptions |
| `client.py` | `httpx`, `auth`, `models`, `exceptions` |
| `mapper.py` | canonical `RepositoryCandidate`, DTOs, `normalize_url` |
| `collection_service.py` | `GitHubCollectionProvider` only |

No workflow, planner, execution_planning, or evidence/verification/ranking provider imports.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| HTTP only in `client.py` | Yes |
| No Search API | Yes |
| No README | Yes |
| No Evidence / Verification / Ranking | Yes |
| Provider exceptions stay internal | Yes |
| DTOs do not leak to workflow | Yes |
| Workflow unchanged | Yes |

---

## Test Coverage

```text
pixi run test
317 passed in 8.94s
```

New tests (`tests/test_github_collection_provider.py`): **15**

| Area | Tests |
|------|-------|
| Valid repository URL resolution | Yes |
| Multiple URLs | Yes |
| Duplicate URL dedup | Yes |
| Non-repository / ignored URLs | Yes |
| Repository not found | Yes |
| Authentication failure | Yes |
| Provider outcome generation | Yes |
| Search API not used | Yes |
| Artifact GitHub URL | Yes |
| URL parsing helpers | Yes |
| Mapper field mapping | Yes |
| CollectionService merge | Yes |
| Default provider order | Yes |
| Workflow end-to-end | Yes |

`tests/conftest.py` stubs live GitHub in default providers for offline existing discovery tests.

---

## Remaining Work

| Item | Phase |
|------|-------|
| `GitHubClient.get_readme()` | Evidence Provider |
| `GitHubEvidenceProvider` | Phase 2 |
| `GitHubVerificationProvider` | Phase 2 |
| `GitHubRankingProvider` | Phase 3 |
| Search API | Out of scope for Phase 1.2 |
| Rate-limit retries / caching | Phase 4 |
| Hydra composition-root registration | Optional |
| Recorded HTTP fixtures for live integration | Optional |

---

## Verdict

**Ready for GitHub Evidence Provider**

Discovery can now resolve explicit GitHub repositories cited in `PaperReproductionAnalysis` through the first production `CollectionProvider`. Resolution is deterministic, Search-free, and isolated behind ports with failure translation at the provider boundary.
