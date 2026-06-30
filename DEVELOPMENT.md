# Development Guide

Engineering workflow and governance for the Man1Lab repository.

---

## Project Lifecycle

Man1Lab follows a milestone-driven lifecycle:

```text
Design → Implementation → Design Review → Architecture Review → ADR (if required) → Git Commit → Next Milestone
```

Each milestone is scoped, implemented, reviewed, and committed before the next begins. Milestone specification: `private/roadmap/MILESTONES.md` (local).

---

## Milestone Workflow

### 1. Design

Before writing code:

- Read [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- Check [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) for current implementation state
- Check `private/roadmap/ROADMAP.md` (local) for milestone timeline
- Identify affected frozen interfaces (see Architecture Freeze below)
- Define goal, scope, acceptance criteria, and deliverables

### 2. Implementation

- Implement only what is in scope
- Do not modify frozen interfaces without an ADR
- Add tests for new behavior
- Keep modules under ~150 lines when reasonable

### 3. Design Review

Produce a factual design review report covering:

- Architecture flow
- Public APIs
- Dependency graph
- Test coverage
- Current limitations
- Changed files

Store under `private/design/drafts/milestones/{milestone}/` (local, gitignored).

### 4. Architecture Review

Verify:

- Alignment with architecture document
- Compliance with active ADRs
- No unauthorized interface changes
- No circular imports
- Agents remain isolated

### 5. ADR (if required)

Create an ADR when the decision is architectural or affects a frozen interface. See [docs/adr/README.md](docs/adr/README.md).

### 6. Git Commit

Commit using Conventional Commits (see Commit Policy below).

### 7. Next Milestone

Update milestone status in `private/roadmap/ROADMAP.md` (local).

---

## Code Review Process

Reviews occur at milestone boundaries, not necessarily per pull request during solo development.

A code review should verify:

| Check | Question |
|-------|----------|
| Scope | Does the change match the milestone scope? |
| Architecture | Does it follow ADRs and the architecture document? |
| Interfaces | Are frozen interfaces unchanged? |
| Tests | Do all tests pass? Are new behaviors tested? |
| Documentation | Are ADRs, roadmap, and reviews updated? |

Review artifacts are stored in `private/` per [Documentation Policy](CONTRIBUTING.md#documentation-policy).

---

## ADR Process

1. Identify whether the change requires an ADR (see [docs/adr/README.md](docs/adr/README.md))
2. Copy the ADR template
3. Assign the next sequential number
4. Set status to `Proposed` during discussion, `Accepted` when merged
5. Add entry to the ADR index in `docs/adr/README.md`
6. Reference the ADR in the milestone design review

---

## Commit Policy

### Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```text
<type>(<scope>): <description>

[optional body]
```

### Types

| Type | Use |
|------|-----|
| `feat` | New feature or milestone capability |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build, tooling, or maintenance |

### Scopes

Use module or agent names: `reader`, `prompt`, `workflow`, `adr`, `pdf`, `planner`, etc.

### Examples

```text
feat(reader): add PDFService integration via read_text()
refactor(prompt): centralize prompt loading in PromptLoader
docs(adr): add ADR-0003 Prompt Infrastructure
test(reader): verify PromptBuilder integration
fix(workflow): correct review loop termination condition
docs(governance): add DEVELOPMENT.md and docs structure
```

### Rules

- One logical milestone per commit when possible
- Do not commit runtime artifacts (`workspace/tasks/*`, `outputs/*`, `logs/*`)
- Do not commit secrets or API keys
- Write commit messages in complete sentences focusing on *why*

---

## Architecture Freeze

### Concept

Public interfaces are considered **stable** after architecture review. Internal implementation may change; public contracts must not.

Changing a frozen interface requires:

1. A new ADR documenting the change and rationale
2. Architecture review
3. Explicit justification in the milestone design review

### Currently Frozen Interfaces

| Component | Frozen Contract |
|-----------|-----------------|
| `WorkflowOrchestrator` | Constructor signature; `run(paper_path: Path) -> ReportModel` |
| `PromptBuilder` | Public builder methods (e.g. `build_reader_prompt() -> str`) |
| `PromptLoader` | `load(agent: str, section: str) -> str` |
| `WorkspaceManager` | `create_workspace`, `write_file`, `read_file`, `write_output`, `write_report` |
| `Reader` | `read_text(paper_path: Path) -> str`; `run(paper_path: Path) -> PaperReproductionAnalysis` ([ADR-0009](docs/adr/ADR-0009-Analysis-Canonical-Artifact.md)) |
| `Planner` | `run(analysis: PaperReproductionAnalysis) -> TaskModel` |
| `Coder` | `run(analysis, task, patch_plan=None) -> Workspace` |
| `Runner` | `run(workspace: Workspace) -> ExecutionResult` |

### Not Frozen

- Internal agent implementation details
- Placeholder/mock return values
- Private methods and attributes (e.g. `Reader._last_prompt`)
- Test fixtures
- Prompt file content under `prompts/`

### Repository and Runtime Artifact Ownership

Repository files and runtime artifacts have different ownership boundaries.

- **Repository files** evolve through `Coder` and are written exclusively via `WorkspaceManager`.
- **Runtime artifacts** evolve through `Runner` and future execution services (currently `EnvironmentService`).

Do not route runtime artifact creation (virtual environments, execution logs, checkpoints, telemetry) through `WorkspaceManager`. Do not route repository file generation through execution services.

See [ADR-0006](docs/adr/ADR-0006-Runtime-Artifact-Ownership.md) and [Architecture §8](docs/architecture/ARCHITECTURE.md#8-workspace).

### Capability Freeze (M5.F)

As of M5.F, the following capabilities are considered complete for MVP baseline:

- **Reader** — `PaperReproductionAnalysis` extraction pipeline
- **Planner** — `TaskModel` planning pipeline
- **Coder** — workspace construction and population
- **Runner** — environment preparation and script execution

Public interfaces for these frozen capabilities must not change without ADR and architecture review.

Post-M5 capabilities (Verification, Reviewer, PatchPlanner, Reporter, Coder quality layers) are documented in [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) and [CAPABILITIES.md](docs/architecture/CAPABILITIES.md).

See [CAPABILITIES.md](docs/architecture/CAPABILITIES.md) for the capability reference. Status tables in ARCHITECTURE.md are synchronized with CURRENT_STATUS during release governance; historical milestone reviews remain frozen snapshots.

---

## Repository Layout

```text
Man1Lab/
├── app.py                  # Composition root
├── config.py               # Configuration constants
├── pixi.toml               # Official environment (Pixi)
├── requirements.txt        # Legacy pip compatibility layer
├── tracking/               # Experiment tracking (MLflow adapter)
├── DEVELOPMENT.md          # This file
├── ARCHITECTURE.md         # Pointer to canonical architecture doc
├── docs/
│   ├── README.md           # Documentation index
│   ├── GETTING_STARTED.md  # Contributor quick start
│   ├── CURRENT_STATUS.md   # Implementation status (single source of truth)
│   ├── architecture/       # Architecture document
│   ├── adr/                # Architecture Decision Records
│   ├── reviews/            # Migration pointer (work docs in private/)
│   └── api/                # API reference
├── private/                # Local work documents (gitignored)
├── agents/                 # Agent implementations
├── models/                 # Pydantic domain models
├── workflow/               # Orchestrator and pipeline
├── services/               # Cross-cutting services (PDF, environment, execution)
├── execution/              # ExecutionPlanner
├── planning/               # PatchPlanner
├── routing/                # TaskRouter
├── prompt/                 # Prompt loader and builder
├── prompts/                # Prompt resource files
├── llm/                    # LLM provider abstraction
├── workspace/              # Workspace manager
└── tests/                  # Unit and integration tests
```

---

## Running the Project

### Recommended — Pixi

```bash
pixi install
pixi run test
pixi run run
```

### Legacy — pip

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python app.py
```

Set `PAPER_PATH` to override the default `paper.pdf` location.

---

## Further Reading

| Document | Location |
|----------|----------|
| **Current status** | [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) |
| **Getting started** | [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Capabilities | [docs/architecture/CAPABILITIES.md](docs/architecture/CAPABILITIES.md) |
| ADRs | [docs/adr/README.md](docs/adr/README.md) |
| Private work docs | [CONTRIBUTING.md § Documentation Policy](CONTRIBUTING.md#documentation-policy) |
| Reviews pointer | [docs/reviews/README.md](docs/reviews/README.md) |
