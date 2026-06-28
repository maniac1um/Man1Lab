# ADR-0004 — Planning Strategy

## Status

Accepted

## Date

2026-06-28

## Context

ResearchAgent must convert a structured `PaperModel` into a sequence of engineering actions that the Coder and Runner can execute. The Planner sits between paper understanding and code generation. Without a clear role definition, the Planner risks becoming a paper summarizer or a general reasoning agent, which would duplicate Reader responsibilities and introduce non-executable output into the workflow.

The reproduction workflow requires concrete, ordered engineering tasks — not narrative summaries or open-ended analysis.

## Decision

The Planner is an **engineering task planner**.

Its sole responsibility is to transform a `PaperModel` into a `TaskModel` containing executable engineering tasks required for paper reproduction.

```text
PaperModel
  ↓
Engineering Task Plan
  ↓
TaskModel
```

The Planner decomposes reproduction into engineering steps such as:

* dependency installation
* dataset preparation
* environment setup
* model implementation
* training
* evaluation

The Planner does not summarize the paper. The Planner does not perform open-ended reasoning. The Planner does not write code. The Planner does not execute tasks.

Each task in `TaskModel` must be actionable by downstream agents (primarily Coder and Runner), with a clear identifier, name, description, and status.

## Alternatives Considered

**Paper summarizer:** Transform `PaperModel` into a narrative summary. Rejected because Reader already extracts structured paper information; summarization produces no executable plan.

**Reasoning agent:** Use the LLM for open-ended analysis of reproduction feasibility, methodology critique, or literature comparison. Rejected because it does not produce ordered engineering tasks and introduces non-deterministic scope beyond MVP requirements.

**End-to-end plan-and-code agent:** Combine planning and code generation in one step. Rejected because it violates single-responsibility agent design and prevents independent replacement of Planner or Coder.

**Fixed static task template:** Always emit the same task list regardless of paper content. Rejected because different papers require different reproduction steps (e.g. dataset preparation varies by domain).

## Consequences

**Positive:**
- Clear boundary between Reader (paper understanding) and Planner (engineering decomposition)
- `TaskModel` output is directly consumable by Coder
- Task status field supports future workflow visualization and scheduling
- Planner scope remains testable and bounded

**Negative:**
- Planner quality depends on `PaperModel` completeness
- Engineering decomposition rules must be defined incrementally across M3 milestones
- LLM-based planning may produce inconsistent task granularity without validation (addressed in M3.2)

## Relationship to Existing Architecture

This ADR defines Planner philosophy only. It does not change the workflow orchestration model (ADR-0001), Reader interface (ADR-0002), or prompt infrastructure (ADR-0003). Planner implementation details are deferred to Phase 2 milestones.
