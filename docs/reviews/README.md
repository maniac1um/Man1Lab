# Review Documents

This directory stores milestone review reports produced during the development lifecycle.

## Purpose

Reviews capture factual assessments of implementation at milestone boundaries. They support architecture review, onboarding, and audit without requiring readers to inspect git history.

## Organization

Reviews are grouped by milestone identifier:

```text
reviews/
    README.md
    M2.1/
        cursor_report.md
        architecture_review.md
        action_items.md
    M2.1.8/
        ...
    M2.1.9/
        ...
```

Create a subdirectory when a milestone produces review artifacts.

## Document Types

| File | Purpose |
|------|---------|
| `cursor_report.md` | Implementation or design review generated during development (e.g. agent-assisted review) |
| `architecture_review.md` | Formal architecture alignment check against `docs/architecture/ARCHITECTURE.md` and ADRs |
| `action_items.md` | Outstanding items identified during review; may be empty if none |

Not every milestone requires all three files. Create only what is produced.

## Guidelines

- Reports must be factual; describe current state, not future recommendations
- Include dependency graphs, API listings, and test coverage where relevant
- Reference related ADRs by number
- Do not duplicate ADR content; link instead

## Current State

No milestone review subdirectories exist yet. Past reviews were produced in development sessions and should be migrated here as milestones are formally closed.
