# Design Review Report — M4.2 Task Routing

**Milestone:** M4.2 — Task Routing  
**Capability:** Coder (repository routing only)  
**Status:** Complete  
**Tests:** 51 total, all passing

---

# 1. Workspace Construction Pipeline

Complete execution path from upstream models through routing to returned workspace:

```text
PaperModel
TaskModel
        ↓
WorkflowOrchestrator._run_stage(PipelineStage.CODER, ...)
        ↓
Coder.run(paper: PaperModel, task: TaskModel, patch_plan: PatchPlan | None = None)
        ↓
Coder._paper_slug(paper.title)                         → paper_slug (str)
        ↓
WorkspaceManager.create_workspace(paper_slug)          → Workspace
        ↓
TaskRouter.route_task(task)                            → TaskRoutingTable
        ↓
WorkspaceManager.store_routing_table(workspace, table) → None (in-memory)
        ↓
WorkspaceManager.initialize_repository(...)              → README.md, requirements.txt
        ↓
return Workspace
        ↓
stored in WorkflowHistory.workspace
```

## Stage-by-stage responsibility

### `TaskModel` (routing input)

`TaskModel.steps` is a list of `TaskStep` objects. Each step has `id`, `name`, `description`, and `status`. The router uses `name` and `description` (combined, lowercased) to classify the step and assign repository targets. `status` is not used for routing.

### `TaskRouter.route_task(task)`

Iterates every `TaskStep` in `task.steps`, calls `route_step(step)` for each, and aggregates all `RepositoryTarget` entries into a single `TaskRoutingTable`. The router does not create files, call the LLM, or access the filesystem.

### `TaskRouter.route_step(step)`

Classifies a single `TaskStep` using deterministic keyword rules (see Section 11), then returns a `list[RepositoryTarget]` describing intended file destinations. Returns an empty list when no rule matches.

### `WorkspaceManager.store_routing_table(workspace, routing_table)`

Stores the `TaskRoutingTable` in an in-memory dictionary keyed by `workspace.root_path.resolve()`. No files are written for routing metadata in M4.2. The routing table is retrievable via `get_routing_table(workspace)` for downstream consumption in M4.3.

### `WorkspaceManager.initialize_repository(...)`

Unchanged in behavior from M4.1. Still writes only `README.md` and `requirements.txt` stub files. Does not write any routed target files (`src/dataset.py`, `scripts/train.py`, etc.).

### `Workspace` (output)

The `Workspace` Pydantic model is unchanged. It still contains only `root_path` and `paper_slug`. Routing metadata is stored separately in `WorkspaceManager`, not embedded in the `Workspace` object.

---

# 2. Repository Layout

## On-disk layout (unchanged from M4.1)

```text
workspace/tasks/{paper_slug}/
├── src/                  (empty)
├── configs/              (empty)
├── scripts/              (empty)
├── outputs/              (empty)
├── logs/                 (empty)
├── README.md             (stub, written)
└── requirements.txt      (stub, written)
```

M4.2 does not create any additional on-disk files beyond M4.1 output.

## Routing targets (metadata only)

The following paths are described by `TaskRoutingTable` but are **not** created on disk in M4.2:

| Relative path | File category | Typical originating task type |
|---------------|---------------|-------------------------------|
| `requirements.txt` | `dependencies` | environment |
| `src/dataset.py` | `source` | dataset |
| `configs/dataset.yaml` | `config` | dataset |
| `src/model.py` | `source` | model |
| `scripts/train.py` | `script` | training |
| `configs/train.yaml` | `config` | training |
| `scripts/evaluate.py` | `script` | evaluation |

Each `RepositoryTarget` records `relative_path`, `file_category`, and `task_id` (the originating `TaskStep.id`).

## Directory responsibilities (unchanged)

