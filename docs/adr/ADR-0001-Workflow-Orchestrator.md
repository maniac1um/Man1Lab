# ADR-0001 — Workflow Orchestrator

## Status

Accepted

## Date

2026-06-28

## Context

ResearchAgent coordinates six specialized agents to reproduce a research paper. Agents must remain independent, replaceable, and testable. Direct agent-to-agent calls would create tight coupling and make scheduling, retry logic, and execution history difficult to manage centrally.

## Decision

`WorkflowOrchestrator` is the **only** component responsible for:

- Scheduling agent execution order
- Controlling the review retry loop
- Maintaining `WorkflowHistory`
- Invoking `WorkspaceManager.write_report()` after `Reporter`

Agents never call each other. All inter-agent communication uses strongly typed Pydantic models passed through the orchestrator.

## Alternatives

**Direct agent chaining:** Each agent calls the next. Rejected because it couples agents, hides workflow logic, and complicates retry and history tracking.

**Event bus / message queue:** Agents publish and subscribe to events. Rejected as over-engineering for MVP scope.

**Distributed workflow engine:** External orchestration (e.g. Temporal). Rejected; excluded from MVP scope per architecture document.

## Consequences

**Positive:**
- Single place to understand and modify workflow order
- Agents are stateless and independently testable
- Retry loop and history are centralized

**Negative:**
- Orchestrator becomes a dependency hub
- Adding workflow branches requires orchestrator changes
- All workflow state flows through one class

## Frozen Interface

`WorkflowOrchestrator` public constructor and `run(paper_path: Path) -> ReportModel` are architecture-frozen. Changes require a new ADR and architecture review.
