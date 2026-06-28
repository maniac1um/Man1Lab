# ADR-0005 — Planner Capability

## Status

Accepted

## Date

2026-06-28

## Context

ResearchAgent requires a planning stage between paper understanding (`PaperModel`) and code generation (`TaskModel`). The Planner must convert structured paper information into ordered engineering tasks without duplicating Reader responsibilities or preempting Coder and Runner responsibilities.

Milestone M3 implemented the Planner through the same pattern established by the Reader: structured LLM extraction, validation, normalization, and typed model construction.

## Decision

The Planner transforms `PaperModel` into `TaskModel` through the following pipeline:

```text
PaperModel
  ↓
Prompt
  ↓
LLM
  ↓
Structured dict
  ↓
Validation
  ↓
Normalization
  ↓
TaskModel
```

The Planner is responsible **only** for engineering task decomposition. It:

* receives `PaperModel` as input
* produces `TaskModel` as output
* decomposes reproduction work into executable engineering tasks

The Planner does **not**:

* generate source code
* execute tasks
* schedule task execution
* optimize dependency graphs
* summarize the paper

Task dependencies (`depends_on`) are extracted and validated but not used for scheduling in the current MVP.

`Planner.run(paper: PaperModel) -> TaskModel` is the stable public interface.

## Alternatives Considered

**Fixed task template:** Emit the same task list for every paper. Rejected in M3.1; different papers require different reproduction steps.

**Combined plan-and-code agent:** Merge Planner and Coder into one LLM call. Rejected; violates single-responsibility and prevents independent agent replacement.

**Reasoning-first planner:** Use the LLM for open-ended feasibility analysis before task generation. Rejected; produces non-executable narrative output outside MVP scope (see ADR-0004).

**Store depends_on in TaskModel:** Extend `TaskStep` with dependency fields. Deferred; validation confirms graph integrity without requiring scheduling infrastructure in MVP.

## Consequences

**Positive:**
- Planner capability mirrors Reader pattern; consistent validation and testing approach
- `TaskModel` is directly consumable by Coder
- Clear separation: Reader understands paper, Planner plans work, Coder implements
- `TaskValidationError` provides explicit failure on invalid LLM output

**Negative:**
- `depends_on` is validated but discarded at `TaskModel` construction
- Planner quality depends on `PaperModel` completeness
- No retry on validation failure; invalid LLM output terminates the stage

## Relationship to Existing ADRs

This ADR records the completed Planner capability. It implements the philosophy defined in [ADR-0004](ADR-0004-Planning-Strategy.md) and uses the prompt infrastructure from [ADR-0003](ADR-0003-Prompt-Infrastructure.md). Workflow scheduling remains governed by [ADR-0001](ADR-0001-Workflow-Orchestrator.md).