| Directory | On-disk state in M4.2 | Intended future use |
|-----------|----------------------|---------------------|
| `src/` | Empty | Source modules (`dataset.py`, `model.py`) |
| `configs/` | Empty | Configuration files (`dataset.yaml`, `train.yaml`) |
| `scripts/` | Empty | Executable scripts (`train.py`, `evaluate.py`) |
| `outputs/` | Empty | Reproduction run outputs |
| `logs/` | Empty | Execution logs |

## File responsibilities

| File | Written in M4.2 | Content |
|------|-----------------|---------|
| `README.md` | Yes (stub) | Paper title, structure, tasks, init status |
| `requirements.txt` | Yes (stub) | Placeholder comment only |
| Routed target files | No | Described in routing table only |

---

# 3. WorkspaceManager Design

**Module:** `workspace/manager.py`

M4.1 filesystem responsibilities are preserved. M4.2 adds in-memory routing metadata storage only. Existing methods (`create_workspace`, `initialize_repository`, `write_file`, `read_file`, `write_output`, `write_report`) are unchanged in signature and M4.1 behavior.

## Existing public APIs (unchanged)

### `WorkspaceManager.__init__(root=None, outputs_dir=None) -> None`

**Responsibility:** Initialize workspace root, outputs directory, and (M4.2) empty routing table store.

**Return value:** `None`

**M4.2 change:** Initializes `self._routing_tables: dict[Path, TaskRoutingTable] = {}`.

---

### `WorkspaceManager.create_workspace(paper_slug) -> Workspace`

**Signature:** `create_workspace(self, paper_slug: str) -> Workspace`

**Responsibility:** Create workspace directory skeleton.

**Return value:** `Workspace`

**Unchanged in M4.2.**

---

### `WorkspaceManager.initialize_repository(workspace, paper_title, task, patch_plan=None) -> None`

**Signature:** `initialize_repository(self, workspace, paper_title, task, patch_plan=None) -> None`

**Responsibility:** Write `README.md` and `requirements.txt` stubs.

**Return value:** `None`

**Unchanged in M4.2.**

---

### `WorkspaceManager.write_file(workspace, relative_path, content) -> None`

**Unchanged in M4.2.**

---

### `WorkspaceManager.read_file(workspace, relative_path) -> str`

**Unchanged in M4.2.**

---

### `WorkspaceManager.write_output(workspace, relative_path, content) -> Path`

**Unchanged in M4.2.**

---

### `WorkspaceManager.write_report(report, filename="report.md") -> Path`

**Unchanged in M4.2.**

---

## New public APIs (M4.2)

### `WorkspaceManager.store_routing_table(workspace, routing_table) -> None`

**Signature:** `store_routing_table(self, workspace: Workspace, routing_table: TaskRoutingTable) -> None`

**Responsibility:** Associate a `TaskRoutingTable` with a workspace in memory. Does not write any files.

**Parameters:**
- `workspace` — the workspace to associate routing metadata with
- `routing_table` — aggregated routing targets from `TaskRouter.route_task()`

**Return value:** `None`

**Storage:** `self._routing_tables[workspace.root_path.resolve()] = routing_table`

---

### `WorkspaceManager.get_routing_table(workspace) -> TaskRoutingTable | None`

**Signature:** `get_routing_table(self, workspace: Workspace) -> TaskRoutingTable | None`

**Responsibility:** Retrieve the routing table previously stored for a workspace.

**Return value:** `TaskRoutingTable` if stored; `None` if no routing table exists for the workspace path.

---

## Why WorkspaceManager stores routing metadata

`Coder` does not hold routing state after `run()` returns. Storing the routing table in `WorkspaceManager` keeps routing metadata associated with the workspace path and available for M4.3 code generation without modifying the `Workspace` model or writing routing files to disk. Filesystem creation responsibilities remain unchanged; routing storage is metadata-only.

---

# 4. Coder Integration

**Module:** `agents/coder.py`

## Constructor

```python
Coder.__init__(
    self,
    workspace_manager: WorkspaceManager,
    llm: LLMProvider | None = None,
    task_router: TaskRouter | None = None,
) -> None
```

