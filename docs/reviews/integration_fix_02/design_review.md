# Design Review Report — Integration Fix #2 Repository Consistency

**Fix:** integration_fix_02 — Repository Consistency  
**Capability:** Coder (shared generation context)  
**Type:** Product integration fix (MVP)  
**Status:** Implemented  
**Prerequisite:** `docs/reviews/integration_fix_01/failure_analysis.md`

---

# 1. Root Cause

Integration fix #1 showed that repository files were generated **independently** with insufficient cross-file coupling:

| Symptom | Evidence |
|---------|----------|
| Mixed frameworks | `PaperModel.framework=Caffe`, `train.py` used PyTorch, `dataset.py` used Caffe |
| Missing dependencies | `train.py` imported `torch`; `requirements.txt` had no `torch` |
| Broken imports | `evaluate.py` imported `CIFAR10` not defined in `dataset.py` |
| Config mismatch | `configs/train.yaml` used Caffe paths; `train.py` expected different YAML schema |
| Stale README | README said "not generated yet" after population |

**Mechanism:** `Coder._populate_repository()` passed only `paper.title`, a local `TaskStep`, and a list of prior file paths into each LLM call. `PaperModel` engineering fields and a repository-wide contract were not shared across generations.

**Root cause:** Files are generated independently without a shared engineering context reused across all file prompts.

---

# 2. Simplified Design

## Why the original proposal was not implemented

An earlier design draft proposed:

- `ProjectContext` Pydantic model
- `ProjectContextBuilder` with a dedicated LLM call
- `validation/project_context.py` pipeline
- New prompt lifecycle and mock-provider changes

That approach correctly diagnosed the problem but introduced **framework-level abstractions** inappropriate for the current MVP:

| Proposed component | MVP cost |
|--------------------|----------|
| New workflow artifact | Expands orchestrator contract surface |
| Extra LLM call | +latency, +cost, +failure mode per run |
| Validation pipeline | Duplicates Reader/Planner patterns for an internal detail |
| Pydantic model | Persistence/serialization semantics not needed |

## Chosen approach

Solve the engineering problem with the **smallest change inside `Coder` only**:

1. Build a plain Python `dict` from existing `PaperModel` and `TaskModel` before file generation
2. Inject that dict into every per-file LLM user prompt
3. Sort generation order: `requirements.txt` → `src/` → `configs/` → `scripts/`
4. Regenerate `README.md` deterministically after population (no LLM call)

No new agents, builders, models, validation modules, orchestrator changes, or public API changes.

---

# 3. Shared Generation Context

**Location:** `Coder._build_shared_generation_context()` — private, not persisted, not a workflow artifact.

Built deterministically from existing inputs:

```python
{
    "paper_title": paper.title,
    "framework": paper.framework,
    "dataset": paper.dataset,
    "model": paper.model,
    "optimizer": paper.optimizer,
    "loss": paper.loss,
    "training_pipeline": paper.training_pipeline,
    "evaluation_metric": paper.evaluation_metric,
    "python_version": f"{major}.{minor}",      # from sys.version_info
    "repository_files": [...],                   # from TaskRoutingTable
    "source_modules": ["src.dataset", ...],      # import paths for scripts
    "config_files": [...],
    "script_files": [...],
    "train_entrypoint": "scripts/train.py",
    "eval_entrypoint": "scripts/evaluate.py",
    "engineering_tasks": [...],                  # from TaskModel.steps
}
```

**No extra LLM call.** Additional fields (`repository_files`, `source_modules`, entrypoints) are derived from `TaskRoutingTable` and runtime Python version to guide cross-file consistency without new abstractions.

Every file-generation user prompt includes:

1. Shared generation context (JSON)
2. Current repository target
3. Current engineering task
4. Existing generated file paths
5. Explicit consistency instructions

Category prompts (`dependencies`, `source`, `config`, `script`) were updated to instruct the LLM to follow the shared context.

---

# 4. Generation Flow

## Before

```text
PaperModel + TaskModel
        ↓
TaskRouter → targets in task-step order
        ↓
for each target:
    prompt = title + task_step + path + [path list]
    LLM → one file
        ↓
README remains skeleton stub
```

## After

```text
PaperModel + TaskModel
        ↓
TaskRouter → TaskRoutingTable
        ↓
_build_shared_generation_context()     ← dict, no LLM
        ↓
initialize_repository (skeleton)
        ↓
for each target in sorted order:
    dependencies → source → config → script
    prompt = shared context + task + target + [path list]
    LLM → one file
        ↓
_finalize_readme()                     ← deterministic, no LLM
        ↓
Workspace
```

