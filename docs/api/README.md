# API Documentation

Public API reference for Man1Lab v1.1.0.

## Purpose

Document stable contracts for contributors and integrators:

- Agent public methods and type contracts
- Domain model field definitions
- Service interfaces
- Workflow orchestrator entry points

## Current State

Detailed API reference pages (`agents.md`, `models.md`, etc.) are not yet written. Public contracts are defined in source code and summarized below.

For capability-level documentation, see [CAPABILITIES.md](../architecture/CAPABILITIES.md). For frozen interface policy, see [DEVELOPMENT.md](../../DEVELOPMENT.md). Analysis artifact migration: [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md).

---

## Workflow Entry Point

| Component | Contract |
|-----------|----------|
| `WorkflowOrchestrator` | `run(paper_path: Path) -> ReportModel` |
| `TrackedWorkflowOrchestrator` | Wraps orchestrator; records MLflow runs ([ADR-0012](../adr/ADR-0012-Experiment-Tracking-MLflow.md)) |
| `app.py` | Composition root; wires agents, services, and tracking |

---

## Agents

| Agent | Public method | Input | Output |
|-------|---------------|-------|--------|
| `Reader` | `run(paper_path)` | `Path` | `PaperReproductionAnalysis` |
| `Reader` | `read_text(paper_path)` | `Path` | `str` |
| `Planner` | `run(analysis)` | `PaperReproductionAnalysis` | `TaskModel` |
| `Coder` | `run(analysis, task, patch_plan=None)` | `PaperReproductionAnalysis`, `TaskModel` | `Workspace` |
| `Runner` | `run(workspace)` | `Workspace` | `ExecutionResult` |
| `Reviewer` | `run(analysis, task, verification_result)` | `PaperReproductionAnalysis`, `TaskModel`, `VerificationResult` | `ReviewReport` |
| `Reporter` | `run(history)` | `WorkflowHistory` | `ReportModel` |

**Coder internal:** `RepositoryAcceptanceError` is raised from `agents/coder_quality.py` when the repository acceptance gate rejects a workspace. Not part of the public agent contract.

---

## Services

| Service | Key method | Purpose |
|---------|------------|---------|
| `PDFService` | `extract_text(path)` | PDF text extraction (legacy; parsing via `DocumentParser` port) |
| `PromptLoader` | `load(agent, section)` | Load prompt markdown |
| `PromptBuilder` | `build_*_prompt()` | Assemble agent prompts |
| `WorkspaceManager` | `create_workspace`, `write_file`, `read_file`, `write_report` | Repository filesystem |
| `EnvironmentService` | `prepare(workspace)` | Virtualenv + pip install |
| `ExecutionPlanner` | `plan(workspace)` | Build `ExecutionPlan` |
| `ExecutionService` | `execute(plan, workspace)` | Run training script |
| `VerificationService` | `verify(workspace, execution_result)` | Deterministic checks |

---

## Planning

| Component | Contract |
|-----------|----------|
| `PatchPlanner` | `plan(review_report) -> PatchPlan` |
| `TaskRouter` | `route_task(task) -> TaskRoutingTable` |

---

## Domain Models

Located in `models/`:

| Model | Produced by |
|-------|-------------|
| `PaperReproductionAnalysis` | Reader |
| `TaskModel` | Planner |
| `Workspace` | Coder |
| `ExecutionResult` | Runner |
| `VerificationResult` | VerificationService |
| `ReviewReport` | Reviewer |
| `PatchPlan` | PatchPlanner |
| `ReportModel` | Reporter |

`PaperModel` is retained for legacy unit tests only — not part of the runtime pipeline ([ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md)).

---

## Planned Structure

```text
api/
    README.md          # This file
    agents.md          # (future)
    models.md          # (future)
    services.md        # (future)
    workflow.md        # (future)
```

API reference pages will be added as Platform Capability (v1.2) stabilizes public contracts.
