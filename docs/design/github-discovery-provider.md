# GitHub Discovery Provider — Architecture Design

**Project:** Man1Lab  
**Phase:** v1.2 — GitHub Discovery Provider Phase 0 (Foundation)  
**Version:** Architecture draft  
**Status:** Design Only — no implementation  
**Audience:** Provider implementers, architects  
**Last updated:** 2026-07-03

Related documents:

- [ADR-0016](../adr/ADR-0016-GitHub-Discovery-Provider.md) — adoption decision
- [ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md) — Discovery capability boundary
- [research-resource-discovery-workflow.md](research-resource-discovery-workflow.md) — workflow and provider priority
- [research-resource-discovery-schema.md](research-resource-discovery-schema.md) — canonical artifact
- [infrastructure.md](../architecture/infrastructure.md) — adoption governance

This document defines the **GitHub Provider architecture** — package layout, module responsibilities, port boundaries, and phase-scoped capabilities. Phase 0 establishes foundation only: **no HTTP, no GitHub API calls, no workflow changes**.

---

## 1. Executive Summary

GitHub is Man1Lab's **first official external Discovery Provider**. It supplies Collection, Evidence, Verification, and Ranking adapters behind existing Discovery ports. Only the GitHub client layer knows REST; workflow and canonical models remain vendor-agnostic.

```text
Discovery Workflow
        ↓
CollectionService / EvidenceService / VerificationService / RankingService
        ↓
GitHub*Provider (implements ports)
        ↓
GitHubClient (REST — client.py only)
        ↓
GitHub REST API
```

**Not in scope:** clone, checkout, dependencies, training scripts, repository structure analysis, workspace, execution, Repository Understanding.

---

## 2. Platform Context

```text
PaperReproductionAnalysis
        ↓
Discovery Workflow (native — unchanged)
        │
        ├── EmbeddedResourceProvider (paper URLs — priority 1)
        ├── GitHubCollectionProvider   (Phase 1+)
        ├── GitHubEvidenceProvider     (Phase 2+)
        ├── GitHubVerificationProvider (Phase 2+)
        └── GitHubRankingProvider      (Phase 3+)
        ↓
ResearchResourceDiscovery
        ↓
Execution Planning
        ↓
Execution (git clone — NOT GitHub Provider)
```

GitHub Provider sits **inside Discovery** as infrastructure adapter. It does not extend to Execution Planning or Repository Understanding.

---

## 3. Package Layout

Suggested layout under repository root:

```text
providers/
    github/
        __init__.py          # Public provider registration helpers
        client.py            # HTTP / REST — sole GitHub API knowledge
        auth.py              # Token resolution and header construction
        models.py            # GitHub DTOs (API response shapes)
        mapper.py            # DTO → Discovery canonical model mapping
        collection.py        # CollectionProvider adapter
        evidence.py          # EvidenceProvider adapter
        verification.py      # VerificationProvider adapter
        ranking.py           # RankingProvider adapter
        exceptions.py        # Provider-scoped error types
```

Existing packages remain unchanged in Phase 0:

```text
providers/embedded/     # Paper-embedded URL provider (priority 1)
providers/noop/         # Test / disable backends
ports/                  # CollectionProvider, EvidenceProvider, …
services/discovery/     # CollectionService, EvidenceService, …
discovery/workflow.py   # Five-stage workflow (no modification)
```

GitHub providers register in composition root alongside embedded/noop — not inside workflow.

---

## 4. Module Responsibilities

### 4.1 `client.py` — HTTP ownership

| Responsibility | Detail |
|----------------|--------|
| Execute GitHub REST requests | GET repository, GET readme, search repositories |
| Return raw response payloads | Passed to `models.py` for parsing |
| Surface transport outcomes | Success, HTTP error, timeout — to callers |
| Retry/backoff | **Adapter-owned** — opaque to workflow ([workflow §8.4](research-resource-discovery-workflow.md)) |

**Only `client.py` may construct REST URLs, set GitHub headers, or parse HTTP status codes.**

Phase 1 REST endpoints (conceptual — not implementation):

| Operation | REST resource |
|-----------|---------------|
| Get repository | `GET /repos/{owner}/{repo}` |
| Get README | `GET /repos/{owner}/{repo}/readme` |
| Search repositories | `GET /search/repositories?q=…` |

### 4.2 `auth.py` — Token ownership

| Responsibility | Detail |
|----------------|--------|
| Resolve `GITHUB_TOKEN` or config-injected token | Via Hydra/settings at composition root ([ADR-0010](../adr/ADR-0010-Hydra-Configuration.md)) |
| Build `Authorization` header | Bearer token for authenticated rate limits |
| Unauthenticated fallback | Document degraded rate limits; never log token |

