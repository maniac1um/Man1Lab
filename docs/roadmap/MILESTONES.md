# Milestones

Development workflow and milestone specification for ResearchAgent.

For the high-level timeline, see [ROADMAP.md](ROADMAP.md).

---

## Capability Completion Criteria

A capability milestone is considered complete only when:

* production implementation exists
* tests pass
* design review completed
* ADR updated (if required)
* committed to repository

---

## Milestone Lifecycle

Every milestone follows this lifecycle:

```text
Design
  ↓
Implementation
  ↓
Design Review
  ↓
Architecture Review
  ↓
ADR (if required)
  ↓
Git Commit
  ↓
Next Milestone
```

### Design

Define goal, scope, acceptance criteria, and deliverables before writing code. Identify which frozen interfaces are affected.

### Implementation

Implement only what is in scope. Do not expand architecture without an ADR.

### Design Review

Produce a factual design review report covering APIs, dependencies, tests, limitations, and changed files. Store under `docs/reviews/`.

### Architecture Review

Verify alignment with [ARCHITECTURE.md](../architecture/ARCHITECTURE.md), ADRs, and the architecture freeze policy in [DEVELOPMENT.md](../../DEVELOPMENT.md).

### ADR (if required)

Create an ADR when a decision affects architecture, public interfaces, or cross-cutting concerns. See [docs/adr/README.md](../adr/README.md).

### Git Commit

Commit with Conventional Commits format. One logical milestone per commit when possible.

### Next Milestone

Update `ROADMAP.md` milestone status before starting the next milestone.

---

## Milestone Template

Each milestone document should include:

### Goal

One paragraph describing the purpose.

### Scope

What is included and explicitly excluded.

### Acceptance Criteria

Verifiable conditions for completion.

### Deliverables

Concrete artifacts: code, tests, documentation, review reports.

---

## Completed Capabilities

### Reader (M2) — Complete

The Reader capability is complete. It ingests a PDF, extracts structured paper information via LLM, validates and normalizes the result, and returns a `PaperModel`.

Sub-milestones completed: M2.1 (PDF Ingestion), M2.1.8 (Interface Stabilization, Prompt Infrastructure), M2.1.9 (Governance), M2.2 (Structured Extraction), M2.3 (Validation and PaperModel Construction).

### Planner (M3) — Complete

The Planner capability is complete. It receives a `PaperModel`, extracts structured engineering tasks via LLM, validates and normalizes the result, and returns a `TaskModel`.

Sub-milestones completed: M3.1 (Structured Task Extraction), M3.2 (Task Validation and TaskModel Construction).

---

## Completed Milestones

### M1 — Framework Skeleton

**Goal:** Build an executable architecture skeleton with all modules connected via typed models.

**Scope:** Agents, orchestrator, models, LLM abstraction, workspace manager, mock pipeline. No real PDF parsing, LLM calls, or code execution.

**Acceptance Criteria:**
- Complete directory structure per architecture document
- `python app.py` completes without error
- Pydantic models between all agent stages
- Smoke test passes

**Deliverables:** Project skeleton, `ARCHITECTURE.md`, unit/smoke tests.

---

### M2.1 — PDF Ingestion

**Goal:** Establish a reliable PDF text extraction pipeline.

**Scope:** `PDFService`, extraction tests, logging. No LLM, no `PaperModel` generation.

**Acceptance Criteria:**
- `PDFService.extract()` returns normalized text
- Typed exceptions for missing, empty, encrypted, and failed PDFs
- Unit tests for all error cases

**Deliverables:** `services/pdf_service.py`, `tests/test_pdf_service.py`, design review report.

---

### M2.1.8 — Reader Interface Stabilization

**Goal:** Restore stable `Reader` public API while preserving `PDFService`.

**Scope:** `read_text() -> str`, `run() -> PaperModel` with placeholder model. Full workflow restored.

