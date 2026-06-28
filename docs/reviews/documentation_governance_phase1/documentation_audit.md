# Documentation Audit — Phase 1

**Audit date:** 2026-06-28  
**Scope:** All project documentation under `docs/`, root-level doc pointers, and cross-references from `README.md` / `DEVELOPMENT.md`  
**Method:** Full tree inventory, content sampling, cross-document comparison, navigation trace from entry points  
**Constraint:** Documentation governance only — no production code reviewed for implementation accuracy beyond what docs claim

---

## 1. Current Documentation Inventory

### 1.1 Root-level documents

| Path | Role | Approx. lines | Lifecycle (observed) |
|------|------|---------------|----------------------|
| `README.md` | Project overview, quick run, doc links | 90 | **Outdated** — describes Reviewer as planned |
| `DEVELOPMENT.md` | Engineering workflow, freeze policy, commit rules | 261 | **Partially outdated** — M6 listed as next |
| `ARCHITECTURE.md` | Pointer to canonical architecture | 8 | **Active** — redirect stub |

### 1.2 `docs/` top level

| Path | Role | Lifecycle |
|------|------|-----------|
| `docs/README.md` | Documentation index | **Active** — missing integration docs and status entry points |
| `docs/architecture/ARCHITECTURE.md` | Canonical system architecture | **Frozen but stale** — Reviewer marked Planned; no Verification stage |
| `docs/architecture/CAPABILITIES.md` | Capability status summary | **Frozen but stale** — frozen at M5.F; Reviewer Planned |
| `docs/roadmap/ROADMAP.md` | Long-term milestone timeline | **Stale** — M6 Next, M7 Planned; M6.x/M7.1 not reflected |
| `docs/roadmap/MILESTONES.md` | Milestone workflow and specs | **Stale** — M6 Next; no M6.1–M6.3 or integration milestones |
| `docs/adr/README.md` + ADR-0001–0007 | Architecture decisions | **Active / Frozen** — index current through ADR-0007 |
| `docs/reviews/README.md` | Review directory guide | **Obsolete** — claims no review subdirectories exist |
| `docs/notes/README.md` | Informal notes placeholder | **Active** — empty directory |
| `docs/api/README.md` | Future API reference placeholder | **Active** — intentionally empty |

### 1.3 `docs/reviews/` — milestone design reviews (16 files)

| Directory | Files | Type |
|-----------|-------|------|
| `M4.1/` | `design_review.md`, `cursor_report.md` | Milestone design review |
| `M4.2/` | `design_review.md` | Milestone design review |
| `M4.3/` | `design_review.md` | Milestone design review |
| `M5.1/` | `design_review.md` | Milestone design review |
| `M5.1.1/` | `design_review.md` | Milestone design review |
| `M5.2/` | `design_review.md` | Milestone design review |
| `M5.F/` | `design_review.md` | Capability-freeze governance review |
| `M6.1/` | `design_review.md` | Milestone design review (Verification) |
| `M6.2/` | `design_review.md` | Milestone design review (LLM Review) |
| `M6.3/` | `design_review.md` | Milestone design review (Patch Planning) |
| `M7.1/` | `integration_report.md` | Integration validation report |

### 1.4 `docs/reviews/` — integration fix cycle (4 files)

| Directory | Files | Type |
|-----------|-------|------|
| `integration_fix_01/` | `failure_analysis.md` | Post-integration failure analysis |
| `integration_fix_02/` | `design_review.md`, `validation_report.md` | Integration fix design + validation |

### 1.5 `docs/reviews/documentation_governance_phase1/` (this audit)

| File | Type |
|------|------|
| `documentation_audit.md` | Governance audit (this document) |
| `restructuring_plan.md` | Proposed hierarchy (pending) |
| `migration_checklist.md` | Migration steps (pending) |

### 1.6 Related documentation outside `docs/` (reference only)

| Path | Notes |
|------|-------|
| `prompts/**/*.md` | Prompt resources — out of scope for restructure; do not move |
| `outputs/report.md` | Runtime artifact — not project documentation |
| `.env.example` | Configuration reference — linked from root README |

