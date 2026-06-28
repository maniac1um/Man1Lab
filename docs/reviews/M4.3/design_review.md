# Design Review Report — M4.3 Repository Population

**Milestone:** M4.3 — Repository Population  
**Capability:** Coder (incremental file generation)  
**Status:** Complete  
**Tests:** 58 total, all passing

---

# 1. Workspace Construction Pipeline

Complete execution path from `Coder.run()` through repository population:

```text
PaperModel
TaskModel
        ↓
Coder.run(paper, task, patch_plan=None)
        ↓
Coder._paper_slug(paper.title)                         → paper_slug
        ↓
WorkspaceManager.create_workspace(paper_slug)          → Workspace
        ↓
TaskRouter.route_task(task)                            → TaskRoutingTable
        ↓
WorkspaceManager.store_routing_table(workspace, table)
        ↓
WorkspaceManager.initialize_repository(...)              → README.md, requirements.txt (stubs)
        ↓
Coder._populate_repository(workspace, paper, task, table)
        ↓
for each RepositoryTarget in routing_table.targets:
        ↓
    Coder._find_task_step(task, target.task_id)         → TaskStep
        ↓
    PromptBuilder.build_coder_prompt(target.file_category) → system prompt
        ↓
    Coder._format_generation_request(...)               → user prompt
        ↓
    LLMProvider.complete([system, user])                → file content (str)
        ↓
    WorkspaceManager.write_file(workspace, target.relative_path, content)
        ↓
return Workspace
```

## Stage-by-stage responsibility

### M4.1 — Workspace skeleton

`create_workspace()` creates directory structure. `initialize_repository()` writes `README.md` and placeholder `requirements.txt`.

### M4.2 — Task routing

`route_task()` produces `TaskRoutingTable`. `store_routing_table()` persists routing metadata in memory.

### M4.3 — Repository population (new)

`_populate_repository()` iterates every `RepositoryTarget` in order. For each target:

1. Resolves the originating `TaskStep` by `target.task_id`
2. Builds a category-specific system prompt via `PromptBuilder.build_coder_prompt(file_category)`
3. Builds a user prompt with paper title, engineering task, target file, and repository context
4. Invokes `LLMProvider.complete()` once
5. Writes the returned content to exactly one file via `WorkspaceManager.write_file()`

The generation unit is strictly one target → one prompt → one LLM call → one file.

### `Workspace` (output)

The `Workspace` model is unchanged. Population does not add fields to the returned object.

---

# 2. Repository Layout

## On-disk layout after M4.3

```text
workspace/tasks/{paper_slug}/
├── src/                          (populated when routed)
│   ├── dataset.py                (if dataset task routed)
│   └── model.py                  (if model task routed)
├── configs/                      (populated when routed)
│   ├── dataset.yaml              (if dataset task routed)
│   └── train.yaml                (if training task routed)
├── scripts/                      (populated when routed)
│   ├── train.py                  (if training task routed)
│   └── evaluate.py               (if evaluation task routed)
├── outputs/                      (empty)
├── logs/                         (empty)
├── README.md                     (stub from M4.1, unchanged by population)
└── requirements.txt              (stub overwritten when environment task routed)
```

Only files present in `TaskRoutingTable.targets` are written during population. No additional files are created.

## Files written by population

| Relative path | File category | Written when |
|---------------|---------------|--------------|
| `requirements.txt` | `dependencies` | Environment or dependency task routed |
| `src/dataset.py` | `source` | Dataset task routed |
| `configs/dataset.yaml` | `config` | Dataset task routed |
| `src/model.py` | `source` | Model implementation task routed |
| `scripts/train.py` | `script` | Training task routed |
| `configs/train.yaml` | `config` | Training task routed |
| `scripts/evaluate.py` | `script` | Evaluation task routed |

## Files not modified by population

| File | State after population |
|------|------------------------|
| `README.md` | Retains M4.1 stub content (including "not started" status lines) |
| `outputs/` | Empty |
| `logs/` | Empty |

