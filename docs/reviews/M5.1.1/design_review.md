# Design Review Report — M5.1.1 Runtime Artifact Ownership

**Milestone:** M5.1.1 — Architecture Documentation  
**Type:** Documentation and architecture cleanup only  
**Status:** Complete  
**Production code modified:** 0  
**Tests modified:** 0  
**Public APIs modified:** 0

---

# 1. Problem Statement

After M5.1 (Environment Preparation), the workspace filesystem contains two categories of content:

1. **Repository artifacts** — created by `Coder` through `WorkspaceManager` during M4.1–M4.3 (source code, configs, scripts, README, requirements.txt).
2. **Runtime artifacts** — created by `EnvironmentService` during M5.1 (`.venv/`, `logs/environment_preparation.log`).

The implementation correctly assigns each category to a different component. However, the canonical architecture document (`docs/architecture/ARCHITECTURE.md` §7) previously stated:

> All file operations are managed by WorkspaceManager.

This statement was accurate before M5.1 but became incomplete once `EnvironmentService` began writing runtime files inside the workspace. The ownership boundary existed in code but was not documented as an explicit architectural contract.

M5.1.1 resolves this gap through documentation only. No production code, tests, or public APIs are modified.

---

# 2. Ownership Boundary

## Repository artifacts

| Attribute | Value |
|-----------|-------|
| **Owner** | `WorkspaceManager` |
| **Orchestrated by** | `Coder` |
| **Nature** | Designed reproduction project content |
| **Lifecycle trigger** | `Coder.run()` |

**Paths:**

- `src/`
- `configs/`
- `scripts/`
- `README.md`
- `requirements.txt`

`Coder` never calls filesystem APIs directly. All repository writes go through `WorkspaceManager`.

## Runtime artifacts

| Attribute | Value |
|-----------|-------|
| **Owner** | Runtime services (`EnvironmentService` in M5.1) |
| **Orchestrated by** | `Runner` |
| **Nature** | Side effects of preparation and execution |
| **Lifecycle trigger** | `Runner.run()` |

**Paths (current and reserved):**

| Path | Status |
|------|--------|
| `.venv/` | Implemented (M5.1) |
| `logs/` | Implemented (M5.1) |
| `outputs/` (execution outputs) | Reserved |
| `checkpoints/` | Reserved |
| `tensorboard/` | Reserved |

`Runner` delegates to `EnvironmentService`; it does not write runtime files inline.

## Boundary rule

| Category | Write path | Do not use |
|----------|------------|------------|
| Repository artifact | `WorkspaceManager` via `Coder` | Execution services |
| Runtime artifact | Execution services via `Runner` | `WorkspaceManager` |

## Why runtime artifacts are excluded from WorkspaceManager

1. **Lifecycle separation** — Repository artifacts define what to reproduce. Runtime artifacts record what happened during preparation or execution. They can be regenerated without changing repository design.

2. **Agent separation** — `WorkspaceManager` serves `Coder`. Runtime services serve `Runner`. Combining both in one component would couple code generation to execution infrastructure.

3. **Operation separation** — Repository management involves skeleton creation, routing metadata, and LLM-driven file population. Runtime management involves subprocess execution, environment provisioning, and log capture.

4. **Interface stability** — `WorkspaceManager` frozen methods (`create_workspace`, `write_file`, `read_file`, `write_output`, `write_report`) remain focused on repository operations. Execution capabilities can grow through new services without expanding this API.

5. **Future execution services** — Training, evaluation, checkpointing, and telemetry will add runtime artifact types. Keeping them outside `WorkspaceManager` preserves single-responsibility ownership.

---

# 3. Repository Artifact Lifecycle

```text
PaperModel + TaskModel
        ↓
Coder.run()
        ↓
WorkspaceManager.create_workspace(slug)
        → workspace/tasks/{slug}/ + empty subdirectories
        ↓
TaskRouter.route_task(task)
WorkspaceManager.store_routing_table(workspace, table)
        → routing metadata (in-memory)
        ↓
WorkspaceManager.initialize_repository(...)
        → README.md, requirements.txt stub
        ↓
for each RepositoryTarget:
    LLMProvider.complete(...)
    WorkspaceManager.write_file(workspace, path, content)
        → src/, configs/, scripts/, requirements.txt (populated)
        ↓
return Workspace
```

