# Contributing to Man1Lab

Man1Lab is an **autonomous research paper reproduction platform** — a research prototype with a milestone-driven architecture. This guide explains how the repository is organized, how to set up a development environment, and what we expect from contributors.

For user installation, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md). For maintainer governance, see [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Project Overview

Man1Lab reads a research PDF and runs a structured pipeline:

```text
Paper (PDF)
    ↓
PaperReproductionAnalysis       ← Analysis
    ↓
ResearchResourceDiscovery       ← Discovery
    ↓
ExecutionStrategy               ← Execution Planning
    ↓
TaskModel → Workspace → ExecutionResult → ReportModel
```

Public entry points:

| Interface | Location | Contract |
|-----------|----------|----------|
| **CLI** | `interfaces/cli/` | Delegates to `Man1Lab` facade only |
| **Python SDK** | `man1lab/` | `from man1lab import Man1Lab` |
| **Platform Facade** | `application/facade.py` | Composition root for all capabilities |

Business logic lives in **workflows**, **services**, and **agents** — not in CLI or SDK modules.

---

## Repository Architecture

```text
Interfaces (CLI · SDK · future MCP/REST)
        ↓
Man1Lab (Platform Facade)
        ↓
Lifecycle · LLMManager · TrackedWorkflowOrchestrator
        ↓
Workflow → Service → Port → Provider
```

### Layer responsibilities

| Layer | Role | Examples |
|-------|------|----------|
| **Platform Facade** | Single composition root; wires configuration, tracking, workflows | `Man1Lab.init()`, `reproduce()`, `doctor()` |
| **Workflow** | Orchestrates capability stages; owns stage ordering | `WorkflowOrchestrator`, `DiscoveryWorkflow`, `ExecutionPlanningWorkflow` |
| **Service** | Business operations behind a workflow stage | `ExecutionPlanner`, `VerificationService` |
| **Port** | Infrastructure boundary (protocol / adapter) | `DocumentParser`, `ExperimentTracker`, `LLMProvider` |
| **Provider** | External or embedded implementation behind a port | GitHub discovery providers, OpenAI/Anthropic LLM adapters, embedded Execution Planning providers |

Additional platform components:

| Component | Role |
|-----------|------|
| **Model Registry** | Named LLM profiles, active profile, persistence (`providers/llm/`) |
| **Execution Planning** | Six embedded providers → Decision Foundation → `ExecutionStrategy` |
| **Lifecycle** | `init`, `doctor`, `clean` — workspace setup and validation |

Full design: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) · Execution Planning: [docs/architecture/EXECUTION_PLANNING.md](docs/architecture/EXECUTION_PLANNING.md)

---

## Development Workflow

Man1Lab follows a **milestone-driven, architecture-first** process:

```text
Design → Implementation → Review → ADR (if required) → Tests → Documentation → Commit
```

Before changing code:

