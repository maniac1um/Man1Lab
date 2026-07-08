# Discovery Verification Audit — Phase 2.3

**Date:** 2026-07-02  
**Scope:** VerificationService + EmbeddedVerificationProvider  
**Verdict:** **Ready for Ranking Foundation**

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
        │
        ▼
VerificationService                    ← Discovery verification entry point
        │
        ├── [1] EmbeddedVerificationProvider
        ├── [2] NoOpVerificationProvider
        ├── (future) GitHubVerificationProvider
        ├── (future) HuggingFaceVerificationProvider
        └── (future) LicenseVerificationProvider
        │
        ▼ merge
VerificationProviderResult
        │
        ▼
Ranking → Selection → ResearchResourceDiscovery
```

---

## Modified Files

| File | Change |
|------|--------|
| `discovery/workflow.py` | Uses `VerificationService` instead of `VerificationProvider` |
| `ports/verification_provider.py` | Port accepts `analysis`, `collection_result`, `evidence_result` |
| `providers/noop/verification.py` | Re-exports from `noop_verification_provider.py` |
| `providers/__init__.py` | Exports `EmbeddedVerificationProvider` |
| `tests/test_discovery_collection.py` | Workflow uses `VerificationService` |
| `tests/test_discovery_evidence.py` | Workflow uses `VerificationService` |
| `tests/test_research_resource_discovery.py` | Updated verification wiring + port signature |

## New Files

| File | Purpose |
|------|---------|
| `services/discovery/verification_service.py` | Verification provider orchestration |
| `services/discovery/verification_merge.py` | Verification dedup + provenance merge |
| `providers/embedded/embedded_verification_provider.py` | Deterministic embedded evidence verification |
| `providers/noop/noop_verification_provider.py` | No-op verification adapter |
| `tests/test_discovery_verification.py` | Verification layer tests (9 tests) |

---

## VerificationService Design

| Responsibility | Owner |
|----------------|-------|
| Provider ordering | `VerificationService` constructor / `default()` |
| Invoke providers sequentially | `VerificationService.verify()` |
| Merge verification records | `verification_merge.merge_verification()` |
| Aggregate `provider_outcomes` | `VerificationService.verify()` |

Default provider order:

1. `EmbeddedVerificationProvider`
2. `NoOpVerificationProvider`

```python
VerificationService.default().verify(analysis, collection_result, evidence_result)
```

---

## Verification Merge Strategy

Documented in `services/discovery/verification_merge.py`:

| Rule | Behavior |
|------|----------|
| Dedup key | `candidate_id` (one record per candidate) |
| On duplicate | Keep first `verification_id` |
| Dimensions | Merge by dimension name; union `evidence_ids` |
| Status | Prefer stronger: pass > partial > skipped > fail > error |
| Blocking failures | Union without duplicates |
| Discard policy | **Never** discard records for distinct candidates |

---

## EmbeddedVerificationProvider

Deterministic checks using **existing embedded evidence only**:

| Check | Outcome |
|-------|---------|
| Embedded evidence present | Evaluate URL consistency + source_query completeness |
| URL matches candidate | `paper_match` + `identity_match` dimensions |
| Complete paper reference | `VerificationStatus.PASS`, confidence `1.0` |
| No embedded evidence | `SKIPPED` with `insufficient_evidence` |
| URL mismatch | `FAIL` with blocking failure |

Stored in dimension `details`:

- `verification_reason`
- `confidence`

No networking. No new candidates. No new evidence collection.

---

## Workflow Changes

| Before | After |
|--------|-------|
| `verification_provider=NoOpVerificationProvider()` | `verification_service=VerificationService.default()` |
| `verify(evidence, candidates, records)` | `verify(analysis, collection, evidence)` |

Ranking and Selection: **unchanged**.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| Workflow knows only VerificationService | **Yes** |
| Workflow does not know providers | **Yes** |
| Providers do not know workflow | **Yes** |
| No HTTP / GitHub / SDK / GraphQL | **Yes** |
| Verification consumes existing evidence only | **Yes** |
| Verification never generates candidates | **Yes** |
| Verification never collects evidence | **Yes** |
| Analysis immutable | **Yes** |
| Append-only discovery | **Yes** |
| WorkflowOrchestrator unchanged | **Yes** |

---

## Dependency Audit

| Module | Imports providers? |
|--------|-------------------|
| `discovery/workflow.py` | **No** — only `VerificationService` |
| `services/discovery/verification_service.py` | Yes (composition) |
| `providers/embedded/embedded_verification_provider.py` | No workflow |
| `agents/*`, `workflow/orchestrator.py` | No discovery verification imports |

Note: `services/verification_service.py` (execution layer) is unrelated to Discovery verification.

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| RankingService (mirror Collection/Evidence/Verification pattern) | Ranking Foundation |
| GitHub / HuggingFace verification providers | External Provider Integration |
| Framework / license / repository-health dimensions with real data | With external providers |
| Hydra-configurable verification provider list | Optional |

---

## Test Results

```text
pixi run test
209 passed in 9.81s
```

New coverage (`tests/test_discovery_verification.py`):

- Embedded verification PASS with embedded evidence
- SKIPPED when no embedded evidence
- Verification merge preserves first ID
- Append-only merge across candidates
- Provider ordering
- VerificationService default merge
- Workflow end-to-end with verification records
- Empty verification when no candidates
- NoOp-only service returns empty

---

## Architecture Compliance

| Principle | Compliant |
|-----------|-----------|
| VerificationService owns orchestration | **Yes** |
| Workflow provider-agnostic | **Yes** |
| Mirrors Collection/Evidence service pattern | **Yes** |
| Deterministic embedded verification | **Yes** |
| Future providers plug into VerificationService | **Yes** |

---

## Verdict

**Ready for Ranking Foundation**

The third Discovery platform capability is complete. The pipeline successfully executes:

```text
PaperReproductionAnalysis → CollectionService → EvidenceService → VerificationService → ResearchResourceDiscovery
```

without external APIs. Verification relies only on deterministic evidence already inside the Discovery platform.
