# ADR-0007 — Execution Capability

## Status

Accepted

## Date

2026-06-28

## Context

ResearchAgent must execute generated reproduction code inside a prepared workspace. Milestones M5.1 and M5.2 implemented environment preparation and script execution. The Runner agent coordinates multiple execution concerns: virtual environment setup, execution planning, and subprocess execution.

Without an explicit decomposition, Runner risks becoming a monolithic component that both decides what to run and runs it.

## Decision

The Runner capability is decomposed into a coordinator and three execution components:

```text
Runner
  ↓
EnvironmentService      (M5.1 — environment preparation)
  ↓
ExecutionPlanner        (M5.2 — execution planning)
  ↓
ExecutionService        (M5.2 — script execution)
```

### Runner (coordinator)

`Runner.run(workspace: Workspace) -> ExecutionResult` sequences execution stages. It does not invoke subprocesses directly, inspect workspace entrypoints, or write execution logs.

Current flow:

1. `EnvironmentService.prepare(workspace)` — create `.venv`, install `requirements.txt`
2. If preparation fails, return preparation `ExecutionResult`
3. `ExecutionPlanner.plan(workspace)` — build `ExecutionPlan`
4. `ExecutionService.execute(plan, workspace)` — run command, return `ExecutionResult`

### EnvironmentService

Prepares a runnable Python environment inside the workspace.

- Creates `.venv` via `python -m venv`
- Installs dependencies via `pip install -r requirements.txt`
- Writes `logs/environment_preparation.log`
- Returns `ExecutionResult` for the preparation stage

### ExecutionPlanner

Inspects the workspace and produces an immutable `ExecutionPlan`. It does not execute commands.

M5.2 supports one entrypoint only: `scripts/train.py`. If the file is missing, `ExecutionPlanError` is raised. No alternative entrypoints are guessed.

`ExecutionPlan` contains:

- `command` — subprocess argv (e.g. `[.venv/bin/python, scripts/train.py]`)
- `working_directory` — workspace root
- `environment_variables` — e.g. `VIRTUAL_ENV`

### ExecutionService

Executes exactly the command described by `ExecutionPlan`. It does not determine which script to run.

- Invokes subprocess with plan command and working directory
- Captures stdout, stderr, exit code, duration
- Writes `logs/execution.log`
- Returns `ExecutionResult`

## Rationale

### Separation of responsibilities

| Component | Responsibility |
|-----------|----------------|
| `Runner` | Coordinate preparation, planning, and execution |
| `EnvironmentService` | Environment provisioning |
| `ExecutionPlanner` | Decide what to execute |
| `ExecutionService` | Execute the plan and record results |

Each component has a single reason to change.

### Immutable ExecutionPlan

`ExecutionPlan` is a frozen Pydantic model describing execution intent only. Planning and execution are separate stages. The plan can be inspected, logged, or tested without running subprocesses.

### Deterministic execution

M5.2 supports one entrypoint (`scripts/train.py`). `ExecutionPlanner` uses a fixed rule: if `scripts/train.py` exists, plan its execution with the workspace venv Python. No heuristic or LLM-based entrypoint selection.

### Runner remains a coordinator

Runner does not grow to contain subprocess logic, log formatting, or entrypoint inspection. New execution stages (evaluation, checkpointing) can add services without changing Runner's public API.

## Alternatives Considered

**Monolithic Runner:** Runner directly runs venv, pip, and train.py. Rejected; violates single responsibility and complicates testing.

**ExecutionPlanner inside ExecutionService:** Service both plans and runs. Rejected; planning must be testable independently and must not execute commands.

**WorkspaceManager for runtime logs:** Centralize all filesystem writes in WorkspaceManager. Rejected; see [ADR-0006](ADR-0006-Runtime-Artifact-Ownership.md) — runtime artifacts belong to execution services.

## Consequences

**Positive:**

- Clear execution pipeline aligned with M5.1 and M5.2 implementation
- `Runner.run()` public API unchanged
- Injectable `command_runner` enables subprocess mocking in tests
- New execution stages can extend services without redesigning Runner

**Negative:**

- Multiple components must be wired in composition root and tests
- Preparation and execution return separate `ExecutionResult` values; Runner returns only the final execution result on success

## Relationship to Existing ADRs

This ADR records the completed Runner execution capability. Runtime artifact ownership is defined in [ADR-0006](ADR-0006-Runtime-Artifact-Ownership.md). Workflow scheduling remains governed by [ADR-0001](ADR-0001-Workflow-Orchestrator.md).
