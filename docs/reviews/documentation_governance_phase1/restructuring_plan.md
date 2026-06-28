# Documentation Restructuring Plan — Phase 1

**Status:** Proposed (not yet executed)  
**Principle:** Improve clarity and discoverability without deleting historical records or modifying production code  
**Architecture:** Frozen — restructure applies to documentation layout only

---

## 1. Design Goals

| Goal | How addressed |
|------|---------------|
| New contributor knows what the project is | `GETTING_STARTED.md` + root README trim |
| What is implemented | `CURRENT_STATUS.md` (single summary) |
| What is in active development | `CURRENT_STATUS.md` §Active Work |
| What to read first | `docs/README.md` → GETTING_STARTED → CURRENT_STATUS → ARCHITECTURE |
| Where decisions live | `docs/adr/` unchanged |
| Historical record preserved | Lifecycle tags; no deletions; redirects in migration checklist |

---

## 2. Proposed Documentation Tree

```text
Research_Agent_MVP/
├── README.md                          # Short project intro; links to docs/GETTING_STARTED.md
├── DEVELOPMENT.md                     # Workflow, freeze, commits (status links to CURRENT_STATUS)
├── ARCHITECTURE.md                    # Pointer only (unchanged pattern)
│
└── docs/
    ├── README.md                      # Master documentation index (expanded)
    ├── GETTING_STARTED.md             # NEW — orientation & first steps
    ├── CURRENT_STATUS.md              # NEW — implementation & integration status
    │
    ├── architecture/
    │   ├── ARCHITECTURE.md            # Frozen canonical architecture (content update Phase 2)
    │   └── CAPABILITIES.md            # Frozen capability reference (content update Phase 2)
    │
    ├── roadmap/
    │   ├── ROADMAP.md                 # Timeline (content update Phase 2)
    │   └── MILESTONES.md              # Workflow spec (content update Phase 2)
    │
    ├── adr/                           # UNCHANGED layout
    │   ├── README.md
    │   └── ADR-0001 … ADR-0007
    │
    ├── reviews/
    │   ├── README.md                  # REWRITTEN — master review index + glossary
    │   │
    │   ├── milestones/                # NEW container — milestone design reviews
    │   │   ├── M4.1/
    │   │   │   ├── design_review.md       [Frozen]
    │   │   │   └── cursor_report.md       [Historical]
    │   │   ├── M4.2/ … M6.3/
    │   │   └── M5.F/
    │   │
    │   ├── integration/               # NEW container — E2E & product fixes
    │   │   ├── README.md                  # Integration track index
    │   │   ├── M7.1/
    │   │   │   └── integration_report.md  [Historical — mock run]
    │   │   ├── fix_01/
    │   │   │   └── failure_analysis.md      [Frozen]
    │   │   └── fix_02/
    │   │       ├── design_review.md         [Frozen]
    │   │       └── validation_report.md     [Active]
    │   │
    │   └── governance/                # NEW container — meta documentation
    │       └── phase1/
    │           ├── documentation_audit.md
    │           ├── restructuring_plan.md
    │           └── migration_checklist.md
    │
    ├── notes/                         # UNCHANGED — informal notes
    │   └── README.md
    │
    └── api/                           # UNCHANGED — future API reference
        └── README.md
```

### Rationale for three review subtrees

| Subtree | Responsibility | Audience |
|---------|----------------|----------|
| `reviews/milestones/` | Capability delivery design reviews tied to M{n}.{m} identifiers | Implementers auditing a capability |
| `reviews/integration/` | End-to-end pipeline validation and product integration fixes | Integration/debugging work |
| `reviews/governance/` | Documentation and process meta-reports | Maintainers |

**Why not flatten:** Current flat `reviews/M*` + `integration_fix_*` mix causes naming collisions (is `M7.1` a milestone or integration event?) and hides the dependency chain fix_01 → fix_02.

### Renaming convention (integration fixes)

| Current path | Proposed path | Note |
|--------------|---------------|------|
| `integration_fix_01/` | `integration/fix_01/` | Shorter; "integration" namespace is parent |
| `integration_fix_02/` | `integration/fix_02/` | Same |

