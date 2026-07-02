# Discovery Collection Audit — Phase 2.1

**Date:** 2026-07-02  
**Scope:** CollectionService + EmbeddedResourceProvider  
**Verdict:** **Ready for External Provider Integration**

---

## Modified Files

| File | Change |
|------|--------|
| `discovery/workflow.py` | `DiscoveryWorkflow` now depends on `CollectionService` instead of `CollectionProvider` |

## New Files

| File | Purpose |
|------|---------|
| `services/discovery/collection_service.py` | Provider orchestration entry point |
| `services/discovery/candidate_merge.py` | URL/identity deduplication + provenance merge |
| `services/discovery/__init__.py` | Package marker |
| `providers/embedded/embedded_resource_provider.py` | Deterministic analysis-embedded extraction |
| `providers/embedded/__init__.py` | Package marker |
| `tests/test_discovery_collection.py` | Collection layer tests (10 tests) |

---

## Architecture Diagram

```text
PaperReproductionAnalysis (read-only)
        │
        ▼
DiscoveryWorkflow
        │
        ▼
CollectionService                    ← Discovery entry point
        │
        ├── [1] EmbeddedResourceProvider   (analysis URLs only)
        ├── [2] NoOpCollectionProvider     (placeholder)
        ├── (future) GitHubSearchProvider
        ├── (future) OpenAlexProvider
        └── (future) HuggingFaceProvider
        │
        ▼ merge + deduplicate
CandidateCollectionResult
        │
        ▼
Evidence / Verification / Ranking / Selection (unchanged)
        │
        ▼
ResearchResourceDiscovery
```

---

## CollectionService Design

| Responsibility | Owner |
|----------------|-------|
| Provider ordering | `CollectionService` constructor / `default()` |
| Invoke all providers sequentially | `CollectionService.collect()` |
| Merge candidates | `candidate_merge.merge_candidates()` |
| Merge resource needs by `need_id` | `CollectionService.collect()` |
| Aggregate `provider_outcomes` | `CollectionService.collect()` |
| Fallback need derivation from analysis gaps | `CollectionService` when no provider returns needs |

Default provider order (not hardcoded in workflow):

1. `EmbeddedResourceProvider`
2. `NoOpCollectionProvider`

---

## Provider Orchestration

```python
CollectionService.default().collect(analysis)
```

Workflow calls only `collection_service.collect(analysis)`.  
Workflow does **not** import `providers.embedded` or `providers.noop`.

---

## Merge Policy

Documented in `services/discovery/candidate_merge.py`:

| Rule | Behavior |
|------|----------|
| Primary dedup key | Normalized URL |
| Secondary dedup key | `(provider, provider_native_id)` |
| On duplicate | Keep first `candidate_id` |
| Provenance | Append `merged duplicate from <provider>` to `notes` |
| Related IDs | Union `related_candidate_ids` |
| Needs | Union `addresses_needs` |
| Discard policy | **Never** discard candidates |

URL normalization strips `utm_*`, `fbclid`, `gclid`, `ref` query params and normalizes host casing.

---

## Workflow Changes

| Before | After |
|--------|-------|
| `DiscoveryWorkflow(collection_provider=...)` | `DiscoveryWorkflow(collection_service=...)` |
| `collection_provider.collect(analysis)` | `collection_service.collect(analysis)` |

Evidence, Verification, Ranking, Selection stages: **unchanged**.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| Workflow does not know GitHub/providers | **Yes** |
| Workflow calls CollectionService only | **Yes** |
| EmbeddedResourceProvider no network | **Yes** |
| EmbeddedResourceProvider no inference | **Yes** — only explicit URLs in analysis |
| Analysis immutable | **Yes** |
| Append-only discovery | **Yes** |
| WorkflowOrchestrator unchanged | **Yes** |
| Ports & Adapters intact | **Yes** |

---

## Dependency Audit

| Module | Imports providers? | Imports workflow? |
|--------|-------------------|-------------------|
| `discovery/workflow.py` | **No** — only `CollectionService` | — |
| `services/discovery/collection_service.py` | Yes (composition root for collection) | No |
| `providers/embedded/*` | No | No |
| `agents/*` | No discovery imports | No |
| `workflow/orchestrator.py` | No | No |

---

## EmbeddedResourceProvider Extraction

| Analysis source | Candidate type |
|-----------------|----------------|
| `resources.external_resources[].url` | Mapped `ResourceType` from `resource_type` field |
| `resources.datasets[].link` | `dataset_portal` |
| `resources.artifacts[].location` (HTTP only) | `checkpoint` / `configuration` / etc. |

Skipped when URL is empty. No URL construction. No external search.

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| GitHub / OpenAlex / HuggingFace collection providers | External Provider Integration |
| Provider outcome record from NoOp (optional audit) | Minor |
| Ranking/selection logic for embedded candidates | Phase 2.2+ |
| Platform pipeline hook after Analysis | Phase 2+ |
| Wire CollectionService provider list via Hydra config | Optional |

---

## Test Results

```text
pixi run test
191 passed in 9.53s
```

New coverage (`tests/test_discovery_collection.py`):

- Embedded URL extraction (repo, dataset, checkpoint)
- Skip entries without URLs
- GitHub identity from embedded URL
- URL deduplication + provenance notes
- URL normalization (tracking params)
- Provider ordering
- CollectionService merge across default providers
- Need derivation fallback
- Workflow end-to-end with embedded resources
- Empty analysis path

---

## Architecture Compliance

| Principle | Compliant |
|-----------|-----------|
| CollectionService owns orchestration | **Yes** |
| Workflow provider-agnostic | **Yes** |
| Deterministic embedded extraction | **Yes** |
| No HTTP / SDK / external APIs | **Yes** |
| Future providers plug into CollectionService | **Yes** — no workflow changes required |

---

## Verdict

**Ready for External Provider Integration**

The permanent Discovery collection entry architecture is established. External providers (GitHub, OpenAlex, HuggingFace) can be registered in `CollectionService` after `EmbeddedResourceProvider` without modifying `DiscoveryWorkflow`.