**Dependencies:**
- `workspace_manager: WorkspaceManager` — required; workspace creation, routing storage, stub file writes
- `llm: LLMProvider | None` — optional; stored but unused
- `task_router: TaskRouter | None` — optional; defaults to `TaskRouter()` if not provided

The `task_router` parameter is new in M4.2. Existing call sites that pass only `workspace_manager` (and optionally `llm`) continue to work.

## Execution flow

```python
def run(self, paper, task, patch_plan=None) -> Workspace:
    slug = self._paper_slug(paper.title)
    workspace = self._workspace_manager.create_workspace(slug)
    routing_table = self._task_router.route_task(task)
    self._workspace_manager.store_routing_table(workspace, routing_table)
    self._workspace_manager.initialize_repository(
        workspace, paper.title, task, patch_plan
    )
    return workspace
```

Steps added in M4.2:
1. `route_task(task)` — produce routing table
2. `store_routing_table(workspace, routing_table)` — pass routing to WorkspaceManager

## Returned Workspace object

Unchanged. `Workspace(root_path, paper_slug)` with no routing fields.

## What Coder does in M4.2

- Derives slug from paper title
- Creates workspace skeleton via `WorkspaceManager`
- Routes each `TaskStep` to repository targets via `TaskRouter`
- Stores routing table in `WorkspaceManager`
- Writes M4.1 stub files via `initialize_repository`
- Returns `Workspace`

## What Coder intentionally does NOT do in M4.2

- Does not generate source code or configuration file contents
- Does not create routed target files on disk
- Does not invoke `LLMProvider`
- Does not modify prompt infrastructure
- Does not change `Runner`, `Reviewer`, or `Reporter`
- Does not call filesystem APIs directly

---

# 5. Public APIs

## TaskRouter

**Module:** `routing/task_router.py`

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `route_step` | `(step: TaskStep) -> list[RepositoryTarget]` | Single `TaskStep` | List of repository targets for that step |
| `route_task` | `(task: TaskModel) -> TaskRoutingTable` | `TaskModel` | Aggregated routing table for all steps |

## RepositoryTarget

**Module:** `models/routing.py`

| Field | Type | Description |
|-------|------|-------------|
| `relative_path` | `str` | Workspace-relative file path |
| `file_category` | `str` | Category label (`dependencies`, `source`, `config`, `script`) |
| `task_id` | `str` | Originating `TaskStep.id` |

## TaskRoutingTable

**Module:** `models/routing.py`

| Field | Type | Description |
|-------|------|-------------|
| `targets` | `list[RepositoryTarget]` | All routing targets for a task model |