When `requirements.txt` is a routing target, the M4.1 placeholder is overwritten with LLM-generated content.

---

# 3. WorkspaceManager Design

**Module:** `workspace/manager.py`

M4.3 does not modify `WorkspaceManager` method signatures or add new public methods. Population uses the existing `write_file()` method exclusively for generated content.

## Methods used by M4.3 population

### `WorkspaceManager.write_file(workspace, relative_path, content) -> None`

**Responsibility:** Write generated file content to `workspace.root_path / relative_path`. Creates parent directories if needed.

**Called by:** `Coder._populate_repository()` once per `RepositoryTarget`.

### `WorkspaceManager.get_routing_table(workspace) -> TaskRoutingTable | None`

**Responsibility:** Retrieve stored routing table (used internally by Coder via routing table passed to `_populate_repository`; not re-fetched from manager during population).

**Unchanged from M4.2.**

## Filesystem ownership

`WorkspaceManager` remains the only component that writes files to disk. `Coder` never calls `Path.write_text` or `open()` directly.

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
    prompt_builder: PromptBuilder | None = None,
) -> None
```

**Dependencies:**
- `workspace_manager` — required
- `llm` — optional; defaults to `CoderMockLLMProvider()`
- `task_router` — optional; defaults to `TaskRouter()`
- `prompt_builder` — optional; defaults to `PromptBuilder(PromptLoader())`

The `prompt_builder` parameter is new in M4.3. Existing call sites passing only `workspace_manager` continue to work.

## Execution flow

`run()` performs M4.1 skeleton creation, M4.2 routing, then calls `_populate_repository()` before returning `Workspace`.

## `_populate_repository()` (new)

Private method encapsulating the per-target generation loop. Iterates `routing_table.targets` in order, maintaining `populated_paths` for repository context in subsequent prompts.

## Helper methods (new)

| Method | Purpose |
|--------|---------|
| `_find_task_step(task, task_id)` | Resolve `TaskStep` by id for prompt context |
| `_format_repository_context(populated_paths)` | List files generated so far in this run |
| `_format_generation_request(...)` | Build user prompt with paper, task, target, context |

## What Coder does in M4.3

- Creates workspace skeleton (M4.1)
- Routes tasks (M4.2)
- Generates one file per `RepositoryTarget` via LLM
- Writes all generated content through `WorkspaceManager`
- Returns `Workspace`

## What Coder does NOT do in M4.3

- Does not generate multiple files in one LLM call
- Does not execute code (Runner unchanged)
- Does not repair or retry on failure
- Does not modify README after population
- Does not create files outside the routing table
- Does not use provider-specific LLM logic

---

# 5. Public APIs

## Coder

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `__init__` | `(workspace_manager, llm=None, task_router=None, prompt_builder=None) -> None` | Dependencies | `None` |
| `run` | `(paper, task, patch_plan=None) -> Workspace` | `PaperModel`, `TaskModel`, optional `PatchPlan` | `Workspace` |

**Frozen contract preserved:** `run(paper, task, patch_plan=None) -> Workspace`.

## PromptBuilder

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `build_coder_prompt` | `(file_category: str) -> str` | Category string (`dependencies`, `source`, `config`, `script`) | Combined system prompt |

## CoderMockLLMProvider

| Member | Signature | Input | Output |
|--------|-----------|-------|--------|
| `complete` | `(messages, *, temperature=0.0) -> str` | `list[LLMMessage]` | Deterministic file content based on target path in user message |

## LLMProvider (abstract, unchanged)

| Member | Signature |
|--------|-----------|
| `complete` | `(messages: list[LLMMessage], *, temperature: float = 0.0) -> str` |

## TaskRouter (unchanged from M4.2)

| Member | Signature | Output |
|--------|-----------|--------|
| `route_step` | `(step: TaskStep) -> list[RepositoryTarget]` | Targets for one step |
| `route_task` | `(task: TaskModel) -> TaskRoutingTable` | Aggregated targets |

## WorkspaceManager (unchanged signatures)

Population uses `write_file`, `create_workspace`, `initialize_repository`, `store_routing_table`.

## Workspace (unchanged)

| Field | Type |
|-------|------|
| `root_path` | `Path` |
| `paper_slug` | `str` |

---

# 6. Test Coverage

## New test file

**File:** `tests/test_coder_population.py`

### `CoderPopulationTest` (5 tests)

#### `test_one_llm_invocation_per_repository_target`

| Field | Value |
|-------|-------|
| **Purpose** | Verify exactly one LLM call per routing target |
| **Verification target** | `RecordingLLMProvider.calls` length |
| **Expected result** | 3 calls for environment + dataset task (3 targets) |

#### `test_generated_content_written_through_workspace_manager`

| Field | Value |
|-------|-------|
| **Purpose** | Verify content is persisted via WorkspaceManager |
| **Verification target** | `read_file(workspace, "src/model.py")` |
| **Expected result** | Content matches `MOCK_FILE_CONTENT["src/model.py"]` |

#### `test_correct_target_file_population`

| Field | Value |
|-------|-------|
| **Purpose** | Verify correct files created for mixed task types |
| **Verification target** | Filesystem under workspace root |
| **Expected result** | `requirements.txt`, `scripts/train.py`, `configs/train.yaml`, `scripts/evaluate.py` exist; `src/dataset.py` does not |

#### `test_deterministic_repository_population`

| Field | Value |
|-------|-------|
| **Purpose** | Verify identical inputs produce identical file content |
| **Verification target** | Two `Coder.run()` calls with same inputs |
| **Expected result** | `src/dataset.py` and `configs/dataset.yaml` content identical across runs |

#### `test_only_routed_files_are_created`

| Field | Value |
|-------|-------|
| **Purpose** | Verify no extra files beyond routing table |
| **Verification target** | Directory listings under `src/`, `scripts/`, `configs/` |
| **Expected result** | Only `src/model.py` in `src/`; `scripts/` and `configs/` empty |

### `CoderPopulationWorkflowTest` (1 test)

#### `test_workflow_execution`

| Field | Value |
|-------|-------|
| **Purpose** | Full workflow remains executable with population |
| **Verification target** | `WorkflowOrchestrator.run()` |
| **Expected result** | Report generated successfully |

## Updated tests

| File | Test | Change |
|------|------|--------|
| `tests/test_coder.py` | `test_requirements_txt_generated` | Asserts populated `torch>=2.0.0` instead of placeholder |
| `tests/test_coder.py` | `test_routed_files_populated` | Replaces `test_no_source_code_generated`; verifies routed files exist |
| `tests/test_task_routing.py` | `test_coder_stores_routing_table_and_populates_routed_files` | Asserts routed files exist on disk |
| `tests/test_prompt.py` | `test_build_coder_prompt_uses_category_template` | Verifies category-specific prompt assembly |

## Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 58 |
| **New tests** | 6 |
| **Updated tests** | 4 |
| **Passing status** | All 58 passing |

---

# 7. Current Limitations

- **Mock LLM by default.** `Coder` defaults to `CoderMockLLMProvider` with predetermined content per target path. Real LLM integration requires injecting an external `LLMProvider`.
- **No response parsing.** LLM output is written directly to file without validation or post-processing.
- **README not updated.** Population does not update workspace status in `README.md`.
- **No deduplication.** Duplicate routing targets (e.g. two environment tasks both routing to `requirements.txt`) result in multiple LLM calls; last write wins.
- **Sequential generation only.** Targets are processed one at a time in routing table order; no parallelization.
- **No retry on LLM failure.** Exceptions from `LLMProvider.complete()` propagate and abort `Coder.run()`.
- **Repository context is path list only.** Context passed to prompts lists previously generated file paths, not file contents.
- **Category must match prompt file.** `build_coder_prompt(file_category)` loads `prompts/coder/{file_category}.md`; unknown categories raise `PromptNotFoundError`.
- **Task step lookup required.** If `target.task_id` does not match any `TaskStep.id`, `ValueError` is raised.
- **Runner still mock.** `scripts/train.py` may be generated but Runner does not execute it.

---

# 8. Code Metrics

| Metric | Value |
|--------|-------|
| **Files added** | 7 (`llm/coder_mock_provider.py`, `tests/test_coder_population.py`, 5 prompt files under `prompts/coder/`) |
| **Files modified** | 5 (`agents/coder.py`, `prompt/builder.py`, `tests/test_coder.py`, `tests/test_task_routing.py`, `tests/test_prompt.py`) |
| **Tests added** | 6 |
| **Tests updated** | 4 |
| **Approximate production lines added** | ~95 |
| **Approximate test lines added** | ~175 |
| **Production files changed** | 7 |

### Per-file line counts (M4.3 production)

| File | Lines |
|------|------:|
| `agents/coder.py` | 111 |
| `prompt/builder.py` | 23 |
| `llm/coder_mock_provider.py` | 29 |
| `prompts/coder/system.md` | 3 |
| `prompts/coder/dependencies.md` | 3 |
| `prompts/coder/source.md` | 3 |
| `prompts/coder/config.md` | 3 |
| `prompts/coder/script.md` | 3 |

---

# 9. Architecture Check

| Item | Answer |
|------|--------|
| Coder `run()` signature unchanged | **YES** |
| `Workspace` model unchanged | **YES** |
| One prompt per `RepositoryTarget` | **YES** |
| One LLM call per `RepositoryTarget` | **YES** |
| One generated file per `RepositoryTarget` | **YES** |
| WorkspaceManager owns all file writes | **YES** |
| Category-specific prompt templates | **YES** |
| LLMProvider abstraction reused | **YES** |
| No provider-specific logic in Coder | **YES** |
| Only routed files populated | **YES** |
| Workflow executable end-to-end | **YES** |
| WorkflowOrchestrator unchanged | **YES** |
| TaskRouter unchanged | **YES** |
| No Runner implementation | **YES** |
| No retry or repair logic | **YES** |
| No circular imports | **YES** |

---

# 10. Changed Files

## `agents/coder.py`

| Field | Detail |
|-------|--------|
| **Why** | M4.3 requires per-target LLM generation and file writes |
| **Responsibility** | Orchestrate skeleton, routing, and incremental population |
| **Implementation** | Added `prompt_builder`, default `CoderMockLLMProvider`, `_populate_repository()`, and prompt formatting helpers |

## `prompt/builder.py`

| Field | Detail |
|-------|--------|
| **Why** | Coder needs category-specific prompt assembly |
| **Responsibility** | Build coder system prompts from resource files |
| **Implementation** | Added `build_coder_prompt(file_category)` loading `system` + category template |

## `llm/coder_mock_provider.py`

| Field | Detail |
|-------|--------|
| **Why** | Deterministic file content for tests and default execution without API keys |
| **Responsibility** | Mock LLM returning content keyed by target path in user message |
| **Implementation** | `CoderMockLLMProvider` with `MOCK_FILE_CONTENT` dict |

## `prompts/coder/*.md`

| Field | Detail |
|-------|--------|
| **Why** | Different file categories require different generation instructions |
| **Responsibility** | Prompt templates for `dependencies`, `source`, `config`, `script` |
| **Implementation** | Five markdown resource files; `system.md` updated for single-file output |

## `tests/test_coder_population.py`

| Field | Detail |
|-------|--------|
| **Why** | M4.3 acceptance criteria require population test coverage |
| **Responsibility** | Unit and integration tests for per-target generation |
| **Implementation** | Six tests with `RecordingLLMProvider` for call counting |

## `tests/test_coder.py`, `tests/test_task_routing.py`, `tests/test_prompt.py`

| Field | Detail |
|-------|--------|
| **Why** | M4.3 changes Coder behavior from skeleton-only to populated repository |
| **Responsibility** | Updated assertions to reflect file population |

---

# 11. Repository Population Flow

## Overview

Population occurs inside `Coder._populate_repository()` after workspace creation, routing storage, and stub initialization. The routing table determines which files to generate; iteration order matches `routing_table.targets` list order.

## Per-target flow

```text
RepositoryTarget
        ↓
_find_task_step(task, target.task_id)           → TaskStep
        ↓
_format_repository_context(populated_paths)     → str (paths generated so far)
        ↓
build_coder_prompt(target.file_category)        → system prompt (str)
        ↓
_format_generation_request(
    paper.title, task_step, target, context
)                                               → user prompt (str)
        ↓
LLMProvider.complete([
    LLMMessage(role="system", ...),
    LLMMessage(role="user", ...),
])                                              → raw file content (str)
        ↓
WorkspaceManager.write_file(
    workspace, target.relative_path, content
)                                               → file on disk
        ↓
populated_paths.append(target.relative_path)
        ↓
next RepositoryTarget (or return)
```

## User prompt structure

Each user message contains:

```text
Paper title: {paper_title}
Engineering task: {task_id} - {task_name}
Task description: {task_description}
Target file: {relative_path}
File category: {file_category}
Repository context:
{context}
```

The `Target file:` line is parsed by `CoderMockLLMProvider` to select mock content.

## System prompt structure

`build_coder_prompt(file_category)` concatenates:

1. `prompts/coder/system.md` — global coder instructions (single file output, no markdown fences)
2. `prompts/coder/{file_category}.md` — category-specific template

Categories map to prompt files:

| `file_category` | Prompt file |
|-----------------|-------------|
| `dependencies` | `dependencies.md` |
| `source` | `source.md` |
| `config` | `config.md` |
| `script` | `script.md` |

## Repository context accumulation

Before the first target, context is `"No repository files generated yet."` After each successful write, `target.relative_path` is appended to `populated_paths`. Subsequent prompts list all prior paths. File contents are not included in context.

## Interaction with M4.1 stubs

`initialize_repository()` runs before `_populate_repository()`. When `requirements.txt` is in the routing table, population overwrites the M4.1 placeholder. `README.md` is not in the routing table and is not overwritten.

---

# 12. File Generation Strategy

## Generation unit

The smallest generation unit is strictly:

```text
One RepositoryTarget → One Prompt → One LLM Completion → One Generated File
```

`Coder._populate_repository()` never batches multiple targets into a single prompt or LLM call.

## Target selection

Targets come exclusively from `TaskRoutingTable.targets` produced by `TaskRouter.route_task()`. No files are generated for paths not in the routing table.

## Content source

Generated content is the raw string returned by `LLMProvider.complete()`. No `ResponseParser`, validation layer, or template engine post-processes the output before `write_file()`.

## Default mock strategy

`CoderMockLLMProvider` maps target paths to predetermined content in `MOCK_FILE_CONTENT`:

| Target path | Mock content summary |
|-------------|---------------------|
| `requirements.txt` | `torch>=2.0.0`, `numpy>=1.24.0` |
| `src/dataset.py` | `Dataset` class placeholder |
| `configs/dataset.yaml` | `dataset.name`, `dataset.path` |
| `src/model.py` | `Model` class placeholder |
| `scripts/train.py` | `main()` printing `"Training complete."` |
| `configs/train.yaml` | `training.epochs`, `training.batch_size` |
| `scripts/evaluate.py` | `main()` printing `"Evaluation complete."` |

Unknown paths receive `# Generated: {path}\n`.

## Prompt differentiation by category

| Category | Prompt emphasis |
|----------|-----------------|
| `dependencies` | Package names and version constraints, one per line |
| `source` | Python module with docstrings and minimal structure |
| `config` | YAML configuration for the target path |
| `script` | Executable Python script for the assigned task |

## Write strategy

All writes go through `WorkspaceManager.write_file()`. Parent directories are created automatically. Each write replaces any existing file at the same path.

## Ordering

Files are generated in the order targets appear in `routing_table.targets`. This order follows `TaskModel.steps` order as produced by `TaskRouter.route_task()`.

## Files explicitly not generated

- `README.md` — stub only, not in routing table
- Files under `outputs/` and `logs/` — not routing targets
- Any path not produced by `TaskRouter` for the given task model
