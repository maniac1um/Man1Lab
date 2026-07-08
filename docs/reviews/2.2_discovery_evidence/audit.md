# Discovery Evidence Audit — Phase 2.2

**Date:** 2026-07-02  
**Scope:** EvidenceService + EmbeddedEvidenceProvider  
**Verdict:** **Ready for Verification Foundation**

---

## Architecture

```text
PaperReproductionAnalysis
        │
        ▼
DiscoveryWorkflow
        │
        ├── CollectionService → CandidateCollectionResult
        │
        ▼
EvidenceService                         ← Discovery evidence entry point
        │
        ├── [1] EmbeddedEvidenceProvider
        ├── [2] NoOpEvidenceProvider
        ├── (future) GitHubMetadataProvider
        ├── (future) OpenAlexEvidenceProvider
        └── (future) HuggingFaceEvidenceProvider
        │
        ▼ merge + deduplicate
EvidenceProviderResult
        │
        ▼
Verification (unchanged skeleton)
        │
        ▼
ResearchResourceDiscovery
```

---

## Modified Files

| File | Change |
|------|--------|
| `discovery/workflow.py` | Uses `EvidenceService` instead of `EvidenceProvider` |
| `ports/evidence_provider.py` | Added `analysis` parameter to port contract |
| `models/research_resource_discovery.py` | Added `EvidenceType.EMBEDDED_REFERENCE` |
| `providers/noop/evidence.py` | Re-exports from `noop_evidence_provider.py` |
| `providers/__init__.py` | Exports `EmbeddedEvidenceProvider` |
| `tests/test_discovery_collection.py` | Workflow uses `EvidenceService` |
| `tests/test_research_resource_discovery.py` | Updated evidence call signature + service wiring |

## New Files

| File | Purpose |
|------|---------|
| `services/discovery/evidence_service.py` | Evidence provider orchestration |
| `services/discovery/evidence_merge.py` | Evidence dedup + provenance merge |
| `providers/embedded/embedded_evidence_provider.py` | Deterministic paper-embedded evidence |
| `providers/noop/noop_evidence_provider.py` | No-op evidence adapter |
| `tests/test_discovery_evidence.py` | Evidence layer tests (9 tests) |

---

## EvidenceService Design

| Responsibility | Owner |
|----------------|-------|
| Provider ordering | `EvidenceService` constructor / `default()` |
| Invoke providers sequentially | `EvidenceService.collect()` |
| Merge evidence records | `evidence_merge.merge_evidence()` |
| Aggregate `provider_outcomes` | `EvidenceService.collect()` |

Default provider order (not in workflow):

1. `EmbeddedEvidenceProvider`
2. `NoOpEvidenceProvider`

```python
EvidenceService.default().collect(analysis, collection_result)
```

---

## Merge Policy

Documented in `services/discovery/evidence_merge.py`:

| Rule | Behavior |
|------|----------|
| Dedup key | `(candidate_id, evidence_type, normalized_url, source_query)` |
| On duplicate | Keep first `evidence_id` |
| Provenance | Append `merged duplicate from <provider>` to `raw_reference` |
| Extensions | Union `observed_fact.extensions` |
| Discard policy | **Never** discard unique evidence |

Evidence is **append-only** across providers.

---

## EmbeddedEvidenceProvider

| Property | Value |
|----------|-------|
| Source | `EvidenceSourceKind.PAPER_TEXT` |
| Type | `EvidenceType.EMBEDDED_REFERENCE` |
| Confidence | `1.0` |
| Polarity | `supports` |

Creates evidence **only** when candidate URL matches an explicit analysis URL:

- `resources.external_resources[].url`
- `resources.datasets[].link`
- `resources.artifacts[].location` (HTTP only)

No inference. No network. No search.

---

## Workflow Changes

| Before | After |
|--------|-------|
| `evidence_provider=NoOpEvidenceProvider()` | `evidence_service=EvidenceService.default()` |
| `evidence_provider.collect(collection, candidates)` | `evidence_service.collect(analysis, collection)` |

Verification, Ranking, Selection: **unchanged**.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| Workflow knows only EvidenceService | **Yes** |
| Workflow does not know providers | **Yes** |
| Providers do not know workflow | **Yes** |
| No HTTP / SDK / GitHub / GraphQL | **Yes** |
| Analysis immutable | **Yes** |
| Evidence append-only | **Yes** |
| WorkflowOrchestrator unchanged | **Yes** |

---

## Dependency Audit

| Module | Imports providers? |
|--------|-------------------|
| `discovery/workflow.py` | **No** — only `EvidenceService` |
| `services/discovery/evidence_service.py` | Yes (composition) |
| `providers/embedded/embedded_evidence_provider.py` | No workflow |
| `agents/*`, `workflow/orchestrator.py` | No discovery evidence imports |

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| VerificationService (mirror Collection/Evidence pattern) | Verification Foundation |
| GitHub / OpenAlex / HuggingFace evidence providers | External Provider Integration |
| Evidence for provider-discovered (non-embedded) candidates | With external providers |
| Hydra-configurable evidence provider list | Optional |

---

## Test Results

```text
pixi run test
200 passed in 9.78s
```

New coverage (`tests/test_discovery_evidence.py`):

- Embedded reference evidence extraction
- Skip candidates without analysis URL match
- Evidence merge preserves first ID + provenance
- Append-only merge behavior
- Provider ordering
- EvidenceService merge across default providers
- Workflow end-to-end with embedded evidence
- Empty evidence when no candidates

---

## Architecture Compliance

| Principle | Compliant |
|-----------|-----------|
| EvidenceService owns orchestration | **Yes** |
| Workflow provider-agnostic | **Yes** |
| Mirrors CollectionService pattern | **Yes** |
| Deterministic embedded evidence | **Yes** |
| Future providers plug into EvidenceService | **Yes** |

---

## Verdict

**Ready for Verification Foundation**

The Discovery evidence entry architecture is established. External evidence providers can register in `EvidenceService` without modifying `DiscoveryWorkflow`.
