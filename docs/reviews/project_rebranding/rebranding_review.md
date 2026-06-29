# Project Rebranding — ResearchAgent → Man1Lab

**Milestone:** Project Rebranding  
**Type:** Documentation-only identity update  
**Date:** 2026-06-29  
**New public name:** Man1Lab  
**Subtitle:** An autonomous research paper reproduction pipeline

---

## 1. Executive Summary

The public-facing project identity has been renamed from **ResearchAgent** to **Man1Lab** across current documentation and release assets. Historical development records (milestone reviews, ADRs, acceptance reports, implementation reviews) were **not rewritten** to preserve audit accuracy.

| Area | Action |
|------|--------|
| Public documentation | Rebranded to Man1Lab |
| Production code | Unchanged |
| Prompts | Unchanged |
| ADRs | Preserved (historical) |
| Milestone/integration reports | Preserved (historical) |
| GitHub URLs | Unchanged (`Research_Agent_MVP`) — actual remote name not yet renamed |

**Branding rule:** Man1Lab is the project name; `Research_Agent_MVP` remains the repository path until GitHub rename is performed.

---

## 2. Files Updated

### Root

| File | Changes |
|------|---------|
| `README.md` | Title, subtitle, descriptions, citation BibTeX |
| `CHANGELOG.md` | Project name; `[Unreleased]` rebrand note |
| `CONTRIBUTING.md` | Opening paragraph |
| `DEVELOPMENT.md` | Repository and lifecycle references |
| `release/v1.0.0.md` | Title **Man1Lab v1.0.0 (Research Prototype)**; body branding; citation |

### docs/

| File | Changes |
|------|---------|
| `docs/README.md` | Index title; rebranding navigation entry |
| `docs/CURRENT_STATUS.md` | Project field; rebranding link |
| `docs/GETTING_STARTED.md` | Project overview |
| `docs/architecture/ARCHITECTURE.md` | Title and vision §1 |
| `docs/architecture/CAPABILITIES.md` | Title and intro |
| `docs/roadmap/ROADMAP.md` | Title and intro |
| `docs/roadmap/MILESTONES.md` | Intro line |
| `docs/api/README.md` | Title line |

### Release governance (branding only)

| File | Changes |
|------|---------|
| `docs/reviews/release_preparation/documentation_review.md` | Executive summary opening sentence |
| `docs/reviews/release_packaging/release_review.md` | Suggested GitHub Release title |
| `docs/reviews/README.md` | Rebranding index entry |

### Created

| File |
|------|
| `docs/reviews/project_rebranding/rebranding_review.md` |

---

## 3. Branding Rules Applied

| Rule | Application |
|------|-------------|
| **Man1Lab** | All public-facing current documentation |
| Subtitle | "An autonomous research paper reproduction pipeline" |
| Release title | `Man1Lab v1.0.0 (Research Prototype)` |
| Citation key | `man1lab_2026` |
| Repository URLs | Kept as `https://github.com/maniac1um/Research_Agent_MVP` (actual `git remote`) |
| Clone directory | Kept as `Research_Agent_MVP` in examples until GitHub rename |
| Filesystem paths in ARCHITECTURE | `Research_Agent_MVP/` directory tree unchanged (physical path) |
| Python modules/classes/APIs | Unchanged |
| Prompts | Unchanged (constraint) |
| Historical reports | Unchanged (constraint) |
| ADRs | Unchanged (constraint) |

---

## 4. Historical Documents Preserved

The following retain **ResearchAgent** / **Research Agent** references as written at completion time:

| Category | Examples |
|----------|----------|
| Milestone design reviews | `docs/reviews/M4.x` – `M7.F` |
| Acceptance/integration reports | `M8.1`, `M8.2`, `M7.1`, `integration_fix_*` |
| Implementation reviews | GQ-1, RAG, integration_fix_03 |
| ADRs | ADR-0001 through ADR-0007 |
| Governance audits | `documentation_governance_phase1/` |
| Restructuring proposals | Historical planning docs |

Navigation indexes (`docs/reviews/README.md`) reference these without rewriting their content.

---

## 5. Consistency Verification

| Document | Uses Man1Lab | Notes |
|----------|--------------|-------|
| `README.md` | ✓ | |
| `CHANGELOG.md` | ✓ | Mentions ResearchAgent only in rebrand note |
| `CONTRIBUTING.md` | ✓ | |
| `release/v1.0.0.md` | ✓ | |
| `docs/CURRENT_STATUS.md` | ✓ | |
| `docs/GETTING_STARTED.md` | ✓ | |
| `docs/README.md` | ✓ | |
| `docs/architecture/ARCHITECTURE.md` | ✓ | |
| `docs/architecture/CAPABILITIES.md` | ✓ | |
| `docs/roadmap/ROADMAP.md` | ✓ | |
| `DEVELOPMENT.md` | ✓ | |

All current-state documents present a consistent **Man1Lab** identity.

---

## 6. Remaining References

Intentionally unchanged references to ResearchAgent:

| Location | Reason |
|----------|--------|
| `prompts/reader/system.md` | Prompt constraint — no prompt changes |
| `prompts/planner/system.md` | Same |
| `prompts/reviewer/system.md` | Same |
| `prompts/patch_planner/system.md` | Same |
| `workspace/manager.py` | Production code — report title string |
| `outputs/report.md` | Runtime artifact |
| `docs/adr/ADR-*.md` | Historical ADR context |
| `docs/reviews/M8.1/acceptance_report.md` | Frozen acceptance report |
| `docs/reviews/integration_fix_03/design_review.md` | Frozen design review |
| `docs/reviews/documentation_governance_phase1/` | Historical governance |
| `CHANGELOG.md` `[Unreleased]` | Documents the rebrand event |

**Follow-up (optional, post-v1.0.0):**

1. Rename GitHub repository to `Man1Lab` and update URLs
2. Update prompt system messages to Man1Lab
3. Update `WorkspaceManager` report header to Man1Lab
4. Regenerate `outputs/report.md` on next pipeline run

---

## 7. Release Impact

| Item | Impact |
|------|--------|
| GitHub Release title | Use **Man1Lab v1.0.0 (Research Prototype)** |
| Release body | Use updated `release/v1.0.0.md` |
| Citation | BibTeX uses `man1lab_2026` and Man1Lab title |
| Repository URL in links | Still `Research_Agent_MVP` until GitHub rename |
| Tag `v1.0.0` | No change required; branding is documentation-level |
| Code behavior | No impact |

After GitHub repository rename to `Man1Lab`, update:

- `README.md`, `release/v1.0.0.md`, `CHANGELOG.md` URLs
- `git clone` examples in GETTING_STARTED and README
- Citation `url` field

---

## Evidence

| Check | Result |
|-------|--------|
| `rg ResearchAgent` in public docs (excl. historical) | Only CHANGELOG rebrand note and reviews index |
| `rg Man1Lab` in current docs | Consistent across 15 files |
| Production code modified | None |
| Prompts modified | None |
