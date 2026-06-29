# ARCHITECTURE.md

# ResearchAgent MVP v1.0.0

## 1. Vision

ResearchAgent is an autonomous paper reproduction framework.

The objective of MVP v1.0.0 is to reproduce a single research paper through an autonomous workflow.

The goal is **not** to achieve SOTA reproduction accuracy, but to build a stable, extensible and fully automated research pipeline.

The architecture should remain scalable for future support of multi-agent collaboration, memory systems and autonomous research.

---

# 2. MVP Scope

## Included

* Read one research paper (PDF)
* Extract structured paper information
* Generate a reproduction plan
* Generate project source code
* Execute generated code
* Analyze runtime failures
* Automatically revise implementation
* Generate a final report

## Excluded

* Multi-agent collaboration
* Memory / RAG
* Human feedback
* Cloud execution
* Distributed execution
* GUI
* Benchmark management

---

# 3. High-Level Architecture

```text
                     User
                       │
                       ▼
                  paper.pdf
                       │
                       ▼
             Workflow Orchestrator
                       │
 ┌───────────────┬───────────────┬───────────────┐
 │               │               │               │
 ▼               ▼               ▼               ▼
Reader        Planner        Coder         Reporter
                    │
                    ▼
                Runner
                    │
                    ▼
                Reviewer
                    │
                    └───────────────┐
                                    ▼
                                Coder
```

The Orchestrator is the only component responsible for scheduling agents.

Agents never communicate directly.

## 3.1 Implementation Status

For the latest integration benchmarks and limitations, see [CURRENT_STATUS.md](../CURRENT_STATUS.md).

| Capability | Status | Output Artifact |
|------------|--------|-----------------|
| Reader | **Implemented** | `PaperModel` |
| Planner | **Implemented** | `TaskModel` |
| Coder | **Implemented** | `Workspace` |
| Runner | **Implemented** | `ExecutionResult` |
| Verification | **Implemented** | `VerificationResult` |
| Reviewer | **Implemented** | `ReviewReport` |
| PatchPlanner | **Implemented** | `PatchPlan` |
| Reporter | **Implemented** | `ReportModel` |

See [CAPABILITIES.md](CAPABILITIES.md) for component-level detail.

### Canonical Pipeline (Implemented)

```text
Research Paper
        ↓
Reader → PaperModel
        ↓
Planner → TaskModel
        ↓
Coder → Workspace
        ↓
Runner → ExecutionResult
        ↓
VerificationService → VerificationResult
        ↓
Reviewer → ReviewReport
        ↓
PatchPlanner → PatchPlan
        ↓
Reporter → ReportModel
```

The review loop (Coder/Runner retry) is described in Section 4.2.

---

# 4. Workflow

## 4.1 Primary Pipeline

```text
Research Paper (paper.pdf)

↓

Reader

↓

PaperModel

↓

Planner

↓

TaskModel

↓

Coder

↓

Workspace

↓

Runner

↓

ExecutionResult

↓

VerificationService

↓

VerificationResult

↓

Reviewer

↓

ReviewReport

↓

PatchPlanner

↓

PatchPlan

↓

Coder (retry — deferred)

↓

(repeat — not yet enabled)

↓

Reporter

↓

ReportModel
```

## 4.2 Review Loop

`Reviewer` produces a `ReviewReport` from execution and verification context. `PatchPlanner` converts it into a `PatchPlan`. When `requires_patch` is true, a future milestone will re-invoke Coder and Runner. The current orchestrator does **not** re-run Coder or Runner; it exits the loop after one iteration regardless of `requires_patch`.

---

# 5. Core Components

## 5.1 Workflow Orchestrator

Responsibilities

* Execute workflow
* Control execution order
* Retry failed stages
* Maintain workflow state
* Record execution history

The Orchestrator is the brain of the system.

Agents never know each other.

---

## 5.2 Reader

Input

paper.pdf

Output

PaperModel

Responsibilities

Extract structured information from paper.

