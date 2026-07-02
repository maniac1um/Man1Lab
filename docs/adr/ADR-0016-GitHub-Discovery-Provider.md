# ADR-0016 — GitHub Discovery Provider

## Status

Draft

## Date

2026-07-03

## Context

Man1Lab v1.2 completed **Discovery foundation** — Collection, Evidence, Verification, Ranking, and Selection workflow stages with native/embedded providers ([ADR-0013](ADR-0013-Research-Resource-Discovery.md)). **Execution Planning foundation** is also complete ([ADR-0014](ADR-0014-Execution-Planning-Capability.md)).

Discovery currently resolves resources using paper-embedded URLs and deterministic native logic. The next milestone is the **first external Discovery backend** for production repository discovery.

For ML reproduction papers, the dominant external engineering artifact is a **GitHub repository** — official code, community reimplementations, and paper-linked project repos. GitHub is the highest-value first provider for the `repository` resource need.

| Requirement | Why GitHub |
|-------------|------------|
| Official implementations | Authors publish code on GitHub |
| Paper-stated URLs | Analysis frequently embeds `github.com` links |
| Metadata for evidence | README, license, topics, activity signals available via API |
| Verification without clone | Repository existence and accessibility checkable remotely |

This ADR adopts GitHub as the **first production Discovery Provider**. Phase 0 establishes **provider foundation architecture only** — no workflow modification, no HTTP implementation, no GitHub API calls in this documentation pass.

### Why GitHub is Discovery-only

Discovery answers: *what external resources exist, what evidence supports them, and which were selected?*

GitHub integration in Discovery is limited to **remote observation** — repository lookup, metadata fetch, shallow verification, deterministic ranking.

**Repository clone is NOT Discovery.** Clone is an **Execution** operation ([ADR-0007](ADR-0007-Execution-Capability.md)). Clone during Discovery would:

- Blur failure attribution between *finding* and *operating* resources
- Add latency and disk cost before strategy is committed
- Violate ADR-0013 capability boundary (Discovery does not clone, install, or execute)
- Conflate Discovery with Repository Understanding (structure inspection requires checkout — future, downstream)

```text
GitHub Provider  →  Discovery  →  Execution Planning  →  Execution (clone here)
```

**Repository Understanding** (semantic mapping of repo structure to analysis modules) is **not** in scope. It runs downstream after Execution Planning commits to a repo-based strategy.

## Decision

Adopt **GitHub REST API** as the first external Discovery Provider backend, integrated via the **Provider pattern** behind existing Discovery ports.

### Provider pattern

External systems integrate as **Discovery Providers** — adapters implementing port contracts defined in `ports/`:

| Port | Discovery stage |
|------|-----------------|
| `CollectionProvider` | Candidate Collection |
| `EvidenceProvider` | Evidence Collection |
| `VerificationProvider` | Verification |
| `RankingProvider` | Ranking |

Discovery Workflow and `CollectionService` depend on **ports and services only**. They never import GitHub SDKs or REST paths.

```text
Discovery Workflow
        ↓
CollectionService / EvidenceService / …
        ↓
GitHubCollectionProvider / GitHubEvidenceProvider / …
        ↓
GitHubClient                    ← sole REST knowledge (client.py)
```

### Why REST API first

| Option | Decision |
|--------|----------|
| **GitHub REST API** | **Adopted (Phase 1)** — stable, well-documented, sufficient for repo metadata, README, search, and verification signals |
| **GitHub GraphQL API** | Deferred — richer queries but higher adoption cost; evaluate in Phase 2+ if REST round-trips become a bottleneck |
| **GitHub CLI (`gh`)** | Rejected — subprocess coupling, environment dependency, poor testability |
| **Unauthenticated scraping** | Rejected — brittle, rate-limited, violates Terms of Service |
| **Direct git clone for metadata** | Rejected — Execution-layer operation; not Discovery |

REST first preserves thin integration, matches Docling/MLflow adapter patterns ([ADR-0008](ADR-0008-Document-Parsing-Docling.md), [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md)), and covers Phase 1 scope without GraphQL schema maintenance.

### Capability boundaries

| GitHub Provider does | GitHub Provider does not |
|---------------------|-------------------------|
| Resolve paper-embedded GitHub URLs to repository candidates | Clone or checkout repositories |
| Fetch repository metadata for evidence | Inspect `requirements.txt`, train scripts, or file trees |
| Shallow verification (exists, accessible, archived, owner match) | Install dependencies or run code |
| Deterministic rule-based ranking signals | LLM ranking or embedding similarity |
| Map GitHub DTOs → Discovery canonical models | Modify Workflow, Planner, Execution Planning, or Coder |
| Retry/backoff inside adapter (opaque to workflow) | Expose GitHub types to workflow or canonical schema |

