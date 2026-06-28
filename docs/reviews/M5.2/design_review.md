# Design Review Report — M5.2 Script Execution

**Milestone:** M5.2 — Script Execution  
**Capability:** Runner / Execution (script execution)  
**Status:** Complete  
**Tests:** 70 total, all passing

---

# 1. Environment Preparation Pipeline

Complete execution path from prepared workspace through script execution:

```text
Workspace
        ↓
WorkflowOrchestrator._run_stage(PipelineStage.RUNNER, ...)
        ↓
Runner.run(workspace: Workspace)
        ↓
EnvironmentService.prepare(workspace)              → M5.1 (environment preparation)
        ↓
(if prep exit_code != 0 → return prep ExecutionResult)
        ↓
ExecutionPlanner.plan(workspace)                 → ExecutionPlan
        ↓
ExecutionService.execute(plan, workspace)        → ExecutionResult
        ↓
write workspace/logs/execution.log
        ↓
return ExecutionResult
```

## Stage-by-stage responsibility

### M5.1 — Environment preparation (unchanged, chained in Runner)

`EnvironmentService.prepare()` creates `.venv/` and installs `requirements.txt` dependencies. If preparation fails (`exit_code != 0`), `Runner.run()` returns the preparation result without building an execution plan.

### M5.2 — Execution planning

`ExecutionPlanner.plan(workspace)` inspects the workspace filesystem. For M5.2 it supports only `scripts/train.py`. If the file is missing, `ExecutionPlanError` is raised. No alternative entrypoints are guessed.

The plan specifies:
- `command` — `[venv_python, "scripts/train.py"]`
- `working_directory` — workspace root path
- `environment_variables` — `{"VIRTUAL_ENV": "<workspace>/.venv"}`

### M5.2 — Script execution

`ExecutionService.execute(plan, workspace)` runs the command from the plan. It captures stdout, stderr, exit code, and duration. It writes `logs/execution.log` and returns `ExecutionResult`. It does not determine which script to run.

### `ExecutionResult` (output)

Unchanged Pydantic model. For successful M5.2 runs, `executed_command` is the joined plan command (e.g. `.venv/bin/python scripts/train.py`).

---

# 2. Repository Layout

## Workspace state after M5.2 execution

```text
workspace/tasks/{paper_slug}/
├── .venv/                              (M5.1)
├── src/
├── configs/
├── scripts/
│   └── train.py                        (required entrypoint)
├── logs/
│   ├── environment_preparation.log     (M5.1)
│   └── execution.log                   (M5.2, new)
├── outputs/
├── README.md
└── requirements.txt
```

M5.2 does not modify repository artifacts (`src/`, `configs/`, `scripts/` content). It adds `logs/execution.log` as a runtime artifact.

---

# 3. EnvironmentService Design

**Unchanged from M5.1.** Still responsible for virtual environment creation and dependency installation.

`Runner` invokes `EnvironmentService.prepare()` before execution planning.

---

# 4. Runner Integration

**Module:** `agents/runner.py`

## Constructor

```python
Runner.__init__(
    self,
    environment_service: EnvironmentService | None = None,
    execution_planner: ExecutionPlanner | None = None,
    execution_service: ExecutionService | None = None,
) -> None
```

**Dependencies:**
- `environment_service` — defaults to `EnvironmentService()`
- `execution_planner` — defaults to `ExecutionPlanner()`
- `execution_service` — defaults to `ExecutionService()`

## Execution flow

```python
def run(self, workspace: Workspace) -> ExecutionResult:
    prep_result = self._environment_service.prepare(workspace)
    if prep_result.exit_code != 0:
        return prep_result
    plan = self._execution_planner.plan(workspace)
    return self._execution_service.execute(plan, workspace)
```

## Coordinator role

`Runner` does not:
- Inspect the workspace for entrypoints (delegated to `ExecutionPlanner`)
- Execute subprocess commands (delegated to `ExecutionService` and `EnvironmentService`)
- Write execution logs directly

`Runner` only sequences preparation, planning, and execution.

## Public API

**Frozen contract preserved:** `run(workspace: Workspace) -> ExecutionResult`

---

# 5. Public APIs

## ExecutionPlanner

**Module:** `execution/execution_planner.py`

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `plan` | `(workspace: Workspace) -> ExecutionPlan` | `Workspace` | `ExecutionPlan` |

**Constant:** `TRAIN_SCRIPT = "scripts/train.py"`

## ExecutionPlan

**Module:** `models/execution_plan.py`

| Field | Type | Description |
|-------|------|-------------|
| `command` | `list[str]` | Subprocess command argv |
| `working_directory` | `Path` | Process working directory |
| `environment_variables` | `dict[str, str]` | Environment overrides |

Immutable frozen Pydantic model. Contains no execution logic.

## ExecutionService

