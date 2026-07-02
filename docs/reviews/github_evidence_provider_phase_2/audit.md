# GitHub Evidence Provider Audit — Phase 2

**Date:** 2026-06-29  
**Scope:** `providers/github/evidence.py`, README client, evidence mapper, EvidenceService wiring  
**Verdict:** **Ready for GitHub Verification Provider**

---

## Files Added

| File | Purpose |
|------|---------|
| `providers/github/evidence.py` | `GitHubEvidenceProvider` implementing `EvidenceProvider` |
| `tests/test_github_evidence_provider.py` | Evidence provider tests (10 tests) |
| `docs/reviews/github_evidence_provider_phase_2/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `providers/github/client.py` | Implemented `get_readme()` with base64 UTF-8 decoding |
| `providers/github/models.py` | Added `decoded_text` on `GitHubReadmeDTO` |
| `providers/github/mapper.py` | Implemented `repository_to_evidence()` and `readme_to_evidence()` |
| `providers/github/exceptions.py` | Added `GitHubReadmeNotFoundError` |
| `providers/github/__init__.py` | Exported evidence types |
| `services/discovery/evidence_service.py` | Registered GitHub between Embedded and NoOp |
| `tests/conftest.py` | Offline GitHub evidence stub for non-GitHub tests |
| `tests/test_github_client.py` | README HTTP tests |
| `tests/test_github_mapper.py` | Evidence mapping tests |
| `tests/test_discovery_evidence.py` | Updated default provider outcome expectations |

---

## REST Endpoints

| Method | Endpoint | Status |
|--------|----------|--------|
| `GET /repos/{owner}/{repo}` | `get_repository()` | Implemented (Phase 1.2) |
| `GET /repos/{owner}/{repo}/readme` | `get_readme()` | **Implemented** |
| `GET /search/repositories` | `search_repositories()` | Not implemented |

HTTP remains confined to `client.py` via `httpx`.

---

## README Handling

| Behavior | Implementation |
|----------|----------------|
| Fetch README via REST | `GitHubClient.get_readme()` |
| Base64 decode | `_decode_readme_text()` in `client.py` |
| UTF-8 text | Stored in `GitHubReadmeDTO.decoded_text` |
| Missing README (HTTP 404) | `GitHubReadmeNotFoundError` |
| Provider policy | Metadata evidence still emitted; outcome `PARTIAL` |

No summarization, LLM, or semantic parsing.

---

## Evidence Mapping

### `repository_to_evidence()` → `EvidenceType.METADATA_EXTRACT`

Observed facts (no interpretation):

| Field | Source |
|-------|--------|
| `repository_url` | `html_url` |
| `full_name` | `full_name` |
| `owner` | `owner.login` |
| `description` | `description` |
| `license` | SPDX ID or license key |
| `topics` | joined topic list |
| `homepage` | `homepage` |
| `default_branch` | `default_branch` |
| `archived` | `archived` |
| `stars` | `stargazers_count` |
| `forks` | `forks_count` |
| `open_issues` | `open_issues_count` |
| `language` | `language` |
| `latest_push` | `pushed_at` ISO |
| `latest_update` | `updated_at` ISO |

### `readme_to_evidence()` → `EvidenceType.README_CLAIM`

| Field | Source |
|-------|--------|
| `readme_exists` | `True` |
| `readme_url` | `html_url` / `download_url` / `url` |
| `readme_text` | decoded UTF-8 raw text |
| `content_hash` | SHA-256 of decoded text |
| `encoding` | DTO encoding |
| `size` | DTO size |

Metadata and README are **separate append-only evidence records** per candidate.

---

## Provider Behavior

| Rule | Status |
|------|--------|
| Only `DiscoveryProvider.GITHUB` candidates | Yes |
| One metadata record per resolved repository | Yes |
| One README record when README exists | Yes |
| No README → metadata only, `PARTIAL` outcome | Yes |
| Authentication failure → `FAILED` outcome | Yes |
| Exceptions translated to `ProviderRecord` | Yes |
| Never raises across provider boundary | Yes |

---

## EvidenceService Integration

```text
EmbeddedEvidenceProvider
        ↓
GitHubEvidenceProvider
        ↓
NoOpEvidenceProvider
```

Registered in `EvidenceService._default_providers()`. Workflow unchanged.

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `evidence.py` | ports, canonical models, `GitHubClient`, `GitHubMapper`, exceptions |
| `client.py` | `httpx`, `auth`, `models`, `exceptions` |
| `mapper.py` | canonical `EvidenceRecord`, DTOs |
| `evidence_service.py` | `GitHubEvidenceProvider` only |

No verification, ranking, search, caching, retry, GraphQL, or workflow imports.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| HTTP only in `client.py` | Yes |
| No verification implementation | Yes |
| No ranking implementation | Yes |
| No Search API | Yes |
| No LLM / README summarization | Yes |
| DTOs isolated | Yes |
| Provider exceptions internal | Yes |
| Workflow unchanged | Yes |

---

## Test Coverage

```text
pixi run test
328 passed in 9.37s
```

New tests (`tests/test_github_evidence_provider.py`): **10**

| Area | Covered |
|------|---------|
| Metadata evidence | Yes |
| README evidence | Yes |
| No README (partial) | Yes |
| Base64 UTF-8 decoding | Yes |
| Evidence mapping | Yes (mapper tests) |
| EvidenceService integration | Yes |
| Workflow integration | Yes |
| Authentication failure translation | Yes |
| Non-GitHub candidate skip | Yes |
| Default provider order | Yes |

`tests/conftest.py` stubs live GitHub evidence in default providers for offline existing discovery tests.

---

## Remaining Work

| Item | Phase |
|------|-------|
| `GitHubVerificationProvider` | Next |
| `GitHubRankingProvider` | Phase 3 |
| Search API | Out of scope |
| Rate-limit retries / caching | Phase 4 |
| Hydra composition-root wiring | Optional |
| Live HTTP fixture tests | Optional |

---

## Verdict

**Ready for GitHub Verification Provider**

GitHub Evidence capability is complete for repository metadata and README collection. Evidence is append-only, deterministic, and isolated behind the `EvidenceProvider` port with failure translation at the provider boundary.
