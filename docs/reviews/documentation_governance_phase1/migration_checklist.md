# Documentation Migration Checklist — Phase 1

**Purpose:** Incremental, non-breaking documentation restructure  
**Rule:** Execute steps in order. Each step should leave the repository in a valid state.  
**Do not:** Modify production code, tests, or prompts in this migration.

---

## Pre-Migration

- [ ] **P0.1** Confirm branch / working tree clean for documentation-only commits
- [ ] **P0.2** Record baseline link targets used externally (if any): root README, `docs/README.md`
- [ ] **P0.3** Run `rg 'docs/reviews/' --glob '*.md'` and save output — inventory of inbound links to update
- [ ] **P0.4** Run `rg 'integration_fix_' --glob '*.md'` — inventory of fix path references

---

## Step 1 — Create entry-point documents (additive only)

No moves yet. New files only.

- [ ] **1.1** Create `docs/GETTING_STARTED.md`
  - Project one-liner
  - Prerequisites and install
  - Run tests and `app.py`
  - LLM configuration pointer (`.env.example`)
  - Reading order (links only — no duplicated architecture)
  - Link to `scripts/run_integration_m7_1.py` for integration runs

- [ ] **1.2** Create `docs/CURRENT_STATUS.md`
  - Last updated: 2026-06-28
  - Implemented stages: Reader through Reporter (orchestrator complete)
  - M6.1 Verification, M6.2 LLM Review, M6.3 Patch Planning — links to milestone reviews
  - Integration: fix_02 validation **Partially Fixed**; latest run `final_status: FAILED`
  - Active defect summary: cross-module import mismatch (`get_dataset`)
  - Tests: 101 passing
  - Stale doc notice: README, CAPABILITIES, ROADMAP, ARCHITECTURE §3.1 pending Phase 2 sync
  - Active work: integration fix track (not new milestones)

- [ ] **1.3** Update `docs/README.md`
  - Add GETTING_STARTED and CURRENT_STATUS to "Start Here" table (top rows)
  - Add "Integration & Validation" section linking to `reviews/integration/` (after Step 3) or interim flat paths
  - Add "Documentation Governance" link to `reviews/governance/phase1/`

- [ ] **1.4** Update root `README.md`
  - Replace outdated pipeline diagram with link to `docs/CURRENT_STATUS.md`
  - Move "Implemented / Planned" tables to link to CURRENT_STATUS (trim duplication)
  - Add `docs/GETTING_STARTED.md` to Documentation table
  - Keep run commands (or link to GETTING_STARTED if deduplicating)

- [ ] **1.5** Update `DEVELOPMENT.md` §Further Reading
  - Add GETTING_STARTED and CURRENT_STATUS
  - Replace "Reviewer is next milestone (M6)" with link to CURRENT_STATUS

**Verify:** All new links resolve. No files moved yet.

---

## Step 2 — Create review subtree scaffolding (empty indexes)

- [ ] **2.1** Create `docs/reviews/milestones/` (directory)
- [ ] **2.2** Create `docs/reviews/integration/README.md` with:
  - Integration track purpose
  - Table: M7.1, fix_01, fix_02 with lifecycle badges
  - Dependency diagram: M7.1 → fix_01 → fix_02
- [ ] **2.3** Create `docs/reviews/governance/phase1/` (move governance deliverables here in Step 4)

**Verify:** New README files render; no broken links to not-yet-moved paths (use interim note if needed).

---

## Step 3 — Move milestone reviews (git mv preserves history)

For each directory, `git mv docs/reviews/Mx.y docs/reviews/milestones/Mx.y`:

