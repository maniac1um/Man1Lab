# M4.1 Workspace Construction — Design Review Report

**Milestone:** M4.1 — Workspace Construction  
**Date:** 2026-06-28  
**Status:** Complete

---

## 1. Workspace Construction Pipeline

```text
TaskModel (+ PaperModel)
        ↓
    Coder.run()
        ↓
WorkspaceManager.create_workspace(paper_slug)
        ↓
WorkspaceManager.initialize_repository(workspace, paper_title, task, patch_plan?)
        ↓
    Workspace
```

`Coder.run()` derives a slug from `PaperModel.title`, delegates directory and file creation to `WorkspaceManager`, and returns a `Workspace` model. No LLM calls occur in this pipeline.

---

## 2. Repository Layout

Each reproduction workspace is created at:

```text
workspace/tasks/{paper_slug}/
├── src/
├── configs/
├── scripts/
├── outputs/
├── logs/
├── README.md
└── requirements.txt
```

`paper_slug` is derived from the paper title (lowercase, non-alphanumeric characters replaced with underscores). Subdirectories are created empty. `README.md` and `requirements.txt` are stub files written during initialization.

---

## 3. WorkspaceManager Responsibilities

`WorkspaceManager` is the sole component that performs filesystem operations for repository construction.

| Method | Role |
|--------|------|
| `create_workspace(paper_slug)` | Creates `workspace/tasks/{slug}/` and empty subdirectories |
| `initialize_repository(workspace, paper_title, task, patch_plan?)` | Writes `README.md` and `requirements.txt` |
| `write_file(workspace, relative_path, content)` | Generic file write (used by `initialize_repository`) |
| `read_file(workspace, relative_path)` | File read |
| `write_output(workspace, relative_path, content)` | Write to workspace `outputs/` |
| `write_report(report, filename)` | Write final report to project `outputs/` |

Private helpers `_format_readme()` and `_format_requirements()` generate stub file content. The constant `REPOSITORY_SUBDIRS` defines the required directory list.

---

## 4. Coder Integration

`Coder` receives `PaperModel`, `TaskModel`, and an optional `PatchPlan` (unchanged public signature). It:

1. Computes `paper_slug` from `paper.title`
2. Calls `workspace_manager.create_workspace(slug)`
3. Calls `workspace_manager.initialize_repository(workspace, paper.title, task, patch_plan)`
4. Returns the `Workspace` object

`Coder` does not call filesystem APIs directly. The `llm` constructor parameter is retained but unused in this milestone.

---

## 5. Public APIs

### Unchanged

| Component | Contract |
|-----------|----------|
| `Coder.__init__(workspace_manager, llm=None)` | Unchanged |
| `Coder.run(paper, task, patch_plan=None) -> Workspace` | Unchanged |
| `WorkspaceManager.create_workspace(paper_slug) -> Workspace` | Unchanged signature; path layout updated to `{slug}` without timestamp prefix |
| `WorkspaceManager.write_file` | Unchanged |
| `WorkspaceManager.read_file` | Unchanged |
| `WorkspaceManager.write_output` | Unchanged |
| `WorkspaceManager.write_report` | Unchanged |
| `WorkflowOrchestrator.run(paper_path) -> ReportModel` | Unchanged |

### Added

| Method | Signature |
|--------|-----------|
| `WorkspaceManager.initialize_repository` | `(workspace, paper_title, task, patch_plan=None) -> None` |

### Module constant

| Name | Value |
|------|-------|
| `REPOSITORY_SUBDIRS` | `("src", "configs", "scripts", "logs", "outputs")` |

---

## 6. Test Coverage

**New file:** `tests/test_coder.py` (7 tests)

| Test | Verifies |
|------|----------|
| `test_creates_workspace_directory` | Workspace path created under `workspace/tasks/{slug}/` |
| `test_required_folders_exist` | All five subdirectories exist |
| `test_readme_generated` | `README.md` contains title, tasks, and not-generated notice |
| `test_requirements_txt_generated` | `requirements.txt` placeholder exists |
| `test_returns_workspace_object` | Correct `Workspace` fields returned |
| `test_no_source_code_generated` | `src/`, `scripts/`, `configs/` remain empty |
| `test_initialize_repository_writes_stub_files` | `WorkspaceManager.initialize_repository` writes both stub files |

**Regression:** `tests/test_smoke.py` — end-to-end workflow completes successfully.

**Total:** 40 tests passing.

---

## 7. Current Limitations

- No source code, configuration, or script files are generated.
- `requirements.txt` contains only a comment placeholder.
- `Coder` retains an unused `llm` parameter for future M4.2 integration.
- `depends_on` task relationships from Planner validation are not reflected in the README.
- Workspace path uses slug only (no timestamp suffix); re-running Coder for the same paper overwrites the existing workspace directory contents via `write_file`.
- `Runner` still returns a mock `ExecutionResult` referencing `scripts/train.py`, which does not exist in the skeleton.

---

## 8. Code Metrics

| File | Lines |
|------|------:|
| `agents/coder.py` | 39 |
| `workspace/manager.py` | 167 |
| `tests/test_coder.py` | 122 |
| **Total (changed/added)** | **328** |

Net change: +87 lines in existing files, +122 lines new test file.

---

## 9. Architecture Check

**YES**

- Agents do not manipulate files directly; `WorkspaceManager` owns filesystem operations.
- `Coder.run()` signature unchanged.
- `WorkflowOrchestrator` integration unchanged.
- Communication via Pydantic models (`PaperModel`, `TaskModel`, `Workspace`) preserved.
- No LLM calls in Coder.
- No Runner, Reviewer, or execution changes.

---

## 10. Changed Files

| File | Change |
|------|--------|
| `agents/coder.py` | Refactored to delegate repository construction to `WorkspaceManager`; removed mock source file generation |
| `workspace/manager.py` | Added `initialize_repository`, `REPOSITORY_SUBDIRS`, README/requirements formatters; updated `create_workspace` path layout |
| `tests/test_coder.py` | New — workspace construction tests |
| `docs/reviews/M4.1/cursor_report.md` | New — this report |
