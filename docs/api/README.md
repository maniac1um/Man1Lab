# API Documentation

Public API reference for Man1Lab v1.0.0.

## Purpose

Document stable contracts for contributors and integrators:

- Agent public methods and type contracts
- Domain model field definitions
- Service interfaces
- Workflow orchestrator entry points

## Current State

Detailed API reference pages (`agents.md`, `models.md`, etc.) are not yet written. Public contracts are defined in source code and summarized below.

For capability-level documentation, see [CAPABILITIES.md](../architecture/CAPABILITIES.md). For frozen interface policy, see [DEVELOPMENT.md](../../DEVELOPMENT.md).

---

## Workflow Entry Point

| Component | Contract |
|-----------|----------|
| `WorkflowOrchestrator` | `run(paper_path: Path) -> ReportModel` |
| `app.py` | Composition root; wires agents and services |

---

## Agents

| Agent | Public method | Input | Output |
|-------|---------------|-------|--------|
| `Reader` | `run(paper_path)` | `Path` | `PaperModel` |
| `Reader` | `read_text(paper_path)` | `Path` | `str` |
| `Planner` | `run(paper)` | `PaperModel` | `TaskModel` |
| `Coder` | `run(paper, task, patch_plan=None)` | `PaperModel`, `TaskModel` | `Workspace` |
| `Runner` | `run(workspace)` | `Workspace` | `ExecutionResult` |
| `Reviewer` | `run(paper, task, verification_result)` | `PaperModel`, `TaskModel`, `VerificationResult` | `ReviewReport` |
| `Reporter` | `run(history)` | `WorkflowHistory` | `ReportModel` |

**Coder internal:** `RepositoryAcceptanceError` is raised from `agents/coder_quality.py` when the repository acceptance gate rejects a workspace. Not part of the public agent contract.

---

## Services

| Service | Key method | Purpose |
|---------|------------|---------|
| `PDFService` | `extract_text(path)` | PDF text extraction |
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
| `PaperModel` | Reader |
| `TaskModel` | Planner |
| `Workspace` | Coder |
| `ExecutionResult` | Runner |
| `VerificationResult` | VerificationService |
| `ReviewReport` | Reviewer |
| `PatchPlan` | PatchPlanner |
| `ReportModel` | Reporter |

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

API reference pages will be added when interfaces stabilize beyond v1.0.0.