- [ ] **3.1** `M4.1/` → `milestones/M4.1/`
- [ ] **3.2** `M4.2/` → `milestones/M4.2/`
- [ ] **3.3** `M4.3/` → `milestones/M4.3/`
- [ ] **3.4** `M5.1/` → `milestones/M5.1/`
- [ ] **3.5** `M5.1.1/` → `milestones/M5.1.1/`
- [ ] **3.6** `M5.2/` → `milestones/M5.2/`
- [ ] **3.7** `M5.F/` → `milestones/M5.F/`
- [ ] **3.8** `M6.1/` → `milestones/M6.1/`
- [ ] **3.9** `M6.2/` → `milestones/M6.2/`
- [ ] **3.10** `M6.3/` → `milestones/M6.3/`

**Verify:** `rg 'docs/reviews/M[0-9]' --glob '*.md'` — update all hits to `docs/reviews/milestones/...`

---

## Step 4 — Move integration and governance docs

- [ ] **4.1** `git mv docs/reviews/M7.1 docs/reviews/integration/M7.1`
- [ ] **4.2** `git mv docs/reviews/integration_fix_01 docs/reviews/integration/fix_01`
- [ ] **4.3** `git mv docs/reviews/integration_fix_02 docs/reviews/integration/fix_02`
- [ ] **4.4** `git mv docs/reviews/documentation_governance_phase1 docs/reviews/governance/phase1`

**Verify:** Update references in:
- `integration/fix_02/design_review.md` (prerequisite path)
- `integration/fix_02/validation_report.md` (baseline path)
- Internal cross-links within moved files

---

## Step 5 — Add redirect stubs at old paths (preserve deep links)

For each moved top-level directory, leave a minimal `README.md` stub at the **old** path:

- [ ] **5.1** `docs/reviews/M4.1/README.md` → "Moved to [milestones/M4.1/](milestones/M4.1/)"
- [ ] **5.2** Repeat for M4.2, M4.3, M5.1, M5.1.1, M5.2, M5.F, M6.1, M6.2, M6.3, M7.1
- [ ] **5.3** `docs/reviews/integration_fix_01/README.md` → redirect to `integration/fix_01/`
- [ ] **5.4** `docs/reviews/integration_fix_02/README.md` → redirect to `integration/fix_02/`
- [ ] **5.5** `docs/reviews/documentation_governance_phase1/README.md` → redirect to `governance/phase1/`

**Alternative (fewer stubs):** Only stub paths that appear in `rg` inbound link inventory from P0.3. Minimum: `integration_fix_01`, `integration_fix_02`, `M6.1`–`M6.3` if externally linked.

**Verify:** Old URLs from audit land on redirect stub or resolve via updated links.

---

## Step 6 — Rewrite `docs/reviews/README.md`

- [ ] **6.1** Remove false "No milestone review subdirectories" statement
- [ ] **6.2** Add document-type glossary (design review, integration report, failure analysis, validation report)
- [ ] **6.3** Add three subtree sections with tables:

| Subtree | Count | Index link |
|---------|-------|------------|
| milestones/ | 11 | per-milestone table with lifecycle |
| integration/ | 3 areas | link to integration/README.md |
| governance/ | 1 phase | link to governance/phase1/ |

- [ ] **6.4** Add "Which review should I read?" decision guide:
  - Implementing a capability → milestone design review
  - Debugging E2E run → latest integration validation / failure analysis
  - Understanding doc structure → governance/phase1

**Verify:** Every review file appears exactly once in an index table.

---

## Step 7 — Update cross-references project-wide

Run and fix each:

- [ ] **7.1** `rg 'docs/reviews/M' --glob '*.md'`
- [ ] **7.2** `rg 'integration_fix_' --glob '*.md'`
- [ ] **7.3** `rg 'documentation_governance_phase1' --glob '*.md'`
- [ ] **7.4** Update `docs/architecture/CAPABILITIES.md` footer links if any
- [ ] **7.5** Update milestone design reviews that link sibling milestones (optional — frozen docs may keep historical paths if stubs exist)

**Verify:** No broken relative links from `docs/README.md` walkthrough.

---

## Step 8 — Lifecycle banners (non-destructive)

Add one-line HTML or markdown banner at top of selected files (optional but recommended):