Optional display names in indexes: "Integration Fix #1 — Dependency / Environment", "Integration Fix #2 — Repository Consistency".

---

## 3. Document Responsibilities

### Entry and status layer

| Document | Responsibility | Must NOT |
|----------|----------------|----------|
| `README.md` (root) | One-paragraph pitch, install/run one-liner, link to docs | Duplicate capability tables |
| `docs/README.md` | Complete doc map with lifecycle badges | Duplicate ARCHITECTURE content |
| `docs/GETTING_STARTED.md` | Prerequisites, clone, test, run `app.py`, LLM setup, reading order | Replace DEVELOPMENT.md workflow detail |
| `docs/CURRENT_STATUS.md` | What works today, active integration defects, test count, last validation run | Duplicate full design reviews |

### Architecture layer (frozen)

| Document | Responsibility | Lifecycle |
|----------|----------------|-----------|
| `docs/architecture/ARCHITECTURE.md` | System design, agent boundaries, pipeline, freeze rules | **Frozen** — content refresh Phase 2 |
| `docs/architecture/CAPABILITIES.md` | Per-capability components and pipelines | **Frozen** — content refresh Phase 2 |
| `docs/adr/*` | Decision records | **Frozen** per ADR status field |

### Planning layer

| Document | Responsibility | Lifecycle |
|----------|----------------|-----------|
| `docs/roadmap/ROADMAP.md` | Chronological milestone narrative | **Active** — needs M6/M7/integration track update (Phase 2) |
| `docs/roadmap/MILESTONES.md` | Milestone process template and specs | **Active** |

### Review layer

| Document type | Filename convention | Lifecycle default |
|---------------|---------------------|-------------------|
| Milestone design review | `design_review.md` | **Frozen** at milestone commit |
| Ad-hoc dev review | `cursor_report.md` | **Historical** |
| Integration validation | `integration_report.md` | **Historical** after superseding run |
| Failure analysis | `failure_analysis.md` | **Frozen** as audit record |
| Fix design | `design_review.md` under `integration/fix_N/` | **Frozen** at fix completion |
| Fix validation | `validation_report.md` | **Active** until next fix supersedes |
| Governance | `documentation_audit.md`, etc. | **Active** for current phase |

### Placeholder layer

| Document | Responsibility | Lifecycle |
|----------|----------------|-----------|
| `docs/notes/README.md` | Note-taking convention | **Active** |
| `docs/api/README.md` | Future API reference scope | **Active** (empty) |

---

## 4. Lifecycle Classification

### Definitions

| Lifecycle | Meaning | Edit policy |
|-----------|---------|-------------|
| **Active** | Describes current process or ongoing work | May be updated any time |
| **Frozen** | Accurate snapshot at a completed milestone/fix; still valid as historical record | Do not rewrite; add errata link in CURRENT_STATUS if misleading |
| **Historical** | Superseded or ad-hoc; retained for audit | Do not delete; demote in indexes |
| **Deprecated** | Actively wrong to follow; replaced by another doc | Banner at top pointing to replacement |

### Full inventory classification

#### Root

| Path | Lifecycle |
|------|-----------|
| `README.md` | Active (needs status trim) |
| `DEVELOPMENT.md` | Active |
| `ARCHITECTURE.md` | Active (pointer) |

#### `docs/` core

| Path | Lifecycle |
|------|-----------|
| `docs/README.md` | Active |
| `docs/GETTING_STARTED.md` | Active (to create) |
| `docs/CURRENT_STATUS.md` | Active (to create) |
| `docs/architecture/ARCHITECTURE.md` | Frozen — **content stale** (Phase 2) |
| `docs/architecture/CAPABILITIES.md` | Frozen — **content stale** (Phase 2) |
| `docs/roadmap/ROADMAP.md` | Active — **content stale** (Phase 2) |
| `docs/roadmap/MILESTONES.md` | Active — **content stale** (Phase 2) |

#### ADRs

| Path | Lifecycle |
|------|-----------|
| `docs/adr/ADR-0001` … `0007` | Frozen (Accepted) |
| `docs/adr/README.md` | Active |