`auth.py` does not perform HTTP — passes headers to `client.py`.

### 4.3 `models.py` — GitHub DTOs

Internal Data Transfer Objects mirroring GitHub REST JSON — **not** canonical Discovery models.

| DTO (conceptual) | Source |
|------------------|--------|
| `GitHubRepository` | Repository API response |
| `GitHubReadme` | README API response (content, encoding) |
| `GitHubSearchResult` | Search API item |
| `GitHubError` | Error response body |

DTOs stay inside `providers/github/`. They must not leak to workflow, services, or `models/research_resource_discovery.py`.

### 4.4 `mapper.py` — DTO → Canonical

Maps GitHub DTOs to Discovery canonical concepts defined in [research-resource-discovery-schema.md](research-resource-discovery-schema.md):

| Direction | Examples |
|-----------|----------|
| Repository → `RepositoryCandidate` / candidate fields | `url`, `identity.provider_native_id`, `resource_type`, `officiality` |
| Metadata → `EvidenceRecord` | `license_present`, `commit_recency`, `http_status` |
| Checks → verification dimension results | `identity_match`, `repository_health` |
| Signals → ranking factor inputs | `officiality`, `maintenance_signal` |

Mapper is **pure transformation** — no HTTP, no business strategy decisions.

### 4.5 `collection.py` — Candidate discovery

Implements **`CollectionProvider`** port.

| Responsibility | Detail |
|----------------|--------|
| Parse GitHub URLs from analysis | Delegate paper URLs to coordination with embedded provider or dedupe |
| Resolve owner/repo from URL | Via client + mapper |
| Conditional search | **Only when no explicit repository candidate exists** for `code_repository` need |
| Return `CollectionProviderResult` | Candidates + provider_outcomes |

Does not verify, rank, or select.

### 4.6 `evidence.py` — Repository metadata evidence

Implements **`EvidenceProvider`** port.

| Responsibility | Detail |
|----------------|--------|
| Fetch repository metadata | Via client |
| Fetch README content/metadata | Via client |
| Emit `EvidenceRecord` list | Mapped through `mapper.py` |
| Label `evidence_source` | `provider_api`, provider name `github` |

Does not aggregate into pass/fail — Verification stage owns that.

### 4.7 `verification.py` — Repository verification

Implements **`VerificationProvider`** port (or contributes to native verification engine via port).

| Responsibility | Detail |
|----------------|--------|
| Evaluate shallow checks | Exists, accessible, README present, archived, owner match, name similarity |
| Produce verification dimension results | Mapped to schema dimensions |
| Reference evidence IDs | No new evidence creation unless delegated to evidence provider in same pass |

**No cloning. No dependency inspection. No file tree walks.**

### 4.8 `ranking.py` — Rule-based ranking

Implements **`RankingProvider`** port.

| Responsibility | Detail |
|----------------|--------|
| Compute deterministic factor scores | From verification + evidence signals |
| Contribute to `RankList` ordering | Workflow/native ranking engine may merge multi-provider scores |
| **No LLM. No embeddings.** | Rule tables only |

### 4.9 `exceptions.py`

Provider-scoped exceptions — translated to port outcomes (`Failure`, `Timeout`, `ProviderUnavailable`) before crossing port boundary. Workflow never catches GitHub-specific exceptions.

---

## 5. Boundary Architecture

### 5.1 Layer diagram

```text
┌─────────────────────────────────────────────────────────────┐
│  DISCOVERY WORKFLOW + SERVICES (native)                      │
│  discovery/workflow.py                                       │
│  services/discovery/collection_service.py                    │
│  services/discovery/evidence_service.py                      │
│  imports: ports.* only                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ CollectionProvider.collect()
                           │ EvidenceProvider.collect_evidence()
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB PROVIDER ADAPTERS                                    │
│  providers/github/collection.py                              │
│  providers/github/evidence.py                                │
│  providers/github/verification.py                            │
│  providers/github/ranking.py                                 │
│  imports: ports.*, providers/github/client, mapper           │
└──────────────────────────┬──────────────────────────────────┘
                           │ client.get_repository(), …
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB CLIENT + AUTH                                        │
│  providers/github/client.py   ← ONLY REST knowledge          │
│  providers/github/auth.py                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
                    GitHub REST API
```

### 5.2 Import rules

| Module | May import | Must not import |
|--------|------------|-----------------|
| `discovery/workflow.py` | services, ports | `providers.github.*` |
| `services/discovery/*` | ports, models (canonical) | `providers.github.client` |
| `providers/github/collection.py` | ports, mapper, client | workflow, planner, execution_planning |
| `providers/github/client.py` | auth, httpx/requests (future) | discovery.workflow, agents |
| `execution_planning/*` | canonical artifacts | `providers.github.*` |
| `agents/*` | agent domain | `providers.github.*` |