### 1.7 Missing documents (requested by governance goals)

| Document | Status |
|----------|--------|
| `GETTING_STARTED.md` | **Missing** |
| `CURRENT_STATUS.md` | **Missing** |
| Single integration index | **Missing** |
| Reviews master index listing all 11 review areas | **Missing** (README is wrong) |

**Total markdown in `docs/`:** 31 files (excluding this phase deliverables until written)

---

## 2. Duplicated Content

### 2.1 High duplication (same information, multiple sources of truth)

| Topic | Locations | Risk |
|-------|-----------|------|
| **Project purpose & pipeline** | `README.md`, `docs/architecture/ARCHITECTURE.md` §1–4, `docs/architecture/CAPABILITIES.md` | Divergent pipeline diagrams; README omits Verification |
| **How to run / test** | `README.md` §Running, `DEVELOPMENT.md` §Running the Project | Near-identical commands duplicated |
| **Capability status** | `README.md`, `CAPABILITIES.md`, `ARCHITECTURE.md` §3.1, `ROADMAP.md`, `MILESTONES.md` | **Five sources**; three are stale |
| **Frozen interfaces** | `DEVELOPMENT.md` §Architecture Freeze, `ARCHITECTURE.md`, ADRs | Acceptable overlap if cross-linked; ADRs should remain authoritative |
| **Repository layout** | `README.md`, `DEVELOPMENT.md`, `ARCHITECTURE.md` | Minor duplication |
| **M4.1 workspace construction** | `M4.1/design_review.md`, `M4.1/cursor_report.md` | **Near-duplicate** — cursor report is shorter early draft of same milestone |

### 2.2 Acceptable duplication (by design)

| Pattern | Rationale |
|---------|-----------|
| Root `ARCHITECTURE.md` → `docs/architecture/ARCHITECTURE.md` | Intentional pointer pattern |
| ADR summary in `adr/README.md` + full ADR body | Index vs record |
| Design review referencing ADR by link | Correct — not content duplication |

### 2.3 Duplication to eliminate (recommendation)

| Action | Target |
|--------|--------|
| Consolidate status into `CURRENT_STATUS.md` | Remove repeated status tables from README where possible — link instead |
| Mark `M4.1/cursor_report.md` as Historical | Do not delete; stop linking from indexes |
| Single canonical pipeline diagram | `ARCHITECTURE.md` only; others link |

---

## 3. Outdated Documents

Documents whose **observable claims** conflict with the current codebase and latest integration run (2026-06-28, DeepSeek API, `integration_fix_02` validation):

| Document | Stale claim | Current observable state |
|----------|-------------|--------------------------|
| `README.md` | Reviewer "(planned)"; Reporter partial only | Reviewer, VerificationService, PatchPlanner implemented (M6.1–M6.3) |
| `README.md` | Pipeline ends at Runner → Reviewer (planned) | Orchestrator runs Verification → Reviewer → PatchPlanner → Reporter |
| `docs/architecture/CAPABILITIES.md` | "As of M5.F"; Reviewer Planned | M6.x complete; Reviewer uses LLM + verification |
| `docs/architecture/CAPABILITIES.md` | Reviewer input `ExecutionResult` only | Reviewer consumes `PaperModel`, `TaskModel`, `VerificationResult` (per M6.2 review) |
| `docs/architecture/ARCHITECTURE.md` | Reviewer (Planned) in pipeline diagrams | Reviewer stage runs; stub behavior replaced |
| `docs/architecture/ARCHITECTURE.md` | No VerificationService | `VerificationService` exists (M6.1) |
| `docs/roadmap/ROADMAP.md` | M6 Status: Next | M6.1–M6.3 design reviews exist; M6 capability largely implemented |
| `docs/roadmap/ROADMAP.md` | M7 Planned | M7.1 integration report exists |
| `docs/roadmap/MILESTONES.md` | M6 — Next | Same as above |
| `DEVELOPMENT.md` | "Reviewer is the next capability milestone (M6)" | Superseded by M6 delivery |
| `docs/reviews/README.md` | "No milestone review subdirectories exist yet" | 11 milestone/integration subdirectories exist |
| `M4.3/design_review.md` | README not updated after population | Fixed by integration_fix_02 — doc now historical for that limitation |
| `M7.1/integration_report.md` | Mock LLM run characterization | Superseded by later real-LLM runs; report is **Historical** for first mock run |