## Coder

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(workspace_manager, llm=None, task_router=None) -> None` | `WorkspaceManager`, optional `LLMProvider`, optional `TaskRouter` | `None` |
| `run` | `(paper, task, patch_plan=None) -> Workspace` | `PaperModel`, `TaskModel`, optional `PatchPlan` | `Workspace` |

**Frozen contract preserved:** `run(paper, task, patch_plan=None) -> Workspace` signature unchanged.

## WorkspaceManager (M4.2 additions)

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `store_routing_table` | `(workspace, routing_table) -> None` | `Workspace`, `TaskRoutingTable` | `None` |
| `get_routing_table` | `(workspace) -> TaskRoutingTable \| None` | `Workspace` | `TaskRoutingTable` or `None` |

## Workspace

| Field | Type | Description |
|-------|------|-------------|
| `root_path` | `Path` | Filesystem path to workspace root |
| `paper_slug` | `str` | Sanitized paper identifier |

**Unchanged in M4.2.**

---

# 6. Test Coverage

## New test file

**File:** `tests/test_task_routing.py`

### `TaskRouterTest` (9 tests)

#### `test_routes_environment_task`

| Field | Value |
|-------|-------|
| **Purpose** | Verify environment-class tasks route to `requirements.txt` |
| **Verification target** | `TaskRouter.route_step()` for `"Environment setup"` |
| **Expected result** | One target: `requirements.txt`, category `dependencies`, task_id `task_1` |

#### `test_routes_dependency_installation_to_environment`

| Field | Value |
|-------|-------|
| **Purpose** | Verify dependency installation routes to environment target |
| **Verification target** | `route_step()` for `"Dependency installation"` |
| **Expected result** | One target: `requirements.txt` |

#### `test_routes_dataset_task`

| Field | Value |
|-------|-------|
| **Purpose** | Verify dataset tasks route to source and config files |
| **Verification target** | `route_step()` for `"Dataset preparation"` |
| **Expected result** | Two targets: `src/dataset.py` (source), `configs/dataset.yaml` (config) |

#### `test_routes_model_implementation_task`

| Field | Value |
|-------|-------|
| **Purpose** | Verify model implementation routes to `src/model.py` |
| **Verification target** | `route_step()` for `"Model implementation"` |
| **Expected result** | One target: `src/model.py`, category `source` |

#### `test_routes_training_task`

| Field | Value |
|-------|-------|
| **Purpose** | Verify training tasks route to script and config files |
| **Verification target** | `route_step()` for `"Training"` |
| **Expected result** | Two targets: `scripts/train.py` (script), `configs/train.yaml` (config) |

#### `test_routes_evaluation_task`

| Field | Value |
|-------|-------|
| **Purpose** | Verify evaluation tasks route to evaluate script |
| **Verification target** | `route_step()` for `"Evaluation"` |
| **Expected result** | One target: `scripts/evaluate.py`, category `script` |

#### `test_routing_is_deterministic`

| Field | Value |
|-------|-------|
| **Purpose** | Verify identical input produces identical output |
| **Verification target** | Two consecutive `route_step()` calls on same step |
| **Expected result** | Both results are equal |

#### `test_route_task_combines_all_steps`

| Field | Value |
|-------|-------|
| **Purpose** | Verify `route_task()` aggregates targets from multiple steps |
| **Verification target** | `route_task()` on four-step task model |
| **Expected result** | Six targets in order: `requirements.txt`, `src/dataset.py`, `configs/dataset.yaml`, `scripts/train.py`, `configs/train.yaml`, `scripts/evaluate.py` |

#### `test_unknown_task_returns_empty_targets`

| Field | Value |
|-------|-------|
| **Purpose** | Verify unclassified tasks produce no targets |
| **Verification target** | `route_step()` for `"Literature review"` |
| **Expected result** | Empty list |

### `CoderRoutingIntegrationTest` (1 test)

#### `test_coder_stores_routing_table_without_generating_routed_files`

| Field | Value |
|-------|-------|
| **Purpose** | Verify Coder stores routing metadata and does not create routed files |
| **Verification target** | `Coder.run()` + `get_routing_table()` + filesystem |
| **Expected result** | Routing table contains three paths; `src/dataset.py` and `configs/dataset.yaml` do not exist on disk |

### `TaskRoutingWorkflowTest` (1 test)

#### `test_workflow_execution`

| Field | Value |
|-------|-------|
| **Purpose** | Verify full workflow remains executable with routing integrated |
| **Verification target** | `WorkflowOrchestrator.run()` end-to-end |
| **Expected result** | `report.final_status` is truthy; report path exists |

## Regression tests

All 40 pre-M4.2 tests continue to pass unchanged, including `tests/test_coder.py` (7 tests) and `tests/test_smoke.py` (1 test).

## Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 51 |
| **New tests** | 11 |
| **Passing status** | All 51 passing |

---

# 7. Current Limitations

- **No file generation for routed targets.** Routing describes destinations only; `src/dataset.py`, `scripts/train.py`, and other routed paths are not created.
- **In-memory routing storage only.** `TaskRoutingTable` is lost when the process exits; not persisted to disk.
- **Keyword-based classification only.** Tasks that do not match defined keywords receive empty target lists.
- **No `depends_on` awareness.** Routing is per-step; task dependency order does not affect target assignment.
- **Classification uses name and description only.** `TaskStep.status` and `TaskStep.id` (except as `task_id` on targets) do not influence routing rules.
- **Rule priority is fixed.** Evaluation is checked before training, training before dataset, etc. A step whose text matches multiple categories is classified by first-match order only.
- **`requirements.txt` stub unchanged.** M4.1 placeholder content is still written; routing to `requirements.txt` does not alter the stub file content.
- **LLM not used.** `Coder` and `TaskRouter` perform no LLM calls.
- **`Workspace` model unchanged.** Routing metadata is not embedded in the returned `Workspace` object; consumers must call `get_routing_table()`.
- **Duplicate targets possible.** If multiple steps route to the same path, the routing table contains duplicate `RepositoryTarget` entries.

---

# 8. Code Metrics

| Metric | Value |
|--------|-------|
| **Files added** | 4 (`models/routing.py`, `routing/__init__.py`, `routing/task_router.py`, `tests/test_task_routing.py`) |
| **Files modified** | 3 (`agents/coder.py`, `workspace/manager.py`, `models/__init__.py`) |
| **Tests added** | 11 |
| **Approximate lines added** | ~320 (production + tests) |
| **Approximate lines removed** | ~5 |
| **Production files changed** | 5 |

### Per-file line counts (current, M4.2 production)

| File | Lines |
|------|------:|
| `models/routing.py` | 15 |
| `routing/task_router.py` | 97 |
| `routing/__init__.py` | 3 |
| `agents/coder.py` | 44 |
| `workspace/manager.py` | 175 |
| `tests/test_task_routing.py` | 197 |

### WorkspaceManager delta (M4.2 only)

Added `store_routing_table`, `get_routing_table`, and `_routing_tables` dict (~12 lines of new logic).

---

# 9. Architecture Check

| Item | Answer |
|------|--------|
| Coder `run()` signature unchanged | **YES** |
| Coder returns `Workspace` unchanged | **YES** |
| `Workspace` model unchanged | **YES** |
| WorkspaceManager M4.1 filesystem responsibilities preserved | **YES** |
| Routing component implemented (`TaskRouter`) | **YES** |
| Deterministic routing (keyword rules, no LLM) | **YES** |
| Coder integrates routing before stub file initialization | **YES** |
| Routed target files not created on disk | **YES** |
| Workflow executable end-to-end | **YES** |
| WorkflowOrchestrator unchanged | **YES** |
| No LLM integration | **YES** |
| No source code generation | **YES** |
| No prompt changes | **YES** |
| Communication via Pydantic models | **YES** |
| No circular imports | **YES** |
| Reader unmodified | **YES** |
| Planner unmodified | **YES** |
| Runner unmodified | **YES** |
| Reviewer unmodified | **YES** |
| Reporter unmodified | **YES** |

---

# 10. Changed Files

## `models/routing.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | M4.2 requires typed models for routing metadata |
| **Responsibility** | Define `RepositoryTarget` and `TaskRoutingTable` Pydantic models |
| **Implementation purpose** | `RepositoryTarget` holds `relative_path`, `file_category`, `task_id`. `TaskRoutingTable` aggregates a list of targets for consumption by Coder and WorkspaceManager. |