Examples

* title
* abstract
* method
* dataset
* model
* framework
* optimizer
* loss
* training pipeline
* evaluation metric

Reader never generates code.

### Implementation Status

**Status:** Completed

**Pipeline:**

```text
PDF
  ↓
Raw Text
  ↓
Prompt
  ↓
LLM
  ↓
Structured dict
  ↓
Validation
  ↓
PaperModel
```

**Modules:** `PDFService`, `PromptBuilder`, `LLMProvider`, `ResponseParser`, `validation/paper.py`

---

## 5.3 Planner

Input

PaperModel

Output

TaskModel

Responsibilities

Convert research ideas into executable engineering tasks.

Example

* Build model
* Implement dataset
* Train model
* Evaluate metrics

Planner never writes code.

### Implementation Status

**Status:** Completed

**Pipeline:**

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
TaskModel
```

**Modules:** `PromptBuilder`, `LLMProvider`, `ResponseParser`, `validation/task.py`

---

## 5.4 Coder

Input

PaperModel

TaskModel

Optional PatchPlan

Output

Workspace

Responsibilities

Generate

* project structure
* source code
* configs
* scripts
* README

Coder never executes code.

### Implementation Status

**Status:** Implemented

**Pipeline:**

```text
PaperModel + TaskModel
  ↓
WorkspaceManager.create_workspace()
  ↓
TaskRouter.route_task() → TaskRoutingTable
  ↓
WorkspaceManager.initialize_repository()
  ↓
for each RepositoryTarget:
    PromptBuilder → LLM → WorkspaceManager.write_file()
  ↓
reconcile requirements (GQ-1)
  ↓
validate_generated_repository() + decide_repository_acceptance() (RAG)
  ↓
Workspace (or RepositoryAcceptanceError)
```

**Modules:** `WorkspaceManager`, `TaskRouter`, `PromptBuilder`, `LLMProvider`, `CoderMockLLMProvider`, `agents/coder_quality.py`

---

## 5.5 Runner

Input

Workspace

Output

ExecutionResult

Responsibilities

Coordinate execution:

* environment preparation (`EnvironmentService`)
* execution planning (`ExecutionPlanner`)
* script execution (`ExecutionService`)

Runner never modifies repository source files. Runtime artifact creation is delegated to execution services (see ADR-0006, ADR-0007).

### Implementation Status

**Status:** Implemented

**Pipeline:**

```text
Workspace
  ↓
EnvironmentService.prepare()     → .venv, pip install, environment_preparation.log
  ↓
ExecutionPlanner.plan()        → ExecutionPlan (scripts/train.py)
  ↓
ExecutionService.execute()     → subprocess, execution.log
  ↓
ExecutionResult
```

**Modules:** `EnvironmentService`, `ExecutionPlanner`, `ExecutionService`, `ExecutionPlan`

---

## 5.6 Verification

Input

`Workspace`, `ExecutionResult`

Output

`VerificationResult`

Responsibilities

Deterministic checks on execution outcome (exit code, log signals, artifact presence). Feeds ground truth into Reviewer.

### Implementation Status

**Status:** Implemented

**Module:** `VerificationService` (`services/verification_service.py`)

Invoked by `WorkflowOrchestrator` between Runner and Reviewer. Not a separate printed pipeline stage.

---

## 5.7 Reviewer

Input

`PaperModel`, `TaskModel`, `VerificationResult`

Output

`ReviewReport`

Responsibilities

Analyze runtime failures and implementation mistakes using LLM structured extraction. Produces a review report for PatchPlanner.

Reviewer never edits source code.

### Implementation Status

**Status:** Implemented

**Modules:** `Reviewer`, `PromptBuilder`, `LLMProvider`, `validation/review.py`

---

## 5.8 PatchPlanner

Input

`ReviewReport`

Output

`PatchPlan`

Responsibilities

Convert review findings into a structured repair plan (`requires_patch`, targeted changes).

### Implementation Status

**Status:** Implemented

**Module:** `planning/patch_planner.py`

---

## 5.9 Reporter

Input

Workflow history

Output

report.md

Generate

* reproduction summary
* implementation summary
* execution history
* debugging history
* final status

### Implementation Status

**Status:** Implemented

`Reporter.run()` produces a `ReportModel` from `WorkflowHistory`. `WorkspaceManager.write_report()` persists the report to project `outputs/report.md`.

---

# 6. Artifact Pipeline

Artifacts evolve through the pipeline as typed domain models and on-disk workspace content.

```text
Research Paper (PDF)
        ↓
