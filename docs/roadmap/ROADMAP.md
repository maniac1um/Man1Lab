# ResearchAgent Roadmap

Long-term development plan for the ResearchAgent autonomous paper-reproduction framework.

For milestone workflow and acceptance criteria, see [MILESTONES.md](MILESTONES.md).

---

## M1 — Framework Skeleton

**Status:** Completed

Establish the project architecture: six agents, `WorkflowOrchestrator`, Pydantic domain models, LLM provider abstraction, `WorkspaceManager`, and an executable mock end-to-end pipeline.

**Delivered:** Project skeleton, typed inter-agent models, workflow orchestration, placeholder agent implementations, smoke test.

---

## M2 — Reader

**Status:** Completed

Build the document ingestion and paper-understanding pipeline for the Reader agent.

### M2.1 — PDF Ingestion

**Status:** Completed

Implement `PDFService` for PDF text extraction with typed error handling and logging.

### M2.1.8 — Reader Interface Stabilization

**Status:** Completed

Restore `Reader.run() -> PaperModel` while delegating extraction to `PDFService` via `read_text()`.

### M2.1.8 — Prompt Infrastructure

**Status:** Completed

Implement `PromptLoader` and `PromptBuilder`; integrate Reader with centralized prompt composition.

### M2.1.9 — Project Governance

**Status:** Completed

Establish documentation structure, ADRs, development workflow, and architecture freeze policy.

### M2.2 — Structured Paper Extraction

**Status:** Completed

Integrate LLM provider and `ResponseParser` to produce a structured extraction dict from PDF text.

### M2.3 — Validation and PaperModel Construction

**Status:** Completed

Validate extracted data, apply lightweight normalization, and construct a real `PaperModel` from LLM output.

---

## M3 — Planner

**Status:** Completed

Build the engineering task planning pipeline for the Planner agent. See [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) and [ADR-0005](../adr/ADR-0005-Planner-Capability.md).

### M3.1 — Structured Task Extraction

**Status:** Completed

Integrate LLM provider and `ResponseParser` to produce a structured task extraction dict from `PaperModel`.

### M3.2 — Task Validation and TaskModel Construction

**Status:** Completed

Validate extracted tasks, apply lightweight normalization, and construct a real `TaskModel` from LLM output.

---

## Phase 3 — Coder Capability

**Status:** Completed

Build and populate reproduction workspaces from engineering tasks.

### M4.1 — Workspace Construction

**Status:** Completed

Create repository skeleton via `WorkspaceManager`.

### M4.2 — Task Routing

**Status:** Completed

Deterministic `TaskRouter` maps `TaskStep` to `RepositoryTarget`.

### M4.3 — Repository Population

**Status:** Completed

Per-target LLM file generation through `WorkspaceManager`.

---

## Phase 4 — Runner Capability

**Status:** Completed

Prepare workspace environment and execute reproduction scripts.

### M5.1 — Environment Preparation

**Status:** Completed

`EnvironmentService` creates `.venv` and installs `requirements.txt`.

### M5.1.1 — Runtime Artifact Ownership

**Status:** Completed

Document repository vs runtime artifact boundaries (ADR-0006).

### M5.2 — Script Execution

**Status:** Completed

`ExecutionPlanner` and `ExecutionService` execute `scripts/train.py`.

### M5.F — Capability Freeze

**Status:** Completed

Architecture documentation consolidation before M6.

---

## M6 — Reviewer

**Status:** Next

Analyze execution failures and produce `PatchPlan` for automated repair iterations.

---

## M7 — Reporter

**Status:** Planned

Generate structured final reports from `WorkflowHistory`; persist via `WorkspaceManager`.

---

## M8 — MVP Release

**Status:** Planned

Deliver a stable single-paper autonomous reproduction pipeline with real LLM integration, code execution, review loop, and final reporting.

---

## Post-MVP (Future)

| Version | Focus |
|---------|-------|
| v0.2 | GitHub repository initialization |
| v0.3 | Multi-model LLM support |
| v0.4 | Memory and retrieval |
| v0.5 | Human-in-the-loop |
| v0.6 | Multi-agent collaboration |
| v1.0 | Autonomous AI Research Assistant |

See [docs/architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) Section 12 for the original vision roadmap.
