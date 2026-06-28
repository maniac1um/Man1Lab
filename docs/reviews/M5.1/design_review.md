# Design Review Report — M5.1 Environment Preparation

**Milestone:** M5.1 — Environment Preparation  
**Capability:** Runner / Execution (environment preparation only)  
**Status:** Complete  
**Tests:** 64 total, all passing

---

# 1. Environment Preparation Pipeline

Complete execution path from workspace input to prepared workspace:

```text
Workspace
        ↓
WorkflowOrchestrator._run_stage(PipelineStage.RUNNER, ...)
        ↓
Runner.run(workspace: Workspace)
        ↓
EnvironmentService.prepare(workspace)
        ↓
verify requirements.txt exists
        ↓
command_runner([python, -m, venv, .venv], cwd=workspace)
        ↓
command_runner([.venv/bin/pip, install, -r, requirements.txt], cwd=workspace)
        ↓
write workspace/logs/environment_preparation.log
        ↓
return ExecutionResult
```

## Stage-by-stage responsibility

### `Workspace` (input)

`Runner.run()` receives a `Workspace` with `root_path` pointing to the generated reproduction project. The workspace must contain `requirements.txt` (produced by Coder in M4.3 for environment-routed tasks).

### `Runner.run(workspace)`

Agent entry point for execution. Delegates entirely to `EnvironmentService.prepare()`. Public signature unchanged: `run(workspace: Workspace) -> ExecutionResult`.

### `EnvironmentService.prepare(workspace)`

Execution component responsible for environment preparation:

1. Locates workspace at `workspace.root_path`
2. Verifies `requirements.txt` exists
3. Runs `python -m venv .venv` inside the workspace
4. Runs `.venv/bin/pip install -r requirements.txt` (platform-specific pip path)
5. Writes `logs/environment_preparation.log`
6. Returns `ExecutionResult` with exit code, stdout, stderr, command summary, duration, and workspace path

### `ExecutionResult` (output)

Frozen Pydantic model unchanged. Reports preparation outcome. `executed_command` describes both venv and pip commands.

### Workspace filesystem (evolved)

After successful preparation:

```text
workspace/tasks/{paper_slug}/
├── .venv/                        (new)
├── logs/
│   └── environment_preparation.log  (new)
└── ... (existing M4 artifacts)
```

The `Workspace` model itself is unchanged (`root_path`, `paper_slug` only).

---

# 2. Repository Layout

## New artifacts after M5.1

| Path | Created by | Purpose |
|------|------------|---------|
| `.venv/` | `python -m venv` subprocess | Python virtual environment for the reproduction project |
| `logs/environment_preparation.log` | `EnvironmentService._write_log()` | Preparation log with commands, status, duration |

## Unchanged artifacts

All Coder-generated files (`src/`, `configs/`, `scripts/`, `README.md`, `requirements.txt`) remain. `requirements.txt` is read but not modified by environment preparation.

## Directories not modified

`outputs/` remains unchanged. No experiment outputs are produced in M5.1.

---

# 3. EnvironmentService Design

**Module:** `services/environment_service.py`

## Public API

### `EnvironmentService.__init__(command_runner=None) -> None`

**Signature:** `__init__(self, command_runner: CommandRunner | None = None) -> None`

**Responsibility:** Initialize service with optional injectable command runner for testing.

**Return value:** `None`

**Default:** `default_command_runner` using `subprocess.run()`.

---

### `EnvironmentService.prepare(workspace) -> ExecutionResult`

**Signature:** `prepare(self, workspace: Workspace) -> ExecutionResult`

**Responsibility:** Prepare a runnable Python environment inside the workspace.

**Behavior:**
1. Resolve `workspace.root_path`
2. Raise `RequirementsNotFoundError` if `requirements.txt` missing
3. Build venv command: `[sys.executable, "-m", "venv", "{workspace}/.venv"]`
4. Build pip command: `[{venv}/bin/pip, "install", "-r", "{workspace}/requirements.txt"]`
5. Execute venv creation via `command_runner`
6. Execute pip install via `command_runner`
7. Write log file with step details and overall status
8. Return `ExecutionResult`

**Return value:** `ExecutionResult`

---

### `default_command_runner(command, cwd) -> CommandResult`

**Signature:** `default_command_runner(command: list[str], cwd: Path) -> CommandResult`

**Responsibility:** Execute subprocess command with captured stdout/stderr.

**Return value:** `CommandResult(returncode, stdout, stderr)`

---

## Supporting types

| Name | Purpose |
|------|---------|
| `CommandResult` | Dataclass holding subprocess exit code and streams |
| `CommandRunner` | Callable type alias: `(list[str], Path) -> CommandResult` |
| `LOG_FILENAME` | `"environment_preparation.log"` |
| `VENV_DIRNAME` | `".venv"` |

## Exceptions