## Canonical sort order

| Priority | `file_category` | Example paths |
|----------|-----------------|---------------|
| 1 | `dependencies` | `requirements.txt` |
| 2 | `source` | `src/dataset.py`, `src/model.py` |
| 3 | `config` | `configs/*.yaml` |
| 4 | `script` | `scripts/train.py`, `scripts/evaluate.py` |

Implemented in `Coder._sort_targets()` using `_CATEGORY_ORDER`.

## README finalization

`Coder._format_populated_readme()` writes a new README via `WorkspaceManager.write_file()` after all routed files are generated. README lists:

- Framework, dataset, model, optimizer, Python version from shared context
- All populated file paths
- Engineering tasks
- Status: source and configuration generation complete

---

# 5. Files Modified

| File | Change |
|------|--------|
| `agents/coder.py` | Shared context dict; target sorting; enriched prompts; README finalization |
| `prompts/coder/dependencies.md` | Follow shared context; include imported packages |
| `prompts/coder/source.md` | Follow shared context; export importable symbols |
| `prompts/coder/config.md` | Follow shared context; match script schema |
| `prompts/coder/script.md` | Follow shared context; import only listed modules |
| `tests/test_coder.py` | README expectations after finalization |
| `tests/test_coder_population.py` | Context-in-prompt, generation order, README tests |

## Unchanged (frozen)

| Component | Reason |
|-----------|--------|
| `Coder.run(paper, task, patch_plan=None) -> Workspace` | Public API |
| `WorkflowOrchestrator` | No workflow changes |
| `TaskRouter` | Routing logic unchanged |
| `WorkspaceManager` public methods | No new public API |
| `Workspace` model | No new fields |

---

# 6. Remaining Limitations

| Limitation | Description |
|------------|-------------|
| **Prompt-enforced consistency** | No AST or import verification. LLM may still violate shared context. |
| **No dependency pinning logic** | Context includes `python_version` but does not auto-fix incompatible pins (e.g. `numpy<1.24` on 3.13). |
| **Routing coverage unchanged** | `TaskRouter` may still omit `src/model.py` if keywords do not match. |
| **Path-only repository context** | Later prompts see prior file paths, not file contents. |
| **Framework follows PaperModel** | If Reader extracts `Caffe`, all files are instructed to use Caffe — consistency over forcing PyTorch. |
| **README is not LLM-generated** | Reflects context and paths deterministically; may omit implementation details inside files. |

---

# 7. Validation Checklist

## Shared context

- [ ] `_build_shared_generation_context()` runs once per `Coder.run()` before any file LLM call
- [ ] Every file-generation user prompt contains `Shared generation context:` with `framework`, `dataset`, `model`
- [ ] `python_version` matches `sys.version_info` of the host interpreter
- [ ] `source_modules` lists import paths for all routed `src/*.py` files

## Generation order

- [ ] `requirements.txt` is generated before `src/`, `configs/`, and `scripts/`
- [ ] `src/` files are generated before `scripts/`

## README

- [ ] README does not contain "have not been generated yet" after `Coder.run()`
- [ ] README lists all populated files under `## Generated Files`
- [ ] README states framework and dataset from shared context

## Repository consistency (integration acceptance)

- [ ] Framework referenced consistently across generated files (manual / grep review)
- [ ] `requirements.txt` includes packages imported in `src/` and `scripts/`
- [ ] `scripts/train.py` imports only from `source_modules` in context
- [ ] `scripts/evaluate.py` imports only from `source_modules` in context
- [ ] Config YAML structure matches what scripts load

## Regression

- [ ] `Coder.run()` signature unchanged
- [ ] All unit tests pass
- [ ] Mock LLM path works without API key

---

## Acceptance mapping

| Criterion | Implementation |
|-----------|----------------|
| Framework consistent everywhere | Shared context `framework` in every prompt + category prompt rules |
| Requirements match imports | Context lists `source_modules` / `script_files`; dependencies prompt requires all imports |
| Scripts import existing modules | Context `source_modules` + script prompt rules |
| Configs match scripts | Context `config_files` + config/script prompt rules |
| README matches repository | `_finalize_readme()` after population |

---

## Related evidence

| Document | Relevance |
|----------|-----------|
| `docs/reviews/integration_fix_01/failure_analysis.md` | ISSUE-04 through ISSUE-08 |
| `agents/coder.py` | Implementation |
| `docs/reviews/M4.3/design_review.md` | Baseline per-file generation |