**Module:** `services/execution_service.py`

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(command_runner=None) -> None` | Optional `CommandRunner` | `None` |
| `execute` | `(plan: ExecutionPlan, workspace: Workspace) -> ExecutionResult` | Plan and workspace | `ExecutionResult` |

## Runner

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(environment_service=None, execution_planner=None, execution_service=None) -> None` | Optional services | `None` |
| `run` | `(workspace: Workspace) -> ExecutionResult` | `Workspace` | `ExecutionResult` |

## Exceptions

| Exception | When raised |
|-----------|-------------|
| `ExecutionPlanError` | `scripts/train.py` not found in workspace |
| `RequirementsNotFoundError` | `requirements.txt` missing (M5.1, during prep) |

## ExecutionResult (unchanged)

| Field | Type |
|-------|------|
| `exit_code` | `int` |
| `stdout` | `str` |
| `stderr` | `str` |
| `executed_command` | `str` |
| `execution_time_seconds` | `float` |
| `workspace_path` | `Path` |

---

# 6. Test Coverage

## New files

**`tests/test_script_execution.py`** — 6 tests  
**`tests/runner_mocks.py`** — shared mock subprocess for env prep and script execution

### `ExecutionPlannerTest` (2 tests)

| Test | Purpose | Expected result |
|------|---------|-----------------|
| `test_successful_execution_plan_generation` | Plan built for workspace with `train.py` | Command uses venv python + `scripts/train.py`; correct cwd and `VIRTUAL_ENV` |
| `test_missing_train_py_raises` | Missing entrypoint | `ExecutionPlanError` raised |

### `ExecutionServiceTest` (3 tests)

| Test | Purpose | Expected result |
|------|---------|-----------------|
| `test_successful_script_execution` | Mock subprocess success | `exit_code == 0`; stdout contains `Training complete.` |
| `test_execution_failure` | Mock subprocess failure | `exit_code == 1`; stderr contains `training failed` |
| `test_execution_log_generation` | Log file written | `logs/execution.log` contains command, duration, exit code, stdout |

### `ScriptExecutionWorkflowTest` (1 test)

| Test | Purpose | Expected result |
|------|---------|-----------------|
| `test_workflow_execution` | End-to-end with mocked subprocess | Report generated successfully |

## Updated tests

| File | Change |
|------|--------|
| `tests/test_environment_service.py` | Uses `runner_mocks`; workspace includes `train.py`; Runner injects `ExecutionService` |
| `tests/test_smoke.py` | Mock execution service injected |
| `tests/test_coder_population.py` | Mock execution service injected |
| `tests/test_task_routing.py` | Mock execution service injected |

## Mock strategy

`mock_command_runner` handles venv creation, pip install, and `train.py` execution without network or real training. `failing_train_command_runner` returns exit code 1 for train commands.

## Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 70 |
| **New tests** | 6 |
| **Passing status** | All 70 passing |

---

# 7. Current Limitations

- **Single entrypoint only.** Only `scripts/train.py` is supported. No `evaluate.py` or other scripts.
- **No entrypoint guessing.** Missing `train.py` raises `ExecutionPlanError`; no fallback.
- **Requires prepared environment.** Plan assumes `.venv/bin/python` exists after M5.1 preparation.
- **Sequential execution.** Environment prep then script execution; no parallel runs.
- **No retry logic.** Single execution attempt per `Runner.run()` call.
- **No checkpoint or evaluation management.**
- **Prep failure short-circuits.** Script execution is skipped if environment preparation fails.
- **Real subprocess by default.** Without injected mocks, `ExecutionService` runs actual commands.
- **Workspace model unchanged.** Execution outcome is in `ExecutionResult`, not `Workspace`.

---

# 8. Code Metrics

| Metric | Value |
|--------|-------|
| **Files added** | 5 (`models/execution_plan.py`, `execution/execution_planner.py`, `execution/__init__.py`, `services/execution_service.py`, `tests/test_script_execution.py`, `tests/runner_mocks.py`) |
| **Files modified** | 8 |
| **Tests added** | 6 |
| **Approximate production lines added** | ~175 |
| **Approximate test lines added** | ~200 |

### Per-file line counts (M5.2 production)

| File | Lines |
|------|------:|
| `models/execution_plan.py` | 11 |
| `execution/execution_planner.py` | 31 |
| `execution/__init__.py` | 3 |
| `services/execution_service.py` | 118 |
| `agents/runner.py` | 26 |

---

# 9. Architecture Check

| Item | Answer |
|------|--------|
| `Runner.run(workspace) -> ExecutionResult` unchanged | **YES** |
| `ExecutionPlanner` implemented | **YES** |
| `ExecutionPlan` model implemented | **YES** |
| `ExecutionService` executes only `ExecutionPlan` | **YES** |
| `Runner` coordinates only | **YES** |
| `execution.log` generated | **YES** |
| `ExecutionResult` returned | **YES** |
| Only `scripts/train.py` supported | **YES** |
| No alternative entrypoint guessing | **YES** |
| Workflow executable | **YES** |
| `WorkflowOrchestrator` unchanged | **YES** |
| `Workspace` model unchanged | **YES** |
| Runtime artifacts via execution services (ADR-0006) | **YES** |
| No circular imports | **YES** |