#### Milestone reviews → `reviews/milestones/`

| Path | Lifecycle |
|------|-----------|
| `M4.1/design_review.md` | Frozen |
| `M4.1/cursor_report.md` | Historical |
| `M4.2` … `M4.3` design reviews | Frozen |
| `M5.1`, `M5.1.1`, `M5.2` design reviews | Frozen |
| `M5.F/design_review.md` | Frozen (capability-freeze baseline) |
| `M6.1`, `M6.2`, `M6.3` design reviews | Frozen |

#### Integration → `reviews/integration/`

| Path | Lifecycle |
|------|-----------|
| `M7.1/integration_report.md` | Historical (mock LLM run; superseded by real-LLM runs) |
| `fix_01/failure_analysis.md` | Frozen |
| `fix_02/design_review.md` | Frozen |
| `fix_02/validation_report.md` | Active |

#### Governance → `reviews/governance/`

| Path | Lifecycle |
|------|-----------|
| `phase1/documentation_audit.md` | Active |
| `phase1/restructuring_plan.md` | Active |
| `phase1/migration_checklist.md` | Active |

---

## 5. Proposed `GETTING_STARTED.md` Outline (summary only)

Not full content — created during migration Step 2:

1. What ResearchAgent MVP does (2 sentences + link to ARCHITECTURE §1)
2. Prerequisites (Python 3.10+, API key optional)
3. Install and run tests
4. Run `app.py` / integration script pointer
5. **Reading order** for new contributors:
   - `CURRENT_STATUS.md`
   - `architecture/ARCHITECTURE.md`
   - `DEVELOPMENT.md`
   - `adr/README.md`
   - `reviews/README.md`
6. What not to read first (individual milestone reviews, historical integration reports)

---

## 6. Proposed `CURRENT_STATUS.md` Outline (summary only)

Single page, updated after each integration run or milestone:

1. **Last updated** date
2. **Pipeline stages implemented** (checklist)
3. **Capability freeze** pointer (M5.F still applies to Reader–Runner interfaces)
4. **Post-M5 work completed** (M6.1–M6.3 summary — link to reviews)
5. **Integration status** (latest run: FAILED / partial; link to fix_02 validation)
6. **Known active defects** (from latest validation report — bullet list, not full copy)
7. **Test count** (101 passing — verify at update time)
8. **Stale doc warning** — ARCHITECTURE/CAPABILITIES/ROADMAP/README pending Phase 2 content sync
9. **What is NOT in scope** (unchanged from MVP)

---

## 7. Why This Plan Was Chosen Over Alternatives

| Alternative | Rejected because |
|-------------|------------------|
| Merge all reviews into one CHANGELOG | Loses milestone audit trail |
| Delete `cursor_report.md` | Violates historical preservation goal |
| Create `ProjectContext`-scale doc framework | Over-engineering for MVP |
| Move ADRs under `architecture/` | ADRs are cross-cutting; separate namespace is standard |
| Single flat `reviews/` with prefixes | Already failed — indexes are unmaintainable |
| Rewrite all stale docs in Phase 1 | Scope creep; governance phase is structure-first |

---

## 8. Phase Boundaries

| Phase | Scope |
|-------|-------|
| **Phase 1 (this plan)** | Audit, propose tree, migration checklist, create GETTING_STARTED + CURRENT_STATUS, rewrite indexes, move files with redirects |
| **Phase 2 (future)** | Content sync: ARCHITECTURE, CAPABILITIES, ROADMAP, README pipeline diagrams |
| **Phase 3 (optional)** | API reference population, link checker CI, frontmatter lifecycle tags |

---

## 9. Success Criteria

Phase 1 restructuring succeeds when:

- [ ] New contributor can reach `CURRENT_STATUS.md` from root README in ≤2 clicks
- [ ] All 11 review areas appear in `reviews/README.md` with lifecycle badges
- [ ] Integration fix chain fix_01 → fix_02 is navigable from `integration/README.md`
- [ ] No historical document deleted
- [ ] Existing relative links either work or have stub redirect notes (see migration checklist)
- [ ] `docs/reviews/README.md` no longer contains false "no subdirectories" claim