- [ ] **8.1** `M4.1/cursor_report.md` — `> **Lifecycle: Historical** — superseded by design_review.md in this directory.`
- [ ] **8.2** `integration/M7.1/integration_report.md` — `> **Lifecycle: Historical** — mock LLM run; see integration/fix_02/validation_report.md for latest.`
- [ ] **8.3** `architecture/CAPABILITIES.md` — `> **Note:** Status summary frozen at M5.F; see [CURRENT_STATUS.md](../../CURRENT_STATUS.md) for current implementation state.`
- [ ] **8.4** `architecture/ARCHITECTURE.md` §3.1 — same pointer banner

**Verify:** Banners link correctly from new paths.

---

## Step 9 — DEVELOPMENT.md and roadmap pointer updates (minimal)

- [ ] **9.1** `DEVELOPMENT.md` §Design Review — note reviews live under `docs/reviews/milestones/{id}/`
- [ ] **9.2** `MILESTONES.md` §Design Review — same path update
- [ ] **9.3** Do **not** rewrite ROADMAP milestone statuses in Phase 1 unless explicitly scoped — link to CURRENT_STATUS instead

---

## Step 10 — Final validation

- [ ] **10.1** Manual walkthrough: clone-fresh reader path  
  `README.md` → `docs/GETTING_STARTED.md` → `docs/CURRENT_STATUS.md` → `docs/reviews/README.md` → specific review

- [ ] **10.2** Confirm integration chain readable:  
  `integration/fix_01/failure_analysis.md` → `integration/fix_02/design_review.md` → `integration/fix_02/validation_report.md`

- [ ] **10.3** Confirm no production files changed:  
  `git diff --name-only` shows only `docs/`, root `README.md`, `DEVELOPMENT.md`

- [ ] **10.4** Optional: add markdown link checker to CI (Phase 3)

- [ ] **10.5** Commit message:  
  `docs(governance): phase 1 documentation restructure and entry points`

---

## Rollback Plan

If a step breaks navigation:

1. `git revert` the migration commit
2. Redirect stubs (Step 5) allow partial rollback — keep stubs even if moves are reverted
3. GETTING_STARTED and CURRENT_STATUS are additive — safe to keep even if moves roll back

---

## Incremental Execution Strategy

| Session | Steps | Outcome |
|---------|-------|---------|
| A | Pre-migration + Step 1 | New entry points live; zero moves |
| B | Steps 2–4 | Files moved; update critical cross-links |
| C | Steps 5–7 | Redirects and project-wide link fix |
| D | Steps 8–10 | Lifecycle banners and validation |

Each session can be a separate commit.

---

## Out of Scope (Phase 2 checklist preview)

Do not block Phase 1 completion on these:

- [ ] Update `ARCHITECTURE.md` pipeline to include VerificationService
- [ ] Update `CAPABILITIES.md` Reviewer section to M6.3 state
- [ ] Update `ROADMAP.md` M6/M7 statuses and add integration track appendix
- [ ] Update root README pipeline diagram content
- [ ] Populate `docs/api/`
- [ ] Add first engineering note under `docs/notes/`

---

## Link Mapping Reference

| Old path | New path |
|----------|----------|
| `docs/reviews/M4.1/` | `docs/reviews/milestones/M4.1/` |
| `docs/reviews/M6.3/` | `docs/reviews/milestones/M6.3/` |
| `docs/reviews/M7.1/` | `docs/reviews/integration/M7.1/` |
| `docs/reviews/integration_fix_01/` | `docs/reviews/integration/fix_01/` |
| `docs/reviews/integration_fix_02/` | `docs/reviews/integration/fix_02/` |
| `docs/reviews/documentation_governance_phase1/` | `docs/reviews/governance/phase1/` |

---

## Completion Sign-off

| Item | Owner | Date |
|------|-------|------|
| Phase 1 migration executed | | |
| GETTING_STARTED.md live | | |
| CURRENT_STATUS.md live | | |
| reviews/README.md accurate | | |
| Link audit clean | | |