### 5.3 Workflow never imports GitHub SDK

Use **stdlib HTTP or thin httpx** inside `client.py` only — not PyGithub or github-kit in workflow-facing modules. SDK evaluation deferred; REST keeps dependency minimal.

---

## 6. Provider Priority

Aligns with [research-resource-discovery-workflow.md §9.3](research-resource-discovery-workflow.md):

```text
Paper embedded GitHub URLs
        ↓
EmbeddedResourceProvider          ← priority 1 (native seed)
        ↓
GitHubCollectionProvider            ← priority 2 (resolve + enrich same URLs)
        ↓
GitHub Search (REST)                ← priority 3 — ONLY if no explicit repo
        ↓
(other index providers — future)
```

Workflow configures **priority slots** in `CollectionService` provider list order. It does not hardcode "GitHub" — provider registration uses class instances at composition root.

```text
┌──────────────────┐
│ CollectionService │
└────────┬─────────┘
         │ ordered provider list
         ▼
   [Embedded, GitHub, NoOp]
         │
         ▼
   merge_candidates()
```

---

## 7. Capability Scope by Phase

### 7.1 Collection — Phase 1

| In scope | Out of scope |
|----------|--------------|
| Paper-embedded GitHub URL normalization | Non-GitHub URLs |
| `GET /repos/{owner}/{repo}` candidate creation | Clone |
| Repository metadata as candidate fields | File tree listing |
| Search API when **no** explicit repository for `code_repository` need | Search when paper URL already present |
| Deduplication with embedded provider | Inventing URLs |

### 7.2 Evidence — Phase 2

| Signal | Evidence type (schema) |
|--------|------------------------|
| Repository description | `metadata_extract` |
| README body / excerpt | `readme_claim`, `paper_citation_match` |
| License (SPDX from API) | `license_type`, `license_present` |
| Topics | `metadata_extract` |
| Stars, forks | `star_count` (weak signal) |
| Default branch | `metadata_extract` |
| Archived flag | `metadata_extract` |
| Last push date | `commit_recency` |

### 7.3 Verification — Phase 2

| Check | Verification dimension |
|-------|------------------------|
| Repository exists (HTTP 200) | `repository_health` |
| Repository accessible (not 404/451) | `repository_health` |
| README exists | `artifact_availability` |
| Not archived (or flagged partial) | `repository_health`, `scope_alignment` |
| Owner matches paper author | `identity_match` |
| Repository name similarity to paper title | `identity_match` |

No cloning. No `requirements.txt`. No train script detection.

### 7.4 Ranking — Phase 3

Deterministic factor weights (conceptual — implementation tuning later):

| Factor | Direction |
|--------|-----------|
| Paper embedded official URL | Highest |
| Owner match paper author | High |
| README present | Medium |
| Not archived | Medium |
| Recent push activity | Low (tie-break) |
| Stars | Low (tie-break only — never dominant) |

No LLM. No embedding similarity. No learned ranker.

---

## 8. Out of Scope (Explicit)

| Item | Owner |
|------|-------|
| Clone / checkout | Execution ([ADR-0007](../adr/ADR-0007-Execution-Capability.md)) |
| Environment creation | Environment / Execution |
| Dependency inspection | Repository Understanding (future) |
| Training / eval script detection | Repository Understanding (future) |
| Repository structure graph | Repository Understanding (future) |
| Workspace generation | Coder |
| Code generation | Coder |
| Engineering strategy | Execution Planning ([ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md)) |
| Task decomposition | Planner |
| GitHub GraphQL | Phase 4+ evaluation |
| GitHub Actions / Releases API | Future ADR if needed |

---

## 9. Configuration (Composition Root)

Conceptual settings — wired via Hydra, injected into providers:

| Setting | Purpose |
|---------|---------|
| `discovery.github.enabled` | Toggle GitHub providers |
| `discovery.github.token` | API token (secret) |
| `discovery.github.search_enabled` | Allow search fallback |
| `discovery.github.timeout_seconds` | Client timeout |
| `discovery.github.max_retries` | Adapter retry (not workflow) |

Workflow and services receive configured provider instances — they do not read env vars directly.

---

## 10. Error Handling

GitHub Provider translates errors to port outcomes before returning to services:

| GitHub condition | Port outcome |
|------------------|--------------|
| HTTP 200 | Success |
| HTTP 404 | Failure (repo not found) — evidence/verification may record |
| HTTP 403 / rate limit | Timeout or ProviderUnavailable after adapter retry |
| Network error | Timeout |
| Invalid token | ProviderUnavailable + degradation note |