### Platform placement

```text
PaperReproductionAnalysis
        ↓
Discovery (native workflow + canonical artifact)
        ↑
GitHub Provider (external adapter — Collection, Evidence, Verification, Ranking)
        ↓
ResearchResourceDiscovery
        ↓
Execution Planning
        ↓
Execution (clone — separate concern)
```

GitHub Provider **never** imports Workflow, Planner, Execution Planning, or Implementation layers.

## Alternatives

**No external provider (embedded-only Discovery):** Rejected for production. Paper-embedded URLs alone miss index expansion when papers omit repository links; benchmarks show unresolved `repository` gaps.

**GitHub Search as primary (skip paper URLs):** Rejected. Paper-stated URLs remain priority 1 per [research-resource-discovery-workflow.md](../design/research-resource-discovery-workflow.md). Search API used only when no explicit repository exists.

**Monolithic GitHub module in workflow:** Rejected. Violates ports & adapters; prevents swapping OpenAlex/HuggingFace providers later.

**GitHub in Execution Planning:** Rejected. Execution Planning consumes `ResearchResourceDiscovery`; it does not call GitHub. Strategy decisions operate on canonical artifacts only ([ADR-0014](ADR-0014-Execution-Planning-Capability.md)).

**GitHub GraphQL first:** Rejected for Phase 1. REST covers Phase 1 scope; GraphQL deferred to reduce initial surface area.

## Consequences

**Positive:**

- **First production Discovery backend** — closes repository gap for majority of ML papers
- **Provider template** — GitHub package layout becomes reference for HuggingFace, OpenAlex, Papers with Code
- **Workflow unchanged** — five Discovery stages and coordinator logic stable; only adapter registration changes
- **Thin boundary** — only `client.py` knows REST; mappers isolate DTO leakage
- **Execution Planning ready** — verified repo selections flow to strategy without re-search

**Negative:**

- GitHub API rate limits require token management and adapter retry policy
- REST may require multiple round-trips per repository (metadata + README)
- Search-based discovery quality depends on paper metadata signals (title, authors, arXiv)
- Shallow verification does not guarantee runnable repos — Execution may still fail
- GitHub-centric bias until additional providers ship

## Relationship to Other ADRs

- [ADR-0013](ADR-0013-Research-Resource-Discovery.md): GitHub Provider implements Discovery ports; does not change five-stage workflow or `ResearchResourceDiscovery` schema semantics
- [ADR-0014](ADR-0014-Execution-Planning-Capability.md): Execution Planning consumes discovery output; never calls GitHub Provider
- [ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md): GitHub Provider reads analysis for seeds and match context; never mutates analysis
- [ADR-0007](ADR-0007-Execution-Capability.md): Clone and runtime repo operations remain Execution — not GitHub Provider
- [ADR-0010](ADR-0010-Hydra-Configuration.md): GitHub token and provider priority configured via Hydra — composition root only; provider modules receive config injection
- [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md): Provider outcomes logged via existing Discovery provenance and optional nested MLflow runs — GitHub Provider does not import MLflow

Companion design: [github-discovery-provider.md](../design/github-discovery-provider.md)

## Future Work

| Phase | Scope |
|-------|-------|
| **Phase 0** (this ADR) | Architecture and package layout — no HTTP |
| **Phase 1** | REST client, auth, collection from paper URLs + conditional search |
| **Phase 2** | Evidence + verification providers wired to workflow |
| **Phase 3** | Ranking provider; integration tests with recorded fixtures |
| **Phase 4+** | GraphQL evaluation, caching layer, HuggingFace provider parity |

Out of scope for all GitHub Provider phases: clone, checkout, dependency inspection, Repository Understanding, Repository Adaptation, workspace generation.

---

# ADR-0016 Audit

| Check | Result |
|-------|--------|
| GitHub adopted as first external Discovery Provider | ✅ |
| Discovery-only boundary (no clone) | ✅ |
| REST first documented | ✅ |
| Provider pattern aligned with ADR-0013 | ✅ |
| No workflow modification in this ADR | ✅ |
| Repository Understanding excluded | ✅ |
| Existing ADRs modified | ❌ None |

**Verdict:** Ready for companion capability design ([github-discovery-provider.md](../design/github-discovery-provider.md))
