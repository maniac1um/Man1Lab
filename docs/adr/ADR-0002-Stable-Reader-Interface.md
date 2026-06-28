# ADR-0002 — Stable Reader Interface

## Status

Accepted

## Date

2026-06-28

## Context

The Reader agent underwent internal refactoring during M2.1 (PDF ingestion). Temporarily, `Reader.run()` returned raw `str`, which broke `WorkflowOrchestrator` and downstream agents that expect `PaperModel`. The workflow must remain executable while internal Reader implementation evolves across milestones.

## Decision

`Reader` exposes two public methods with stable contracts:

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `read_text(paper_path)` | `Path` | `str` | Raw document text from PDF |
| `run(paper_path)` | `Path` | `PaperModel` | Workflow entry point; always returns `PaperModel` |

Internal implementation may change (PDF service, prompt building, LLM extraction). The public signatures and return types must not change without a new ADR.

During M2.1–M2.2, `run()` may construct a placeholder `PaperModel` until LLM extraction is implemented.

## Alternatives

**Return `str` from `run()`:** Rejected; breaks orchestrator and all downstream agents.

**Separate `IngestionAgent` and `ReaderAgent`:** Rejected for MVP; adds agent count and orchestrator complexity without current benefit.

**Union return type `str | PaperModel`:** Rejected; violates typed artifact communication principle.

## Consequences

**Positive:**
- Workflow remains executable during Reader evolution
- `read_text()` enables isolated PDF ingestion testing
- Downstream agents depend only on `PaperModel`

**Negative:**
- Placeholder `PaperModel` fields may mislead Planner until M2.2
- Two public methods require clear documentation of when to use each

## Frozen Interface

`Reader.read_text()` and `Reader.run()` signatures and return types are architecture-frozen.