## `routing/task_router.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | M4.2 requires a dedicated routing component |
| **Responsibility** | Map `TaskStep` instances to `list[RepositoryTarget]` using deterministic keyword rules |
| **Implementation purpose** | `TaskRouter.route_step()` classifies a step and returns targets. `TaskRouter.route_task()` aggregates all step targets into a `TaskRoutingTable`. |

## `routing/__init__.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | Package initialization for routing module |
| **Responsibility** | Export `TaskRouter` |
| **Implementation purpose** | Public import path `from routing import TaskRouter` |

## `agents/coder.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | Coder must obtain and pass routing information during `run()` |
| **Responsibility** | Orchestrate workspace creation, routing, and stub initialization |
| **Implementation purpose** | Added `task_router` constructor parameter. `run()` calls `route_task()` and `store_routing_table()` between `create_workspace()` and `initialize_repository()`. |

## `workspace/manager.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | Coder must pass routing metadata to WorkspaceManager without file generation |
| **Responsibility** | Store and retrieve in-memory routing tables per workspace |
| **Implementation purpose** | Added `_routing_tables` dict, `store_routing_table()`, and `get_routing_table()`. No changes to M4.1 filesystem write behavior. |

## `models/__init__.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | Export new routing models |
| **Responsibility** | Package-level model exports |
| **Implementation purpose** | Added `RepositoryTarget` and `TaskRoutingTable` to `__all__` |