**Components involved:**

| Component | Role |
|-----------|------|
| `Coder` | Orchestrates repository construction and population |
| `TaskRouter` | Maps tasks to repository targets (M4.2) |
| `PromptBuilder` / `LLMProvider` | Per-target file generation (M4.3) |
| `WorkspaceManager` | Sole filesystem writer for repository artifacts |

**Retry behavior:** When the review loop re-invokes `Coder.run()`, repository artifacts are recreated or overwritten. Runtime artifacts from a prior `Runner.run()` are not managed by this lifecycle.

---

# 4. Runtime Artifact Lifecycle

```text
Workspace
        ↓
Runner.run(workspace)
        ↓
EnvironmentService.prepare(workspace)
        ↓
verify requirements.txt exists
        ↓
subprocess: python -m venv .venv
        → .venv/ created
        ↓
subprocess: .venv/bin/pip install -r requirements.txt
        → dependencies installed into .venv
        ↓
write workspace/logs/environment_preparation.log
        → preparation log with commands, status, duration
        ↓
return ExecutionResult
```

**Components involved:**

| Component | Role |
|-----------|------|
| `Runner` | Agent entry point; delegates to `EnvironmentService` |
| `EnvironmentService` | Creates venv, runs pip install, writes preparation log |
| `ExecutionResult` | Reports exit code, streams, command, duration |

**Current runtime artifacts:**

| Artifact | Created by | Content |
|----------|------------|---------|
| `.venv/` | `python -m venv` subprocess | Python virtual environment |
| `logs/environment_preparation.log` | `EnvironmentService._write_log()` | Step commands, status, duration, stdout/stderr |

**Reserved runtime paths** (not yet implemented): `outputs/` (execution), `checkpoints/`, `tensorboard/`.

**Note on `outputs/`:** `WorkspaceManager.write_output()` writes repository-scoped outputs to `workspace/outputs/`. This is a repository API path, distinct from future execution-run outputs under the same directory name. Callers must use the API matching the artifact category.

---

# 5. Architecture Impact

## What changed

| Area | Change |
|------|--------|
| ADR index | Added ADR-0006 |
| Architecture §7 | Replaced blanket WorkspaceManager ownership with repository/runtime lifecycle subsections (§7.1, §7.2) |
| Architecture §5.5 | Clarified Runner does not modify repository source files |
| DEVELOPMENT.md | Added repository/runtime ownership engineering guideline |
| Documentation index | Added ADR-0006 entry |

## What did not change

| Area | Status |
|------|--------|
| Production code | Unchanged |
| Tests | Unchanged |
| Public APIs | Unchanged |
| `WorkspaceManager` frozen interface | Unchanged |
| `Runner.run(workspace) -> ExecutionResult` | Unchanged |
| `Coder.run(paper, task) -> Workspace` | Unchanged |
| `WorkflowOrchestrator` | Unchanged |

## Architecture check

| Item | Answer |
|------|--------|
| Implementation matches documented ownership | **YES** |
| Repository artifacts owned by WorkspaceManager | **YES** |
| Runtime artifacts owned by execution services | **YES** |
| No code changes required | **YES** |
| No API changes required | **YES** |

---

# 6. Changed Documents

| Document | Change |
|----------|--------|
| `docs/adr/ADR-0006-Runtime-Artifact-Ownership.md` | **Created** — documents repository vs runtime artifact ownership, rationale, and consequences |
| `docs/adr/README.md` | Added ADR-0006 to index |
| `docs/README.md` | Added ADR-0006 to documentation index |
| `docs/architecture/ARCHITECTURE.md` | §7 expanded with §7.1 Repository Artifact Lifecycle and §7.2 Runtime Artifact Lifecycle; §5.5 Runner clarification |
| `DEVELOPMENT.md` | Added "Repository and Runtime Artifact Ownership" engineering guideline |
| `docs/reviews/M5.1.1/design_review.md` | **Created** — this report |

## Files not changed

| Category | Files |
|----------|-------|
| Production code | All (`agents/`, `services/`, `workspace/`, etc.) |
| Tests | All (`tests/`) |
| Root `ARCHITECTURE.md` | Unchanged (pointer to canonical doc) |