Workflow records outcome in `provenance.providers_used` — same pattern as [research-resource-discovery-workflow.md §8.4](research-resource-discovery-workflow.md).

---

## 11. Testing Strategy (Future Implementation)

| Layer | Approach |
|-------|----------|
| `mapper.py` | Unit tests with fixture JSON — no network |
| `collection.py` / `evidence.py` | Mock `GitHubClient` |
| `client.py` | Recorded HTTP fixtures (vcr/pytest-httpx) — optional live integration job |
| Workflow integration | Existing discovery tests + GitHub provider registered with mock client |

Phase 0 defines strategy only — no test code.

---

## 12. Future Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| **0** (now) | ADR-0016 + this document |
| **1** | `client.py`, `auth.py`, `models.py`, `mapper.py`, `collection.py` + unit tests |
| **2** | `evidence.py`, `verification.py` + service wiring |
| **3** | `ranking.py` + end-to-end discovery fixture tests |
| **4** | Search tuning, caching, rate-limit observability |
| **5** | GraphQL spike ADR if REST round-trips insufficient |

Each phase adds code behind ports — **no Discovery Workflow stage changes**.

---

# GitHub Provider Foundation Audit

### ADR summary

| Item | Status |
|------|--------|
| [ADR-0016](../adr/ADR-0016-GitHub-Discovery-Provider.md) created | ✅ |
| GitHub Discovery-only; clone rejected | ✅ |
| REST first; GraphQL deferred | ✅ |
| Provider pattern; workflow unchanged | ✅ |

### Architecture

| Check | Result |
|-------|--------|
| Aligns with ADR-0013 five-stage Discovery | ✅ |
| Aligns with CollectionService / port pattern in codebase | ✅ |
| Execution Planning / Repository Understanding excluded | ✅ |

### Boundary verification

| Check | Result |
|-------|--------|
| Only `client.py` knows REST | ✅ |
| Workflow never imports GitHub | ✅ |
| GitHub Provider never imports Workflow / Planner / Execution Planning / Coder | ✅ |
| DTOs isolated in `models.py` | ✅ |
| Canonical mapping only via `mapper.py` | ✅ |

### Package structure

| Module | Responsibility documented |
|--------|---------------------------|
| `client.py` | ✅ HTTP |
| `auth.py` | ✅ Tokens |
| `models.py` | ✅ DTOs |
| `mapper.py` | ✅ Canonical mapping |
| `collection.py` | ✅ Collection port |
| `evidence.py` | ✅ Evidence port |
| `verification.py` | ✅ Verification port |
| `ranking.py` | ✅ Ranking port |
| `exceptions.py` | ✅ Error translation |

### Capability scope

| Stage | Phase | Scope documented |
|-------|-------|------------------|
| Collection | 1 | ✅ URLs + conditional search |
| Evidence | 2 | ✅ Metadata + README + license + activity |
| Verification | 2 | ✅ Shallow checks, no clone |
| Ranking | 3 | ✅ Deterministic rules, no LLM |

### Future implementation phases

| Phase | Recorded |
|-------|----------|
| 0–5 roadmap | ✅ §12 |
| Hydra config | ✅ §9 |
| Testing strategy | ✅ §11 |

### Potential risks

| Risk | Mitigation |
|------|------------|
| GitHub rate limits | Token via auth; adapter retry; degradation notes |
| Search false positives | Search only without explicit URL; deterministic ranking; evidence trail |
| REST round-trip cost | Phase 4 caching; future GraphQL ADR |
| Owner/name collision | Verification identity_match + ranking tie-breakers |
| Token leakage | auth.py only; secrets via Hydra; never log token |
| Scope creep into clone/structure | Explicit out-of-scope §8; ADR-0013 boundary |
| Provider leakage into workflow | Import rules §5.2; port outcomes only |

---

## Verdict

**Ready for GitHub Provider Coding**

Phase 0 foundation architecture complete. Implementation may begin with Phase 1 (`client`, `auth`, `models`, `mapper`, `collection`) behind existing `CollectionProvider` port without workflow modification.

---

## Document Maintenance

| Event | Action |
|-------|--------|
| Phase 1 implementation starts | Mark ADR-0016 Accepted when merged |
| GraphQL adoption | New ADR or ADR-0016 amendment |
| HuggingFace provider | Mirror package layout; update infrastructure matrix |
| Workflow change required | Reject — provider must adapt to ports |

**Status:** Design Only — Phase 0 foundation complete. No HTTP. No code.