PaperModel
        ↓
TaskModel
        ↓
Workspace
        ↓
ExecutionResult
        ↓
VerificationResult
        ↓
ReviewReport
        ↓
PatchPlan
        ↓
ReportModel
```

## 6.1 Artifact Definitions

| Artifact | Type | Produced by | Description |
|----------|------|-------------|-------------|
| Research Paper | File (`paper.pdf`) | User input | Source PDF document |
| `PaperModel` | Pydantic model | Reader | Structured paper fields |
| `TaskModel` | Pydantic model | Planner | Ordered engineering tasks |
| `Workspace` | Pydantic model + directory | Coder | Reproduction project root |
| `ExecutionResult` | Pydantic model | Runner | Script execution outcome |
| `VerificationResult` | Pydantic model | VerificationService | Deterministic execution checks |
| `ReviewReport` | Pydantic model | Reviewer | LLM failure analysis |
| `PatchPlan` | Pydantic model | PatchPlanner | Repair strategy for retry loop |
| `ReportModel` | Pydantic model | Reporter | Final workflow report |

## 6.2 On-Disk Artifact Evolution

| Stage | Repository artifacts | Runtime artifacts |
|-------|---------------------|-------------------|
| After Coder | `src/`, `configs/`, `scripts/`, `README.md`, `requirements.txt`, `logs/generation_validation.log`, `logs/repository_acceptance.log` | — |
| After Runner (prep) | unchanged | `.venv/`, `logs/environment_preparation.log` |
| After Runner (execute) | unchanged | `logs/execution.log` |

Repository and runtime artifact ownership is defined in [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md).

---

# 7. Domain Models

Every stage communicates through strongly typed models.

Recommended implementation

Pydantic

Examples

PaperModel

TaskModel

ExecutionResult

PatchPlan

ReportModel

No raw dictionaries should be passed between agents.

---

# 8. Workspace

Every reproduction task owns an independent workspace.

Example

workspace/

```
paper_name/

    src/

    configs/

    scripts/

    logs/

    outputs/

    .venv/
```

A workspace contains two categories of on-disk content with different ownership boundaries. See [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md).

Agents never manipulate files directly. Repository writes go through `WorkspaceManager`. Runtime writes go through execution services invoked by `Runner`.

## 8.1 Repository Artifact Lifecycle

Repository artifacts are the files that constitute the reproduction project design.

**Owner:** `WorkspaceManager`

**Orchestrated by:** `Coder`

**Lifecycle:**

```text
TaskModel
  ↓
Coder.run()
  ↓
WorkspaceManager.create_workspace()        → directory skeleton
WorkspaceManager.store_routing_table()     → routing metadata (in-memory)
WorkspaceManager.initialize_repository()   → README.md, requirements.txt stub
WorkspaceManager.write_file()              → per-target generated files (M4.3)
  ↓
Repository artifacts on disk
```

**Repository artifact paths:**

| Path | Purpose |
|------|---------|
| `src/` | Source modules |
| `configs/` | Configuration files |
| `scripts/` | Executable scripts |
| `README.md` | Project documentation |
| `requirements.txt` | Dependency declaration |

Repository artifacts evolve when `Coder.run()` is invoked, including during review-loop retries.

`WorkspaceManager` methods used: `create_workspace`, `initialize_repository`, `write_file`, `read_file`, `write_output`.

## 8.2 Runtime Artifact Lifecycle

Runtime artifacts are files created when a workspace is prepared or executed.

**Owner:** Runtime services (`EnvironmentService`, `ExecutionService`)

**Orchestrated by:** `Runner`

**Lifecycle:**

```text
Workspace
  ↓