## `tests/test_task_routing.py`

| Field | Detail |
|-------|--------|
| **Why it changed** | M4.2 requires routing and integration test coverage |
| **Responsibility** | Unit tests for `TaskRouter`, Coder routing integration, workflow regression |
| **Implementation purpose** | Eleven tests covering environment, dataset, training, evaluation, model, deterministic behavior, unknown tasks, Coder storage without file creation, and workflow execution. |

## Files not changed

| File | Status |
|------|--------|
| `workflow/orchestrator.py` | Unchanged |
| `models/workspace.py` | Unchanged |
| `models/task.py` | Unchanged |
| `app.py` | Unchanged |
| `tests/test_coder.py` | Unchanged |
| `tests/test_smoke.py` | Unchanged |
| `prompts/` | Unchanged |

---

# 11. Routing Rules

All routing is performed by `TaskRouter` in `routing/task_router.py`. Classification uses the combined lowercase text of `TaskStep.name` and `TaskStep.description`. Rules are evaluated in fixed priority order; the first matching rule determines the task type.

## Classification priority order

| Priority | Task type | Match condition |
|----------|-----------|-----------------|
| 1 | `evaluation` | Text contains `evaluat` or `evaluation` |
| 2 | `training` | Text contains `train` or `training` |
| 3 | `dataset` | Text contains `dataset` |
| 4 | `model` | Text contains `model` AND (`implement` or `implementation`) |
| 5 | `environment` | Text contains `environment`, `dependency`, `dependencies`, or `setup` |
| 6 | `unknown` | No rule matches |

## Target assignment by task type

### `environment`

| Relative path | File category |
|---------------|---------------|
| `requirements.txt` | `dependencies` |

**Matching examples:** `"Environment setup"`, `"Dependency installation"`, any step whose name or description contains `setup` or `dependency`.

---

### `dataset`

| Relative path | File category |
|---------------|---------------|
| `src/dataset.py` | `source` |
| `configs/dataset.yaml` | `config` |

**Matching examples:** `"Dataset preparation"`, any step containing `dataset`.

---

### `model`

| Relative path | File category |
|---------------|---------------|
| `src/model.py` | `source` |

**Matching examples:** `"Model implementation"`. Requires both `model` and `implement`/`implementation` in the combined text. A step containing only `model` without implementation context does not match this rule (may match `training` if it contains `train`).

---

### `training`

| Relative path | File category |
|---------------|---------------|
| `scripts/train.py` | `script` |
| `configs/train.yaml` | `config` |

**Matching examples:** `"Training"`, any step containing `train` or `training`.

---

### `evaluation`

| Relative path | File category |
|---------------|---------------|
| `scripts/evaluate.py` | `script` |

**Matching examples:** `"Evaluation"`, any step containing `evaluat` or `evaluation`.

---

### `unknown`

| Relative path | File category |
|---------------|---------------|
| *(none)* | — |

Returns an empty `list[RepositoryTarget]`.

**Matching examples:** `"Literature review"`, any step that does not match rules 1–5.

---

## `task_id` assignment

Every `RepositoryTarget` produced for a step receives `task_id=step.id`. When a task type maps to multiple files, all targets share the same `task_id`.

## `route_task()` aggregation

`route_task()` calls `route_step()` for each step in `task.steps` order and appends all targets into a single flat list. No deduplication is applied.