**Note:** Stale status does not invalidate historical design reviews. Those documents describe state **at milestone completion** and should be classified **Frozen / Historical**, not rewritten in Phase 1.

---

## 4. Missing Navigation

### 4.1 Broken or absent paths from entry points

| Starting point | Gap |
|----------------|-----|
| `docs/README.md` | No links to `integration_fix_*`, `M7.1`, `M6.x` reviews |
| `docs/README.md` | No `GETTING_STARTED.md` or `CURRENT_STATUS.md` |
| `docs/reviews/README.md` | Incorrect current state; no file index |
| `README.md` | No link to reviews, integration reports, or current status |
| `DEVELOPMENT.md` | No integration-fix workflow documentation |
| `ROADMAP.md` | No pointer to integration validation track parallel to milestones |

### 4.2 No single "read first" path for new contributors

A new contributor landing on `README.md` sees an outdated pipeline and cannot discover:

- What integration work is in progress (`integration_fix_02` validation: Partially Fixed)
- Where failure analyses live (`integration_fix_01`)
- That M6.x sub-milestones exist as separate reviews
- Which architecture doc sections are stale

### 4.3 Orphaned or weakly linked documents

| Document | Issue |
|----------|-------|
| `integration_fix_01/failure_analysis.md` | Only linked from fix_02 docs |
| `integration_fix_02/validation_report.md` | Not in any index |
| `M4.1/cursor_report.md` | Not in `docs/README.md`; duplicates design_review |
| `documentation_governance_phase1/*` | New; needs index entry after migration |

---

## 5. Inconsistent Terminology

### 5.1 Milestone naming

| Pattern | Usage | Example |
|---------|-------|---------|
| `M{n}` | ROADMAP top-level phases | M6, M7, M8 |
| `M{n}.{m}` | Review subdirectories | M6.1, M6.2, M4.3 |
| `M{n}.F` | Freeze milestone | M5.F |
| `M{n}.{m}.{k}` | Rare variant | M5.1.1 |
| `Phase N` | ROADMAP section headers | "Phase 3 — Coder Capability" maps to M4.x |
| `integration_fix_{nn}` | Product integration fixes | Not in ROADMAP |
| `M7.1` | Integration validation milestone | Naming mixes M-prefix with integration semantics |

**Impact:** Contributors cannot infer ordering between `M6.3`, `M7.1`, and `integration_fix_02`.

### 5.2 Document type naming

| Term used | Meaning varies |
|-----------|----------------|
| Design Review | Milestone implementation report |
| Integration Report | End-to-end pipeline validation (M7.1) |
| Failure Analysis | Post-run defect catalog (fix_01) |
| Validation Report | Post-fix engineering validation (fix_02) |
| cursor_report | Ad-hoc agent-assisted review (M4.1 only) |

No glossary or `reviews/README.md` taxonomy covers integration fix documents.

### 5.3 Capability vs agent vs service

| Term | Inconsistent usage |
|------|-------------------|
| Reviewer | Sometimes agent only; sometimes includes VerificationService + PatchPlanner |
| Runner | Agent vs EnvironmentService + ExecutionService |
| Capability freeze (M5.F) | vs Architecture freeze (DEVELOPMENT.md) — related but distinct |

### 5.4 Status vocabulary

| Term | Meaning drift |
|------|---------------|
| Planned / Next / Partial / Implemented | Used inconsistently across README, CAPABILITIES, ROADMAP |
| Complete / Completed / Frozen | Milestone reviews vs roadmap status |

---

## 6. Broken Navigation (link and index audit)

| Link / reference | Issue |
|------------------|-------|
| `docs/reviews/README.md` §Current State | Factually false — misleads onboarding |
| `docs/api/README.md` → reviews for API | Valid but reviews are not API docs — sets wrong expectation |
| `CAPABILITIES.md` → "Next milestone M6" | Incorrect navigation for current work |
| No redirect from old mental model "M6 next" | Contributors following DEVELOPMENT.md hit wrong priority |

