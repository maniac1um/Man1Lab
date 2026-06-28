# ResearchAgent Capability Summary

Current implementation status of ResearchAgent MVP capabilities as of the M5.F architecture freeze.

For architecture details see [ARCHITECTURE.md](ARCHITECTURE.md). For design decisions see [ADR index](../adr/README.md).

---

## Capability Overview

| Capability | Status | Input | Output |
|------------|--------|-------|--------|
| Reader | **Implemented** | Research paper (PDF) | `PaperModel` |
| Planner | **Implemented** | `PaperModel` | `TaskModel` |
| Coder | **Implemented** | `PaperModel`, `TaskModel` | `Workspace` |
| Runner | **Implemented** | `Workspace` | `ExecutionResult` |
| Reviewer | **Planned** | `ExecutionResult` | `PatchPlan` |
| Reporter | **Partial** | `WorkflowHistory` | `ReportModel` |

---

## Reader

**Purpose:** Extract structured paper information from a PDF research paper.

| Field | Value |
|-------|-------|
| **Input artifact** | Research paper (`paper.pdf`) |
| **Output artifact** | `PaperModel` |
| **Agent** | `Reader` |
| **Status** | Implemented |

**Major components:**

| Component | Role |
|-----------|------|
| `PDFService` | PDF text extraction |
| `PromptBuilder` | Reader prompt assembly |
| `LLMProvider` | Structured extraction |
| `ResponseParser` | JSON parsing |
| `validation/paper.py` | Validation and `PaperModel` construction |

**Pipeline:**

```text
PDF → PDFService → Prompt → LLM → dict → Validation → PaperModel
```

---

## Planner

**Purpose:** Convert structured paper information into ordered engineering tasks.

| Field | Value |
|-------|-------|
| **Input artifact** | `PaperModel` |
| **Output artifact** | `TaskModel` |
| **Agent** | `Planner` |
| **Status** | Implemented |

**Major components:**

| Component | Role |
|-----------|------|
| `PromptBuilder` | Planner prompt assembly |
| `LLMProvider` | Structured task extraction |
| `ResponseParser` | JSON parsing |
| `validation/task.py` | Validation and `TaskModel` construction |

**Pipeline:**

```text
PaperModel → Prompt → LLM → dict → Validation → TaskModel
```

---

## Coder

**Purpose:** Build and populate a reproduction workspace from engineering tasks.

| Field | Value |
|-------|-------|
| **Input artifact** | `PaperModel`, `TaskModel` |
| **Output artifact** | `Workspace` |
| **Agent** | `Coder` |
| **Status** | Implemented |

**Major components:**

| Component | Role |
|-----------|------|
| `WorkspaceManager` | Repository filesystem operations |
| `TaskRouter` | Deterministic task-to-file routing |
| `PromptBuilder` | Per-file category prompts |
| `LLMProvider` | Per-target file generation |
| `CoderMockLLMProvider` | Default mock file content (no API key) |

**Pipeline:**

```text
TaskModel → TaskRouter → TaskRoutingTable
         → WorkspaceManager (skeleton)
         → LLM per RepositoryTarget → WorkspaceManager.write_file
         → Workspace
```

Repository artifacts (`src/`, `configs/`, `scripts/`, `README.md`, `requirements.txt`) are written exclusively through `WorkspaceManager`.

---

## Runner

**Purpose:** Prepare the workspace environment and execute the reproduction training script.

| Field | Value |
|-------|-------|
| **Input artifact** | `Workspace` |
| **Output artifact** | `ExecutionResult` |
| **Agent** | `Runner` (coordinator) |
| **Status** | Implemented |

**Major components:**

| Component | Role |
|-----------|------|
| `EnvironmentService` | Virtual environment creation and dependency installation (M5.1) |
| `ExecutionPlanner` | Build `ExecutionPlan` for `scripts/train.py` (M5.2) |
| `ExecutionService` | Execute plan, capture output, write `execution.log` (M5.2) |

**Pipeline:**

```text
Workspace → EnvironmentService.prepare()
         → ExecutionPlanner.plan() → ExecutionPlan
         → ExecutionService.execute() → ExecutionResult
```

Runtime artifacts (`.venv/`, `logs/`) are managed by execution services. See [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) and [ADR-0007](../adr/ADR-0007-Execution-Capability.md).

---

## Reviewer

**Purpose:** Analyze execution failures and produce a repair plan for the review loop.

| Field | Value |
|-------|-------|
| **Input artifact** | `ExecutionResult` |
| **Output artifact** | `PatchPlan` |
| **Agent** | `Reviewer` |
| **Status** | Planned (mock implementation only) |

**Current state:** `Reviewer.run()` returns a stub `PatchPlan` with `requires_patch=False`. No failure analysis or repair strategy generation is implemented.

**Next milestone:** M6 — Reviewer Capability.

---

## Reporter

**Purpose:** Generate a final structured report from workflow history.

| Field | Value |
|-------|-------|
| **Input artifact** | `WorkflowHistory` |
| **Output artifact** | `ReportModel` |
| **Agent** | `Reporter` |
| **Status** | Partial (template-based report generation) |

**Current state:** `Reporter.run()` produces a template `ReportModel`. `WorkspaceManager.write_report()` persists the report. Full reporting capability is planned under M7.

---

## Capability Freeze (M5.F)

The following capabilities are frozen for MVP baseline before M6:

- Reader
- Planner
- Coder
- Runner

Public interfaces for these capabilities are stable. Internal implementation may change only with ADR and architecture review.