| Exception | Module | When raised |
|-----------|--------|-------------|
| `RequirementsNotFoundError` | `services/exceptions.py` | `requirements.txt` not found in workspace |
| `EnvironmentError` | `services/exceptions.py` | Base class for environment errors |

## Log file content

Each log includes:

- Start timestamp and workspace path
- Per-step section: command, start time, status, exit code, duration, stdout, stderr
- Overall status (`SUCCESS` or `FAILED`)
- Total duration
- Completion timestamp

---

# 4. Runner Integration

**Module:** `agents/runner.py`

## Constructor

```python
Runner.__init__(
    self,
    environment_service: EnvironmentService | None = None,
) -> None
```

**Dependencies:**
- `environment_service` — optional; defaults to `EnvironmentService()` with real subprocess

## Execution flow

```python
def run(self, workspace: Workspace) -> ExecutionResult:
    return self._environment_service.prepare(workspace)
```

## What Runner does in M5.1

- Receives `Workspace` from orchestrator
- Delegates environment preparation to `EnvironmentService`
- Returns `ExecutionResult` describing preparation outcome

## What Runner does NOT do in M5.1

- Does not execute `scripts/train.py` or `scripts/evaluate.py`
- Does not run experiments or evaluation
- Does not invoke Reviewer or retry logic
- Does not use Docker, Conda, or Poetry
- Does not modify source files in `src/`, `configs/`, or `scripts/`

---

# 5. Public APIs

## Runner

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(environment_service=None) -> None` | Optional `EnvironmentService` | `None` |
| `run` | `(workspace: Workspace) -> ExecutionResult` | `Workspace` | `ExecutionResult` |

**Frozen contract preserved:** `run(workspace) -> ExecutionResult`.

## EnvironmentService

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(command_runner=None) -> None` | Optional `CommandRunner` | `None` |
| `prepare` | `(workspace: Workspace) -> ExecutionResult` | `Workspace` | `ExecutionResult` |

## ExecutionResult (unchanged)

| Field | Type |
|-------|------|
| `exit_code` | `int` |
| `stdout` | `str` |
| `stderr` | `str` |
| `executed_command` | `str` |
| `execution_time_seconds` | `float` |
| `workspace_path` | `Path` |

## Workspace (unchanged)

| Field | Type |
|-------|------|
| `root_path` | `Path` |
| `paper_slug` | `str` |

## WorkflowOrchestrator (unchanged)

Still invokes `Runner.run(history.workspace)` at `PipelineStage.RUNNER`.

---

# 6. Test Coverage

## New test file

**File:** `tests/test_environment_service.py`

### `EnvironmentServiceTest` (4 tests)

#### `test_virtual_environment_creation`

| Field | Value |
|-------|-------|
| **Purpose** | Verify venv command is invoked and `.venv/` created |
| **Verification target** | `RecordingCommandRunner.commands`, `.venv/` directory |
| **Expected result** | One venv command; `.venv/` exists; `exit_code == 0` |

#### `test_requirements_installation_invoked`

| Field | Value |
|-------|-------|
| **Purpose** | Verify pip install is invoked against requirements.txt |
| **Verification target** | Recorded pip command |
| **Expected result** | One pip command with `install` and `-r requirements.txt` |

#### `test_log_generation`

| Field | Value |
|-------|-------|
| **Purpose** | Verify preparation log is written |
| **Verification target** | `logs/environment_preparation.log` |
| **Expected result** | Log contains step names, `Status: SUCCESS`, `Duration:` |

#### `test_successful_execution_result`

| Field | Value |
|-------|-------|
| **Purpose** | Verify `ExecutionResult` fields |
| **Verification target** | Return value of `prepare()` |
| **Expected result** | `exit_code == 0`; correct `workspace_path`; command string includes venv and pip |

### `RunnerEnvironmentTest` (1 test)

#### `test_runner_returns_execution_result_for_same_workspace`

| Field | Value |
|-------|-------|
| **Purpose** | Verify Runner delegates and returns result for input workspace path |
| **Verification target** | `Runner.run(workspace)` |
| **Expected result** | `exit_code == 0`; `workspace_path` matches; `.venv/` created |

### `EnvironmentWorkflowTest` (1 test)

#### `test_workflow_execution`

| Field | Value |
|-------|-------|
| **Purpose** | Full workflow with environment preparation |
| **Verification target** | `WorkflowOrchestrator.run()` |
| **Expected result** | Report generated successfully |

## Updated tests

| File | Change |
|------|--------|
| `tests/test_smoke.py` | Injects mock `command_runner` to avoid network package downloads |
| `tests/test_coder_population.py` | Same mock injection for workflow test |
| `tests/test_task_routing.py` | Same mock injection for workflow test |

## Mock strategy

`_mock_command_runner` in `tests/test_environment_service.py`:

- On venv command: creates `.venv/` and stub pip executable
- On pip command: returns success without downloading packages
- Used by all workflow integration tests

## Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 64 |
| **New tests** | 6 |
| **Updated tests** | 3 |
| **Passing status** | All 64 passing |

---

# 7. Current Limitations

- **Environment preparation only.** No training, evaluation, or script execution.
- **Standard venv only.** No Conda, Docker, or Poetry support.
- **Requires requirements.txt.** Preparation fails with `RequirementsNotFoundError` if file is missing.
- **Sequential subprocess calls.** Venv creation must succeed before pip install is attempted; pip is still invoked if venv fails.
- **No pip retry logic.** Single pip install attempt; failure recorded in log and `ExecutionResult`.
- **Real subprocess by default.** `Runner()` without injection runs actual `venv` and `pip install`, which may download packages and require network access.
- **Workspace model unchanged.** `.venv` presence is not reflected in the `Workspace` Pydantic object.
- **README not updated.** Workspace status in `README.md` still reflects M4.1 stub text.
- **Reviewer unchanged.** Still returns mock `requires_patch=False`.
- **Log writes bypass WorkspaceManager.** `EnvironmentService` writes directly to `workspace/logs/` (execution logs, not repository source files).

---

# 8. Code Metrics

| Metric | Value |
|--------|-------|
| **Files added** | 2 (`services/environment_service.py`, `tests/test_environment_service.py`) |
| **Files modified** | 6 (`agents/runner.py`, `services/exceptions.py`, `services/__init__.py`, `tests/test_smoke.py`, `tests/test_coder_population.py`, `tests/test_task_routing.py`) |
| **Tests added** | 6 |
| **Approximate production lines added** | ~195 |
| **Approximate test lines added** | ~175 |
| **Production files changed** | 4 |

### Per-file line counts (M5.1 production)

| File | Lines |
|------|------:|
| `services/environment_service.py` | 179 |
| `agents/runner.py` | 11 |
| `services/exceptions.py` | 26 |
| `services/__init__.py` | 22 |

---

# 9. Architecture Check

| Item | Answer |
|------|--------|
| Runner `run(workspace) -> ExecutionResult` signature unchanged | **YES** |
| `ExecutionResult` model unchanged | **YES** |
| `Workspace` model unchanged | **YES** |
| Execution component implemented (`EnvironmentService`) | **YES** |
| Virtual environment created (`.venv/`) | **YES** |
| `requirements.txt` installation invoked | **YES** |
| Logs written to `workspace/logs/` | **YES** |
| No experiment execution | **YES** |
| No Docker / Conda / Poetry | **YES** |
| Workflow executable end-to-end | **YES** |
| WorkflowOrchestrator unchanged | **YES** |
| Coder unmodified | **YES** |
| Reviewer unmodified | **YES** |
| No new domain models | **YES** |
| No circular imports | **YES** |
| Subprocess mockable for tests | **YES** |

---

# 10. Changed Files

## `services/environment_service.py`

| Field | Detail |
|-------|--------|
| **Why** | M5.1 requires dedicated environment preparation logic |
| **Responsibility** | Create venv, install requirements, write logs, return `ExecutionResult` |
| **Implementation** | Injectable `CommandRunner`; two-step subprocess execution; log file generation |

## `agents/runner.py`

| Field | Detail |
|-------|--------|
| **Why** | Runner must delegate to execution component instead of returning mock training result |
| **Responsibility** | Agent entry point for execution stage |
| **Implementation** | Replaced hardcoded `ExecutionResult` with `EnvironmentService.prepare()` delegation |

## `services/exceptions.py`

| Field | Detail |
|-------|--------|
| **Why** | Missing requirements file needs typed error |
| **Responsibility** | Environment error hierarchy |
| **Implementation** | Added `EnvironmentError`, `RequirementsNotFoundError` |

## `services/__init__.py`

| Field | Detail |
|-------|--------|
| **Why** | Export new service and exceptions |
| **Responsibility** | Package public API |
| **Implementation** | Added `EnvironmentService`, `EnvironmentError`, `RequirementsNotFoundError` |

## `tests/test_environment_service.py`

| Field | Detail |
|-------|--------|
| **Why** | M5.1 acceptance criteria require environment preparation tests |
| **Responsibility** | Unit and integration tests with mocked subprocess |
| **Implementation** | Six tests; `_mock_command_runner` and `RecordingCommandRunner` helpers |

## `tests/test_smoke.py`, `tests/test_coder_population.py`, `tests/test_task_routing.py`

| Field | Detail |
|-------|--------|
| **Why** | Runner now performs real subprocess by default; workflow tests must avoid package downloads |
| **Responsibility** | Inject mock `EnvironmentService` for integration tests |
| **Implementation** | `Runner(environment_service=EnvironmentService(command_runner=_mock_command_runner))` |
