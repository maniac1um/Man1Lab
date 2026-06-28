# ARCHITECTURE.md

# ResearchAgent MVP v0.1

## 1. Vision

ResearchAgent is an autonomous paper reproduction framework.

The objective of MVP v0.1 is to reproduce a single research paper through an autonomous workflow.

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

---

# 4. Workflow

```text
paper.pdf

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

Reviewer

↓

PatchPlan

↓

Coder

↓

(repeat)

↓

Reporter

↓

Final Report
```

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

---

## 5.5 Runner

Input

Workspace

Output

ExecutionResult

Responsibilities

Run

* pip install
* pytest
* python train.py

Collect

* stdout
* stderr
* execution time
* exit code

Runner never modifies files.

---

## 5.6 Reviewer

Input

ExecutionResult

Output

PatchPlan

Responsibilities

Analyze

* runtime errors
* implementation mistakes
* repair strategy

Reviewer never edits source code.

---

## 5.7 Reporter

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

---

# 6. Domain Models

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

# 7. Workspace

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
```

Agents never manipulate files directly.

All file operations are managed by WorkspaceManager.

---

# 8. LLM Layer

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

# 9. Prompt System

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

# 10. Directory Structure

```text
research-agent/

├── app.py
├── config.py
│
├── workflow/
│   ├── orchestrator.py
│   └── pipeline.py
│
├── agents/
│   ├── reader.py
│   ├── planner.py
│   ├── coder.py
│   ├── runner.py
│   ├── reviewer.py
│   └── reporter.py
│
├── models/
│   ├── paper.py
│   ├── task.py
│   ├── execution.py
│   ├── review.py
│   └── report.py
│
├── llm/
│   ├── provider.py
│   ├── openai_provider.py
│   └── anthropic_provider.py
│
├── workspace/
│   ├── manager.py
│   └── tasks/
│
├── prompts/
│
├── tools/
│
├── outputs/
│
├── logs/
│
└── tests/
```

---

# 11. Design Principles

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

# 12. Future Roadmap

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
