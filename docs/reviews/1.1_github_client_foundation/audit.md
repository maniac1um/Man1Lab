# GitHub Client Foundation Audit — Phase 1.1

**Date:** 2026-06-29  
**Scope:** `providers/github/` foundation package (no HTTP)  
**Verdict:** **Ready for GitHub Collection Provider**

---

## Implemented Modules

| Module | Responsibility | Phase 1.1 status |
|--------|----------------|------------------|
| `providers/github/__init__.py` | Public exports for foundation types | Complete |
| `providers/github/auth.py` | `GitHubAuth` — token resolution and headers | Complete |
| `providers/github/client.py` | `GitHubClient` — REST interface stub | Complete |
| `providers/github/models.py` | Frozen GitHub REST DTOs | Complete |
| `providers/github/mapper.py` | `GitHubMapper` — DTO → canonical mapping stub | Complete |
| `providers/github/exceptions.py` | Provider-scoped exception hierarchy | Complete |

Not implemented (by design):

| Module | Phase |
|--------|-------|
| `collection.py` | Next — Collection Provider |
| `evidence.py` | Phase 2 |
| `verification.py` | Phase 2 |
| `ranking.py` | Phase 3 |

---

## Dependency Audit

| Module | Depends on | Does not depend on |
|--------|------------|-------------------|
| `exceptions.py` | stdlib only | — |
| `models.py` | `pydantic` | Discovery services, HTTP libs |
| `auth.py` | stdlib (`os`) | HTTP libs, workflow |
| `client.py` | `auth`, `models` | HTTP libs, ports |
| `mapper.py` | `models`, `RepositoryCandidate` (canonical type only) | HTTP, workflow, services |
| `__init__.py` | local github modules | — |

**HTTP / SDK audit:** No `requests`, `httpx`, `urllib` network calls, or GitHub SDK imports in `providers/github/`.

---

## Import Boundary Verification

| Constraint | Status |
|------------|--------|
| No workflow imports | Yes |
| No Discovery service imports | Yes |
| No provider port implementations | Yes |
| No Hydra / MLflow imports | Yes |
| No agent / planner / execution_planning imports | Yes |
| `mapper.py` references canonical `RepositoryCandidate` only | Yes |
| DTOs isolated in `models.py` | Yes |

Workflow and services remain unchanged. GitHub package is not registered in composition root yet.

---

## DTO Isolation

| DTO | Purpose |
|-----|---------|
| `GitHubOwnerDTO` | Owner account fragment |
| `GitHubLicenseDTO` | License metadata |
| `GitHubRepositoryDTO` | `GET /repos/{owner}/{repo}` shape |
| `GitHubSearchItemDTO` | Search result item |
| `GitHubSearchResultDTO` | `GET /search/repositories` page |
| `GitHubReadmeDTO` | `GET /repos/{owner}/{repo}/readme` shape |
| `GitHubErrorDTO` | Error response body |

All DTOs are frozen Pydantic models. They mirror REST payloads only and do not replace `RepositoryCandidate` or other canonical Discovery models.

---

## Client Interface

| Method | Future REST resource | Phase 1.1 behavior |
|--------|---------------------|-------------------|
| `get_repository(owner, repo)` | `GET /repos/{owner}/{repo}` | Raises `NotImplementedError` |
| `get_readme(owner, repo)` | `GET /repos/{owner}/{repo}/readme` | Raises `NotImplementedError` |
| `search_repositories(query, ...)` | `GET /search/repositories` | Raises `NotImplementedError` |

`GitHubClient` accepts optional `GitHubAuth`. Public interface matches the future HTTP implementation.

---

## Auth

| Capability | Status |
|------------|--------|
| Injected token | Yes |
| `GITHUB_TOKEN` environment resolution | Yes |
| Unauthenticated mode (`None`) | Yes |
| `Authorization: Bearer …` header | Yes |
| Default GitHub API headers | Yes |
| Token masking (`mask_token`, `masked_token`, safe `__repr__`) | Yes |
| No token logging | Yes |

---

## Mapper

| Method | Phase 1.1 behavior |
|--------|-------------------|
| `parse_full_name(full_name)` | Implemented — trivial `owner/repo` split |
| `repository_html_url(repository)` | Implemented — direct field access |
| `repository_to_candidate(repository)` | Raises `NotImplementedError` |
| `search_item_to_candidate(item)` | Raises `NotImplementedError` |
| `readme_to_evidence_fields(readme)` | Raises `NotImplementedError` |

---

## Exception Hierarchy

```text
GitHubProviderError
├── GitHubAuthenticationError
├── GitHubRateLimitError
├── GitHubNotFoundError
├── GitHubApiError
└── GitHubTimeoutError
```

Exceptions are provider-internal. Future adapters must translate them to port outcomes before crossing the Discovery boundary.

---

## Future Extension Points

| Extension | Location |
|-----------|----------|
| HTTP transport | `client.py` — sole REST knowledge |
| Retry/backoff policy | `client.py` (adapter-owned) |
| Collection provider | `collection.py` implementing `CollectionProvider` |
| Evidence provider | `evidence.py` |
| Verification provider | `verification.py` |
| Ranking provider | `ranking.py` |
| Canonical mapping | `mapper.py` method implementations |
| Composition root registration | Hydra / app wiring (unchanged in this phase) |

---

## Test Results

```text
pixi run test tests/test_github_models.py tests/test_github_mapper.py tests/test_github_client.py
300 passed in 10.44s
```

New tests: **27**

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_github_models.py` | 7 | DTO construction, defaults, frozen, JSON round-trip |
| `tests/test_github_mapper.py` | 7 | Construction, helpers, `NotImplementedError` stubs |
| `tests/test_github_client.py` | 13 | Auth resolution, headers, masking, client interface, exceptions |

No networking during tests.

---

## Remaining Work

| Item | Phase |
|------|-------|
| HTTP transport in `GitHubClient` | Phase 1.2 |
| `GitHubMapper` canonical mappings | Collection Provider phase |
| `collection.py` — `CollectionProvider` adapter | Next |
| `evidence.py`, `verification.py` | Phase 2 |
| `ranking.py` | Phase 3 |
| Composition root provider registration | With Collection Provider |
| Recorded HTTP fixture tests | With HTTP implementation |

---

## Verdict

**Ready for GitHub Collection Provider**

GitHub Provider foundation is in place behind Ports & Adapters boundaries. DTOs, auth, client interface, mapper stubs, and exception hierarchy are complete with no HTTP, no workflow changes, and no Discovery service modifications.
