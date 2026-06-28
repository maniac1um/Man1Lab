# ADR-0006 — Runtime Artifact Ownership

## Status

Accepted

## Date

2026-06-28

## Context

ResearchAgent workspaces contain two distinct categories of on-disk content:

1. **Repository artifacts** — source code, configuration, documentation, and dependency declarations produced during the Coder stage.
2. **Runtime artifacts** — environments, logs, execution outputs, and other files created when the workspace is prepared or executed.

Milestone M5.1 introduced `EnvironmentService`, which creates `.venv/` and writes `logs/environment_preparation.log` inside the workspace. These operations are intentionally performed outside `WorkspaceManager`.

The implementation is correct, but the architectural contract was implicit. Section 7 of `ARCHITECTURE.md` previously stated that all file operations are managed by `WorkspaceManager`, which no longer reflects the full system after M5.1.

This ADR documents the ownership boundary as an explicit architectural decision.

## Decision

### Repository artifacts

Repository artifacts are managed **exclusively** by `WorkspaceManager`.

`Coder` orchestrates repository construction and population but never calls filesystem APIs directly. All repository writes go through `WorkspaceManager` methods (`create_workspace`, `initialize_repository`, `write_file`, `read_file`, `write_output`).

**Examples:**

| Path | Category |
|------|----------|
| `src/` | Source modules |
| `configs/` | Configuration files |
| `scripts/` | Executable scripts |
| `README.md` | Project documentation |
| `requirements.txt` | Dependency declaration |

Repository artifacts represent the **intended reproduction project**. They evolve through the Coder capability and optional Coder retry paths in the review loop.

### Runtime artifacts

Runtime artifacts are managed by **runtime services**, not `WorkspaceManager`.

`Runner` orchestrates execution-stage services. The current runtime service is `EnvironmentService` (M5.1). Future execution services may manage additional runtime paths.

**Examples:**

| Path | Category | Current owner |
|------|----------|---------------|
| `.venv/` | Python virtual environment | `EnvironmentService` |
| `logs/` | Execution and preparation logs | `EnvironmentService` |
| `outputs/` (execution outputs within workspace) | Run outputs | Reserved for future execution services |
| `checkpoints/` | Model checkpoints | Reserved for future execution services |
| `tensorboard/` | Training telemetry | Reserved for future execution services |

Runtime artifacts represent **what happened when the workspace was prepared or executed**. They evolve through `Runner` and future execution services.

### Why runtime artifacts are excluded from WorkspaceManager

1. **Different lifecycle.** Repository artifacts are designed and versioned as part of reproduction planning. Runtime artifacts are ephemeral side effects of execution and may be regenerated without changing the repository design.

2. **Different agents.** `WorkspaceManager` serves the Coder agent. Runtime services serve the Runner agent. Mixing both responsibilities in one component would couple code generation to execution infrastructure.

3. **Different operations.** Repository management involves structured skeleton creation, routing metadata, and LLM-driven file population. Runtime management involves subprocess execution, environment provisioning, and log capture.

4. **Separation of concerns.** `EnvironmentService` owns subprocess invocation and preparation logging. `WorkspaceManager` owns repository layout and repository file I/O. Each component has a single, clear responsibility.

5. **Future execution services.** Training, evaluation, and checkpoint management will add more runtime artifact types. Keeping them outside `WorkspaceManager` avoids expanding the repository filesystem API with execution-specific methods.

Agents never manipulate files directly. Repository writes go through `WorkspaceManager`. Runtime writes go through runtime services invoked by `Runner`.

## Alternatives Considered

**Extend WorkspaceManager with runtime methods** (`create_venv`, `write_log`). Rejected; would merge Coder and Runner filesystem responsibilities into one class and blur the repository/runtime boundary.

**Runner writes runtime files directly.** Rejected; same pattern as Coder — Runner should delegate to services (`EnvironmentService`), not perform I/O inline.

**Store runtime artifacts outside the workspace.** Rejected for MVP; runtime artifacts remain co-located with the reproduction project for discoverability, but ownership is still assigned to runtime services.

## Consequences

**Positive:**

- Clear ownership: Coder → repository artifacts via `WorkspaceManager`; Runner → runtime artifacts via execution services
- `WorkspaceManager` frozen interface remains focused on repository operations
- New execution capabilities can add services without modifying `WorkspaceManager`
- Documentation matches current M5.1 implementation

**Negative:**

- Two filesystem ownership paths exist within the same workspace directory tree
- `outputs/` may be written by both `WorkspaceManager.write_output()` (repository-scoped) and future execution services (runtime-scoped); callers must use the correct API for the artifact category

## Relationship to Existing ADRs

This ADR clarifies workspace filesystem ownership introduced across Coder milestones (M4.1–M4.3) and execution milestone M5.1. It does not change any public interface. Workflow scheduling remains governed by [ADR-0001](ADR-0001-Workflow-Orchestrator.md).