**Acceptance Criteria:**
- `Reader.run()` returns `PaperModel`
- `PDFService` remains sole PDF reader
- Smoke test passes

**Deliverables:** Refactored `Reader`, restored smoke test, design review report.

---

### M2.1.8 — Prompt Infrastructure

**Goal:** Centralize prompt loading and composition for all future agents.

**Scope:** `PromptLoader`, `PromptBuilder`, Reader integration. No LLM calls.

**Acceptance Criteria:**
- Prompt file paths hidden from `Reader`
- `PromptBuilder.build_reader_prompt()` composes sections in order
- Prompt unit tests pass
- Workflow still executable

**Deliverables:** `prompt/` module, prompt resource files, tests, design review report.

---

### M2.1.9 — Project Governance

**Goal:** Establish long-term documentation and engineering workflow.

**Scope:** `docs/` structure, ADRs, `DEVELOPMENT.md`, roadmap. No business logic changes.

**Acceptance Criteria:**
- Complete `docs/` tree
- Three ADRs documenting key decisions
- Development workflow documented
- Architecture freeze policy documented

**Deliverables:** Governance documentation, governance report.

---

### M2.2 — Structured Paper Extraction

**Goal:** Produce a structured extraction dict from PDF text via LLM.

**Scope:** LLM integration in Reader, `ResponseParser`, tests. No `PaperModel` population.

**Acceptance Criteria:**
- Reader invokes LLM and ResponseParser
- Structured dict stored internally
- Placeholder `PaperModel` still returned
- All tests pass

**Deliverables:** `llm/response_parser.py`, updated `Reader`, tests, design review report.

---

### M2.3 — Validation and PaperModel Construction

**Goal:** Transform structured extraction dict into a validated `PaperModel`.

**Scope:** `validation/paper.py`, normalization, real `PaperModel` construction. No Planner changes.

**Acceptance Criteria:**
- `Reader.run()` returns real `PaperModel`
- Placeholder implementation removed
- `PaperValidationError` on invalid data
- Workflow executable

**Deliverables:** `validation/` module, updated `Reader`, tests, design review report.

---

### M3.1 — Structured Task Extraction

**Goal:** Produce a structured task extraction dict from `PaperModel` via LLM.

**Scope:** LLM integration in Planner, `ResponseParser`, prompt resources, tests. No `TaskModel` population.

**Acceptance Criteria:**
- Planner invokes PromptBuilder, LLM, and ResponseParser
- Structured task dict stored internally
- Placeholder `TaskModel` still returned
- All tests pass

**Deliverables:** Updated `Planner`, planner prompt resources, tests, design review report.

---

### M3.2 — Task Validation and TaskModel Construction

**Goal:** Transform structured task extraction dict into a validated `TaskModel`.

**Scope:** `validation/task.py`, normalization, real `TaskModel` construction. No Coder changes.

**Acceptance Criteria:**
- `Planner.run()` returns real `TaskModel`
- Placeholder implementation removed
- `TaskValidationError` on invalid data
- Workflow executable

**Deliverables:** `validation/task.py`, updated `Planner`, tests, design review report.

---

## Planned Milestones

### Phase 3 — Coder Capability

**Status:** Not Started

### M4.1 — Workspace Population

**Goal:** Populate reproduction workspaces from `PaperModel` and `TaskModel` via `WorkspaceManager`.

### M4.2 — Structured Code Generation

**Goal:** Generate project source code, configs, and scripts using LLM-backed structured extraction.

### M4.3 — Coder Capability Review

**Goal:** Validate Coder capability, synchronize documentation, and record architectural decisions.

### M5 — Runner

**Goal:** Execute generated code and collect `ExecutionResult`.

### M6 — Reviewer

**Goal:** Analyze failures and produce `PatchPlan` for retry loop.

### M7 — Reporter

**Goal:** Produce final structured report from workflow history.

### M8 — MVP Release

**Goal:** End-to-end autonomous single-paper reproduction with real integrations.