---

# 10. Changed Files

| File | Why | Responsibility |
|------|-----|----------------|
| `models/execution_plan.py` | M5.2 needs immutable execution description | `ExecutionPlan` model |
| `execution/execution_planner.py` | M5.2 needs workspace inspection and plan building | `ExecutionPlanner.plan()` |
| `execution/__init__.py` | Package export | Export `ExecutionPlanner` |
| `services/execution_service.py` | M5.2 needs subprocess execution and logging | `ExecutionService.execute()` |
| `services/exceptions.py` | Typed plan failure | `ExecutionPlanError` |
| `services/__init__.py` | Package exports | Export new service and exception |
| `agents/runner.py` | Chain prep + plan + execute | Runner coordination |
| `models/__init__.py` | Export `ExecutionPlan` | Model package |
| `tests/test_script_execution.py` | M5.2 test coverage | Planner, service, workflow tests |
| `tests/runner_mocks.py` | Shared mock subprocess | Env prep + train execution mocks |
| `tests/test_environment_service.py` | Runner now executes scripts | Updated fixtures and Runner injection |
| `tests/test_smoke.py` | Avoid real subprocess in smoke test | Mock execution service |
| `tests/test_coder_population.py` | Same | Mock execution service |
| `tests/test_task_routing.py` | Same | Mock execution service |

---

# 11. Execution Planning Flow

```text
Workspace
        ↓
ExecutionPlanner.plan(workspace)
        ↓
resolve workspace.root_path
        ↓
check (workspace / "scripts/train.py").is_file()
        ↓
(if missing → raise ExecutionPlanError)
        ↓
resolve .venv/bin/python (platform-specific)
        ↓
ExecutionPlan(
    command=[python, "scripts/train.py"],
    working_directory=workspace.root_path,
    environment_variables={"VIRTUAL_ENV": "<workspace>/.venv"},
)
```

## Inspection rules (M5.2)

| Rule | Behavior |
|------|----------|
| Entrypoint path | Fixed: `scripts/train.py` |
| File existence | Must be a regular file |
| Missing file | `ExecutionPlanError` — no fallback |
| Python interpreter | `.venv/bin/python` (or `Scripts/python.exe` on Windows) |
| Working directory | Workspace root |
| Environment | `VIRTUAL_ENV` set to `.venv` absolute path |

## Planning vs execution separation

`ExecutionPlanner` only reads the workspace filesystem and constructs `ExecutionPlan`. It does not invoke subprocess, write logs, or return `ExecutionResult`.

---

# 12. Execution Lifecycle

```text
ExecutionPlan
Workspace
        ↓
ExecutionService.execute(plan, workspace)
        ↓
record start_time
        ↓
subprocess.run(plan.command, cwd=plan.working_directory, env=...)
        ↓
capture returncode, stdout, stderr
        ↓
record end_time, compute duration
        ↓
write logs/execution.log
        ↓
ExecutionResult(
    exit_code, stdout, stderr,
    executed_command=" ".join(plan.command),
    execution_time_seconds, workspace_path,
)
```

## Full Runner lifecycle (M5.1 + M5.2)

```text
Runner.run(workspace)
  │
  ├─ EnvironmentService.prepare()
  │     ├─ python -m venv .venv
  │     ├─ pip install -r requirements.txt
  │     └─ logs/environment_preparation.log
  │
  ├─ (if prep failed → return prep ExecutionResult)
  │
  ├─ ExecutionPlanner.plan()
  │     └─ ExecutionPlan for scripts/train.py
  │
  └─ ExecutionService.execute()
        ├─ subprocess: .venv/bin/python scripts/train.py
        └─ logs/execution.log
```

## Log file content (`execution.log`)

- Start timestamp
- Workspace path
- Command string
- Working directory
- End timestamp
- Duration (seconds)
- Exit code
- Status (SUCCESS / FAILED)
- Stdout (if non-empty)
- Stderr (if non-empty)

## Subprocess behavior

- **Default:** `subprocess.run` with merged environment variables when no custom `command_runner` is injected
- **Tests:** Injected `command_runner` bypasses real subprocess and env merge
- **Failure:** Non-zero exit code propagated to `ExecutionResult.exit_code`; log records FAILED status

## Artifacts produced

| Artifact | Owner | Lifecycle stage |
|----------|-------|-----------------|
| `.venv/` | `EnvironmentService` | Preparation |
| `logs/environment_preparation.log` | `EnvironmentService` | Preparation |
| `logs/execution.log` | `ExecutionService` | Execution |

Repository artifacts (`scripts/train.py`, etc.) are created by Coder before the Runner stage begins.
