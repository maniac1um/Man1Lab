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

## Phase 2 — Planning Capability

**Status:** Not Started

Planner development begins after Reader capability closure. See [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) for Planner philosophy.

### M3.1 — Engineering Task Planning

**Status:** Planned

Convert `PaperModel` into an executable `TaskModel` using LLM-backed engineering task decomposition.

### M3.2 — Task Validation

**Status:** Planned

Validate `TaskModel` structure, required fields, and task ordering before passing to Coder.

### M3.3 — Planner Integration

**Status:** Planned

Integrate Planner into the workflow with prompt infrastructure and end-to-end smoke test verification.

---

## M4 — Coder

**Status:** Planned

Generate project source code, configs, and scripts into an isolated workspace from `PaperModel` and `TaskModel`.

---

## M5 — Runner

**Status:** Planned

Execute generated code (install dependencies, run training, run tests) and produce `ExecutionResult`.

---

## M6 — Reviewer

**Status:** Planned

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