1. Read [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) for what is implemented today.
2. Check [docs/adr/README.md](docs/adr/README.md) for accepted decisions.
3. Confirm your change respects frozen interfaces ([DEVELOPMENT.md](DEVELOPMENT.md#architecture-freeze)).
4. Prefer extending existing abstractions over adding parallel paths.

Architectural changes require an ADR. Interface changes to frozen agents require an ADR and architecture review.

---

## Development Environment

### Prerequisites

- **Python 3.10+** (Pixi installs 3.12 by default)
- **[Pixi](https://pixi.sh/)** — recommended for contributors
- Git

### Installation for contributors

```bash
git clone https://github.com/maniac1um/Man1Lab.git
cd Man1Lab
pixi install
```

Verify the environment:

```bash
pixi run man1lab --version
pixi run test
```

### Common commands

| Task | Command |
|------|---------|
| Run full test suite | `pixi run test` |
| Run CLI | `pixi run man1lab <command>` |
| Legacy maintainer entry | `pixi run run` |
| Integration test (API key required) | `pixi run integration` |
| Build distribution packages | `pixi run python -m build` |
| Editable pip install | `pip install -e .` |

Initialize a workspace for manual testing:

```bash
pixi run man1lab init
pixi run man1lab doctor
```

---

## Coding Principles

### Dependency rules

These boundaries are enforced by convention and AST tests:

| Rule | Rationale |
|------|-----------|
| **CLI must delegate through the Facade** | `interfaces/cli/` imports `application` only — never workflow, agents, or providers |
| **SDK must delegate through the Facade** | `man1lab` package wraps `Man1Lab` — no direct orchestrator imports |
| **Workflow must not import providers directly** | Workflows call services; services resolve providers through registries |
| **Business agents must not call vendor SDKs** | LLM access flows through `LLMManager` → `ModelRegistry` → `ProviderRegistry` |
| **Providers stay isolated** | Provider adapters live under `providers/`; no workflow imports |

```text
CLI / SDK
    ↓
Platform Facade
    ↓
LLMManager → ModelRegistry → ProviderRegistry → LLMProvider
WorkflowOrchestrator → Services → Ports → Providers
```

### General guidelines

- Match existing naming, types, and module layout in the area you edit.
- Keep changes scoped to the task — avoid drive-by refactors.
- Prefer self-explanatory code; comment only non-obvious business logic.
- Do not commit secrets, API keys, runtime artifacts (`outputs/`, `logs/`, `workspace/tasks/`), or large datasets.

---

## Testing Expectations

All changes should keep the test suite green.

```bash
pixi run test
```

| Expectation | Detail |
|-------------|--------|
| **Unit tests** | Add or update tests for new behavior in `tests/` |
| **No real API calls in unit tests** | Mock LLM and external providers |
| **Boundary tests** | CLI and SDK import restrictions are tested — do not break them |
| **Regression** | 614+ tests should pass before submitting |

Relevant test modules: `test_cli.py`, `test_sdk.py`, `test_platform_facade.py`, `test_model_cli.py`, `test_init_wizard.py`.

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>
```

| Type | Use |
|------|-----|
| `feat` | New capability or feature |
| `fix` | Bug fix |
| `refactor` | Internal change without behavior change |
| `test` | Test additions or fixes |
| `docs` | Documentation only |
| `chore` | Tooling, build, maintenance |

Scopes: `cli`, `facade`, `workflow`, `discovery`, `execution-planning`, `llm`, `model-registry`, etc.

Write complete sentences focused on **why**, not just what changed.

---

## Pull Requests

### Before opening a PR

1. Open a [GitHub Issue](https://github.com/maniac1um/Man1Lab/issues) or Discussion to align on scope — especially for features or architectural changes.
2. Keep PRs focused and reviewable.
3. Run `pixi run test` locally.
4. Update documentation when behavior or public contracts change.

### PR checklist

- [ ] Tests pass (`pixi run test`)
- [ ] No breaking changes to public CLI or SDK API without discussion
- [ ] No workflow-layer dependency violations (CLI → Facade only)
- [ ] Documentation updated if user-facing behavior changed
- [ ] ADR added or updated for architectural decisions

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) when opening a PR.

> **Note:** Man1Lab is maintainer-led research software. Large or unscoped PRs may be declined. Start with an issue describing the problem and proposed approach.

---

## Issues and Support

| Need | Channel |
|------|---------|
| Bug reports | [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) — use the bug template |
| Feature ideas | [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) — use the feature template |
| Questions | [GitHub Discussions](https://github.com/maniac1um/Man1Lab/discussions) (if enabled) or Issues with the `question` label |
| Security vulnerabilities | [SECURITY.md](SECURITY.md) — **never** open a public issue |

See [SUPPORT.md](SUPPORT.md) for channel guidance.

---

## Reading the Codebase

| Document | Purpose |
|----------|---------|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | Install, init, doctor, reproduce |
| [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | Capabilities, tests, limitations |
| [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | Platform architecture |
| [docs/architecture/EXECUTION_PLANNING.md](docs/architecture/EXECUTION_PLANNING.md) | Execution Planning design |
| [docs/adr/README.md](docs/adr/README.md) | Architecture Decision Records |
| [docs/reviews/README.md](docs/reviews/README.md) | Phase implementation audits |
| [ROADMAP.md](ROADMAP.md) | Milestones |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Maintainer engineering workflow |

---

## Documentation Policy

Man1Lab maintains two documentation layers: **public** (version-controlled on GitHub) and **private** (local only, not committed).

### Public documentation (in Git)

| Category | Location |
|----------|----------|
| Architecture Decision Records | `docs/adr/` |
| Architecture | `docs/architecture/` |
| User / developer guides | `docs/`, root |
| Release notes | `docs/releases/` |
| Current status | `docs/CURRENT_STATUS.md` |

**Rule:** Final architecture decisions become **ADRs**. ADRs are the durable audit trail.

### Private documentation (local only)

Research process documents stay in `private/` (gitignored): adoption reviews, working roadmaps, benchmark drafts, meeting notes.

**Rule:** Technology reviews inform ADRs; they do not replace ADRs.

Full policy: [docs/README.md](docs/README.md#documentation-classification) · [DEVELOPMENT.md](DEVELOPMENT.md)

---

## Architecture-First Philosophy

Man1Lab prioritizes **clear boundaries** over convenience shortcuts:

- Interfaces stay thin; the Facade owns composition.
- Capabilities produce **canonical artifacts** (`PaperReproductionAnalysis`, `ExecutionStrategy`, etc.).
- Providers are swappable; workflows stay provider-agnostic.
- Configuration flows through Hydra and the Model Registry — CLI does not edit YAML directly.

When in doubt, read the architecture document before writing code.

Thank you for helping improve Man1Lab.
