# Man1Lab Capability Summary

Implementation status of Man1Lab v1.0.0 capabilities.

For the latest benchmarks and limitations, see [CURRENT_STATUS.md](../CURRENT_STATUS.md). For architecture detail see [ARCHITECTURE.md](ARCHITECTURE.md). For design decisions see [ADR index](../adr/README.md).

---

## Capability Overview

| Capability | Status | Input | Output |
|------------|--------|-------|--------|
| Reader | **Implemented** | Research paper (PDF) | `PaperModel` |
| Planner | **Implemented** | `PaperModel` | `TaskModel` |
| Coder | **Implemented** | `PaperModel`, `TaskModel` | `Workspace` |
| Runner | **Implemented** | `Workspace` | `ExecutionResult` |
| Verification | **Implemented** | `Workspace`, `ExecutionResult` | `VerificationResult` |
| Reviewer | **Implemented** | `PaperModel`, `TaskModel`, `VerificationResult` | `ReviewReport` |
| PatchPlanner | **Implemented** | `ReviewReport` | `PatchPlan` |
| Reporter | **Implemented** | `WorkflowHistory` | `ReportModel` |

Reader, Planner, Coder, and Runner public interfaces are frozen since [M5.F](../reviews/M5.F/design_review.md).

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
| `agents/coder_quality.py` | Framework binding, validation, requirements reconciliation, acceptance gate |

**Pipeline:**

```text
TaskModel → TaskRouter → TaskRoutingTable
         → WorkspaceManager (skeleton)
         → LLM per RepositoryTarget → WorkspaceManager.write_file
         → reconcile requirements (GQ-1)
         → validate + decide_repository_acceptance (RAG)
         → Workspace
```

Repository artifacts (`src/`, `configs/`, `scripts/`, `README.md`, `requirements.txt`) are written exclusively through `WorkspaceManager`.

**Delivery quality layers:**

| Layer | Reference |
|-------|-----------|
| GQ-1 (generation quality) | [implementation review](../reviews/generation_quality_upgrade_v1/implementation_review.md) |
| RAG (repository acceptance gate) | [implementation review](../reviews/repository_acceptance_gate/implementation_review.md) |

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
| `EnvironmentService` | Virtual environment creation and dependency installation |
| `ExecutionPlanner` | Build `ExecutionPlan` for `scripts/train.py` |
| `ExecutionService` | Execute plan, capture output, write `execution.log` |

**Pipeline:**

```text
Workspace → EnvironmentService.prepare()
         → ExecutionPlanner.plan() → ExecutionPlan
         → ExecutionService.execute() → ExecutionResult
```

Runtime artifacts (`.venv/`, `logs/`) are managed by execution services. See [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) and [ADR-0007](../adr/ADR-0007-Execution-Capability.md).

---

## Verification

**Purpose:** Deterministic checks on execution outcome before LLM review.

| Field | Value |
|-------|-------|
| **Input artifacts** | `Workspace`, `ExecutionResult` |
| **Output artifact** | `VerificationResult` |
| **Service** | `VerificationService` |
| **Status** | Implemented |

**Module:** `services/verification_service.py`

Invoked by `WorkflowOrchestrator` between Runner and Reviewer. See [M6.1 design review](../reviews/M6.1/design_review.md).

---

## Reviewer

**Purpose:** Analyze execution failures using LLM structured extraction.

| Field | Value |
|-------|-------|
| **Input artifacts** | `PaperModel`, `TaskModel`, `VerificationResult` |
| **Output artifact** | `ReviewReport` |
| **Agent** | `Reviewer` |
| **Status** | Implemented |

**Major components:** `PromptBuilder`, `LLMProvider`, `validation/review.py`

See [M6.2 design review](../reviews/M6.2/design_review.md).

---

## PatchPlanner

**Purpose:** Convert review findings into a structured repair plan.

| Field | Value |
|-------|-------|
| **Input artifact** | `ReviewReport` |
| **Output artifact** | `PatchPlan` |
| **Component** | `PatchPlanner` |
| **Status** | Implemented |

**Module:** `planning/patch_planner.py`

See [M6.3 design review](../reviews/M6.3/design_review.md). The orchestrator does not yet re-invoke Coder/Runner when `requires_patch` is true.

---

## Reporter

**Purpose:** Generate a final structured report from workflow history.

| Field | Value |
|-------|-------|
| **Input artifact** | `WorkflowHistory` |
| **Output artifact** | `ReportModel` |
| **Agent** | `Reporter` |
| **Status** | Implemented |

`Reporter.run()` produces a `ReportModel`. `WorkspaceManager.write_report()` persists the report to `outputs/report.md`.

---

## Capability Freeze (M5.F)

The following agent public interfaces are frozen for MVP baseline:

- Reader
- Planner
- Coder
- Runner

Post-M5 capabilities (Verification, Reviewer, PatchPlanner, Reporter, Coder quality layers) were added without changing these frozen contracts. Internal Coder behavior may evolve; `Coder.run()` signature is unchanged.
