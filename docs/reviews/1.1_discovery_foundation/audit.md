# Discovery Foundation Audit — Phase 1.1

**Date:** 2026-07-02  
**Scope:** Domain model, validation, workflow skeleton, ports, NoOp providers  
**Verdict:** **Ready for Discovery Provider Integration**

---

## Modified Files

| File | Change |
|------|--------|
| `validation/exceptions.py` | Added `DiscoveryValidationError` |
| `validation/__init__.py` | Exported discovery validation API |

## New Files

| File | Purpose |
|------|---------|
| `models/research_resource_discovery.py` | Canonical Pydantic domain model |
| `validation/research_resource_discovery.py` | Normalize / validate / build |
| `discovery/workflow.py` | `DiscoveryWorkflow` + `ResearchResourceDiscoveryBuilder` |
| `discovery/__init__.py` | Package marker |
| `ports/collection_provider.py` | Collection port |
| `ports/evidence_provider.py` | Evidence port |
| `ports/verification_provider.py` | Verification port |
| `providers/noop/collection.py` | NoOp collection provider |
| `providers/noop/evidence.py` | NoOp evidence provider |
| `providers/noop/verification.py` | NoOp verification provider |
| `providers/noop/__init__.py` | Package marker |
| `providers/__init__.py` | NoOp provider exports |
| `tests/test_research_resource_discovery.py` | Foundation tests |

**Unchanged (per scope):** `WorkflowOrchestrator`, all agents, MLflow, Hydra, Pixi, Analysis logic.

---

## Architecture Diagram

```text
PaperReproductionAnalysis (read-only input)
        ↓
DiscoveryWorkflow
        ├── Stage 1: Candidate Collection  → CollectionProvider (port)
        ├── Stage 2: Evidence Collection   → EvidenceProvider (port)
        ├── Stage 3: Verification          → VerificationProvider (port)
        ├── Stage 4: Ranking               → skeleton (empty)
        ├── Stage 5: Selection             → skeleton (gaps from analysis)
        └── ResearchResourceDiscoveryBuilder
                ↓
        validation.build_research_resource_discovery()
                ↓
        ResearchResourceDiscovery (canonical artifact)
```

```text
Ports & Adapters boundary:

ports/collection_provider.py     ← Protocol
ports/evidence_provider.py     ← Protocol
ports/verification_provider.py ← Protocol
        ↑
providers/noop/*               ← NoOp adapters (Phase 1.1)
providers/github/*               ← NOT IMPLEMENTED (Phase 2+)
```

---

## Implemented Layers

| Layer | Status |
|-------|--------|
| **Domain model** | Complete — all schema modules, enums, `SCHEMA_VERSION = "1.0"` |
| **Validation** | Complete — normalize, validate, build; reference integrity V-01–V-07; metadata counts |
| **Workflow skeleton** | Complete — five fixed stages + builder assembly |
| **Ports** | Complete — Collection, Evidence, Verification protocols |
| **NoOp providers** | Complete — empty results, end-to-end runnable |
| **Tests** | Complete — 9 new tests |

## Unimplemented Layers

| Layer | Phase |
|-------|-------|
| GitHub / OpenAlex / HuggingFace providers | Provider Integration |
| Ranking business logic | Phase 2 |
| Selection business logic | Phase 2 |
| Platform workflow integration (post-Analysis hook) | Phase 2 |
| MLflow nested run for Discovery | Optional Phase 2 |
| HTTP / SDK calls | Explicitly out of scope |

---

## Validation Coverage

| Area | Covered |
|------|---------|
| Schema version | Yes |
| Enum normalization | Yes — all discovery enums |
| Metadata required fields | Yes |
| Candidate uniqueness (V-01) | Yes |
| Evidence → candidate refs (V-02) | Yes |
| Verification → candidate refs (V-03) | Yes |
| Ranking → candidate refs (V-04) | Yes |
| Selection → candidate refs (V-05) | Yes |
| Selection → rank_list refs (V-06) | Yes |
| Selection/evidence ID refs (V-07) | Yes |
| Metadata count alignment (V-16) | Yes |
| Selection verification status (V-11) | Yes |
| Gap ID uniqueness + required description | Yes |

---

## Workflow Coverage

| Stage | Skeleton behavior |
|-------|-------------------|
| Candidate Collection | Delegates to `CollectionProvider` |
| Evidence Collection | Delegates to `EvidenceProvider` |
| Verification | Delegates to `VerificationProvider` |
| Ranking | Returns empty `RankList` per resource need |
| Selection | Returns empty selections; derives `discovery_gaps` from analysis |
| Builder | Assembles + validates canonical artifact |

End-to-end path verified:

```text
PaperReproductionAnalysis → DiscoveryWorkflow (NoOp) → ResearchResourceDiscovery
```

---

## Provider Coverage

| Provider | Port | Implementation |
|----------|------|----------------|
| Collection | `CollectionProvider` | `NoOpCollectionProvider` |
| Evidence | `EvidenceProvider` | `NoOpEvidenceProvider` |
| Verification | `VerificationProvider` | `NoOpVerificationProvider` |

No HTTP. No SDK. No external network.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| `WorkflowOrchestrator` unchanged | **Yes** |
| Agent logic unchanged | **Yes** |
| Analysis immutable | **Yes** — read-only input, content hash snapshot |
| Discovery artifact append-only | **Yes** — model design preserves full candidate set |
| Workflow does not import provider implementations | **Yes** — depends on ports + injected instances |
| Providers do not import workflow | **Yes** |
| Builder has no provider/business logic | **Yes** — assembly + validation only |
| Validation has no business logic | **Yes** — structural rules only |

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `discovery/workflow.py` | `models.*`, `ports.*`, `validation.research_resource_discovery` |
| `providers/noop/*` | `ports.*`, `models.paper_reproduction_analysis` (collection only) |
| `ports/*` | `models.*`, other `ports.*` (evidence/verification) |
| `agents/*` | **No discovery imports** |
| `workflow/orchestrator.py` | **No discovery imports** |

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| Paper-seed collection from `PaperReproductionAnalysis.resources` | Provider Integration |
| Real ranking/selection stages | Phase 2 |
| Wire Discovery into platform pipeline after Analysis | Phase 2 |
| Resource need derivation from analysis gaps | Provider Integration |
| Rank/selection stage provider ports (if needed) | TBD |
| ADR-0013 status → Accepted on merge | Governance |

---

## Test Results

```text
pixi run test
181 passed in 12.59s
```

New tests (`tests/test_research_resource_discovery.py`):

- Domain model + schema version + frozen model
- Validation build, reference integrity, metadata counts
- Builder empty artifact
- Workflow end-to-end with NoOp providers
- Provenance stage timestamps
- NoOp provider empty results

---

## Architecture Compliance

| Principle | Compliant |
|-----------|-----------|
| Ports & Adapters | **Yes** |
| Same organization as Analysis (`models → validation → workflow → ports → providers → tests`) | **Yes** |
| Thin skeleton (no discovery business logic) | **Yes** |
| Canonical schema as source of truth | **Yes** |
| No external provider / networking | **Yes** |

---

## Verdict

**Ready for Discovery Provider Integration**

No blocking issues. Phase 1.1 establishes the canonical Discovery runtime architecture. Next step: implement real `CollectionProvider` adapters (paper-seed, then GitHub/OpenAlex/HuggingFace) without modifying the workflow coordinator contract.