Runner.run()
  ↓
EnvironmentService.prepare()
  ↓
.venv/, logs/environment_preparation.log
  ↓
ExecutionPlanner.plan() → ExecutionPlan
  ↓
ExecutionService.execute()
  ↓
logs/execution.log
  ↓
ExecutionResult
```

**Runtime artifact paths:**

| Path | Purpose | Status |
|------|---------|--------|
| `.venv/` | Python virtual environment | Implemented (M5.1) |
| `logs/environment_preparation.log` | Environment prep log | Implemented (M5.1) |
| `logs/execution.log` | Script execution log | Implemented (M5.2) |
| `outputs/` | Execution run outputs | Reserved |
| `checkpoints/` | Model checkpoints | Reserved |
| `tensorboard/` | Training telemetry | Reserved |

Runtime artifacts evolve when `Runner.run()` is invoked. They are not created or modified by `WorkspaceManager` or `Coder`.

**Note:** `WorkspaceManager.write_output()` writes to `workspace/outputs/` as a repository-scoped output path. Future execution services may also write runtime outputs under `outputs/`. Callers must use the API matching the artifact category.

---

# 9. LLM Layer

The system should never call an LLM SDK directly inside an Agent.

Architecture

```text
Agent

↓

LLM Interface

↓

OpenAI

Claude

Gemini

DeepSeek

...
```

Every model provider should implement the same interface.

Future provider replacement should require zero changes to Agent logic.

---

# 10. Prompt System

Each Agent owns an independent prompt directory.

Example

prompts/

```
reader/

    system.md

    output.md

planner/

coder/

reviewer/
```

Few-shot examples can be added later without modifying workflow logic.

---

# 11. Directory Structure

```text
Research_Agent_MVP/

├── app.py
├── config.py
├── README.md
│
├── workflow/
│   ├── orchestrator.py
│   └── pipeline.py
│
├── agents/
│   ├── reader.py
│   ├── planner.py
│   ├── coder.py
│   ├── coder_quality.py
│   ├── runner.py
│   ├── reviewer.py
│   └── reporter.py
│
├── models/
│   ├── paper.py
│   ├── task.py
│   ├── workspace.py
│   ├── routing.py
│   ├── execution.py
│   ├── execution_plan.py
│   ├── review.py
│   └── report.py
│
├── services/
│   ├── pdf_service.py
│   ├── environment_service.py
│   └── execution_service.py
│
├── execution/
│   └── execution_planner.py
│
├── planning/
│   └── patch_planner.py
│
├── routing/
│   └── task_router.py
│
├── validation/
│
├── llm/
│
├── workspace/
│   └── manager.py
│
├── prompt/
│
├── prompts/
│
├── docs/
│
└── tests/
```

---

# 12. Design Principles

1. Single Responsibility

Each component has one responsibility.

2. Stateless Agents

Agents never share internal state.

3. Artifact-based Communication

Agents communicate only through typed artifacts.

4. Replaceability

Any component can be replaced independently.

5. Reproducibility

Every execution should be reproducible.

6. Traceability

Every decision should be recorded.

7. Extensibility

Future modules should integrate without redesigning the architecture.

---

# 13. Future Roadmap

See [docs/roadmap/ROADMAP.md](../roadmap/ROADMAP.md) for the current milestone timeline and post-MVP plans.

The original vision below is retained for historical context:

v0.1

Single-paper autonomous reproduction

↓

v0.2

GitHub repository initialization

↓

v0.3

Multi-model support

↓

v0.4

Memory & Retrieval

↓

v0.5

Human-in-the-loop

↓

v0.6

Multi-agent collaboration

↓

v1.0

Autonomous AI Research Assistant
