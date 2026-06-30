# ADR-0009 — Analysis Layer Canonical Artifact

## Status

Accepted

## Date

2026-06-30

## Context

Man1Lab Phase 2 migrated Reader output from legacy flat `PaperModel` to modular `PaperReproductionAnalysis`. Phase 2.4 completes pipeline migration so Planner, Coder, Reviewer, Reporter, and Workflow consume the analysis artifact directly.

ADR-0002 previously froze `Reader.run() -> PaperModel`. That contract is superseded for the analysis pipeline by this ADR.

## Decision

`PaperReproductionAnalysis` is the **canonical artifact** of the Analysis layer and the sole domain object passed through the reproduction pipeline after Reader.

| Stage | Canonical input / output |
|-------|--------------------------|
| Parsing | `ParsedDocument` |
| Analysis (Reader) | `PaperReproductionAnalysis` |
| Planning | `TaskModel` (from analysis) |
| Generation (Coder) | `Workspace` (from analysis + task) |

`WorkflowHistory.analysis` stores the Reader output. `WorkflowHistory.paper` is removed.

`Reader.run(paper_path) -> PaperReproductionAnalysis` is the Reader workflow entry point.

## Legacy retirement

| Component | Status after Phase 2.4 |
|-----------|------------------------|
| `PaperModel` in runtime pipeline | **Removed** |
| `validation/paper_model_adapter.py` | **Deleted** |
| `models/paper.py` | Retained only for legacy unit tests (`test_paper_validation.py`) |
| `validation/paper.py` | Retained only for legacy validation tests |

## Consequences

**Positive:**
- Single domain object across pipeline stages
- Planner/Coder/Reviewer consume structured modules (goal, resources, method, evaluation, gaps)
- No silent semantic loss from flat adapter projection

**Negative:**
- ADR-0002 return type amended (documented here)
- External docs referencing `PaperModel` require update in documentation pass

## Relationship to other ADRs

- ADR-0008 (Parsing): unchanged — Parsing layer still outputs `ParsedDocument`
- ADR-0004/0005 (Planning): Planner input type changes from `PaperModel` to `PaperReproductionAnalysis`; planning philosophy unchanged