**Link integrity:** No automated link checker observed. Internal relative links between `docs/` files appear valid when manually traced. Root `ARCHITECTURE.md` pointer works.

---

## 7. Reviews Directory Assessment

### Current flat structure

```text
docs/reviews/
├── README.md                    # obsolete index
├── M4.1/ … M6.3/                # milestone design reviews
├── M7.1/                        # integration report
├── integration_fix_01/          # failure analysis
├── integration_fix_02/          # fix design + validation
└── documentation_governance_phase1/
```

### Problems

1. **Three document classes interleaved** without namespace separation: milestone reviews, integration milestones, integration fixes.
2. **No chronological or dependency index** (e.g. fix_02 depends on fix_01).
3. **README describes M2.x layout** that does not exist in the repository.
4. **Governance docs** placed under `reviews/` — acceptable for Phase 1 deliverable; long-term belong under `docs/governance/` or `docs/meta/`.

---

## 8. Recommendations

### Priority 1 — Contributor entry (no content duplication)

1. Add `docs/GETTING_STARTED.md` — orientation only; links to README, DEVELOPMENT, CURRENT_STATUS, ARCHITECTURE.
2. Add `docs/CURRENT_STATUS.md` — single source of truth for implemented capabilities, active integration work, and stale-doc warning.
3. Update `docs/README.md` and root `README.md` to link to both; trim duplicated status from root README.

### Priority 2 — Reviews hierarchy

1. Restructure `docs/reviews/` into `milestones/`, `integration/`, `governance/` (see `restructuring_plan.md`).
2. Replace `docs/reviews/README.md` with an accurate index and document-type glossary.
3. Classify lifecycle on each index entry: Active / Frozen / Historical.

### Priority 3 — Stale canonical docs (content update phase — separate from Phase 1 structure)

1. Update `CAPABILITIES.md`, `ROADMAP.md`, `ARCHITECTURE.md` pipeline sections in a follow-up milestone (not Phase 1 restructure alone).
2. Mark M5.F freeze banner in CAPABILITIES as **Historical context**; add pointer to CURRENT_STATUS.

### Priority 4 — Reduce duplication

1. Stop promoting `M4.1/cursor_report.md` in indexes; retain as Historical.
2. Deduplicate run instructions: canonical in GETTING_STARTED; DEVELOPMENT links to it.

### Priority 5 — Terminology standard

1. Adopt document-type suffix convention in indexes: `design_review.md`, `integration_report.md`, `failure_analysis.md`, `validation_report.md`.
2. Document integration-fix numbering in ROADMAP appendix or CURRENT_STATUS — not as formal milestones unless promoted.

### Priority 6 — Tooling (optional, later)

1. Add a CI markdown link check for `docs/`.
2. Add `lifecycle:` frontmatter to index entries (optional; not required for Phase 1).

---

## 9. Summary Metrics

| Metric | Count |
|--------|-------|
| Total `docs/` markdown files | 31 (+3 this phase) |
| Outdated canonical docs (README, CAPABILITIES, ROADMAP, ARCHITECTURE, DEVELOPMENT) | 6 |
| Obsolete index files | 1 (`reviews/README.md`) |
| Near-duplicate review files | 1 pair (`M4.1/cursor_report` + `design_review`) |
| Missing entry-point docs | 2 (`GETTING_STARTED`, `CURRENT_STATUS`) |
| Integration docs not in main index | 4 files across 3 directories |
| ADRs current | 7 / 7 indexed |

---

## 10. Audit Conclusion

Documentation **content quality at milestone boundaries is strong** — design reviews are detailed and factual for their time. **Governance and navigation are weak** — multiple stale canonical summaries, no current-status single source of truth, and an incorrect reviews index. Integration work (M7.1, fix_01, fix_02) is poorly discoverable from entry points.

Phase 1 should prioritize **navigation and lifecycle classification** over writing new architectural content. Canonical doc content updates should follow in Phase 2 after `CURRENT_STATUS.md` establishes what is true today.
