# Design Review Report — Integration Fix #3 Cross-file Contract Consistency

**Fix:** integration_fix_03 — Cross-file Contract Consistency  
**Capability:** Coder (repository contract extension)  
**Type:** Product integration fix (MVP)  
**Status:** Design (revised)  
**Prerequisite:** [integration_fix_02/validation_report.md](../integration_fix_02/validation_report.md)

---

## Design Revision (role-based contract)

This document was revised after initial review. The following sections changed; root cause analysis (§1) and architectural constraints remain valid.

### 1. What changed

| Area | Previous design | Revised design |
|------|-----------------|----------------|
| Export model | Canonical function names (`get_dataset`, `build_model`) | **Interface roles** (e.g. Dataset Provider, Model Builder) |
| Cross-file binding | Predeclared symbol lists in contract | **Role obligations** + **interface registry** updated during generation |
| Config agreement | Fixed `required_keys` / flat schema template | **Configuration expectations** (semantic fields); keys recorded when configs are generated |
| Script imports | Hardcoded `imports` map with symbol names | Scripts consume **recorded interfaces** from upstream modules |
| Prompt obedience | “Implement exactly `get_dataset`” | “Fulfill role; downstream files must use interfaces you establish” |

Target-specific contract slices, generation order, README deduplication, and Runner entrypoint **expectations** are unchanged.

### 2. Why canonical API names were removed

Predefined names (`get_dataset`, `build_model`) improved consistency but turned Coder into a **repository template engine**. Every paper would converge on the same API surface regardless of Reader output, Planner tasks, or paper-specific engineering choices.

That conflicts with the Research Agent goal: **reproduce arbitrary papers**, not emit variants of one scaffold. Canonical names are framework-level conventions; they belong outside a generic generation system.

The revision keeps coordination benefits without prescribing implementation vocabulary.

### 3. How interface-role contracts improve generality

The contract now describes **what each module must provide**, not **what it must be called**:

- *Dataset Provider* — supplies training and validation data access for downstream scripts
- *Model Builder* — supplies a trainable model when `src/model.py` is routed
- *Training Entrypoint* — runnable under the fixed Runner invocation
- *Training Configuration* — exposes hyperparameters and dataset references scripts will read

The LLM chooses concrete function names, class names, and YAML keys appropriate to the paper and shared generation context. **Consistency is enforced by propagation**, not by pre-assigned identifiers.

### 4. Why this better supports arbitrary research papers

Interface roles are derived from **routing and engineering responsibility**, which already vary per paper:

- A CIFAR-10–only task plan may route dataset without ImageNet-specific APIs
- A paper without a separate model module omits the Model Builder role
- Config expectations reference `PaperModel` themes (optimizer, dataset) without fixing key strings

The generated repository shape follows **paper + TaskModel + TaskRoutingTable**, not a global template. Two papers may produce different public APIs while still satisfying the same role contract.

### 5. Why architecture complexity remains unchanged

| Constraint | Status |
|------------|--------|
| Internal plain `dict` only | Yes — contract + in-memory registry |
| No workflow artifacts | Yes — registry is Coder loop state, not persisted |
| No extra LLM calls | Yes |
| No new agents, builders, validators, Pydantic models | Yes |
| `Coder.run()` unchanged | Yes |
| `WorkflowOrchestrator` unchanged | Yes |

The registry adds a small in-loop data structure (like `populated_paths` today). It coordinates generation; it is not an engineering framework.

---

## 1. Root Cause

Integration Fix #2 established a **Shared Generation Context** that aligned repository-wide engineering themes (framework, dataset, optimizer, file list, generation order). Validation showed measurable improvement — dependencies install, PyTorch stack coherence, README finalization — but execution still failed because **independently generated files disagree on interfaces**.

| Defect | Symptom | What shared context provided | What was missing |
|--------|---------|------------------------------|------------------|
| DEFECT-01 | `train.py` imports `get_dataset`; `dataset.py` exports `get_cifar10_loaders` | `source_modules: ["src.dataset"]` | No agreement on module interface |
| DEFECT-02 | `evaluate.py` imports `get_cifar10_test_loader` | Same module list | No shared consumption model |
| DEFECT-03 | `train.yaml` nested keys vs `train.py` flat `config.get()` | Generic “match config” instruction | No configuration agreement |
| DEFECT-04 | `train.py` requires `--model`; Runner runs `python scripts/train.py` | `train_entrypoint` path only | No execution expectation tied to Runner |

**Mechanism:** `source_modules` tells the LLM *which modules exist* but not *what interface they expose* or *how downstream files must use them*. Each per-file LLM call still invents symbols, YAML shapes, and CLI definitions independently.

**Root cause:** Shared generation context describes engineering themes, not **interface relationships**. Generated files share context but not a binding agreement on responsibilities, configuration shape, and entrypoint behavior.

This is a generation-logic problem, not a defect in one ResNet workspace. Patching individual `ImportError`s would not generalize.

---

## 2. Repository Contract Design

### Principle

Add a **Repository Contract** — a plain Python `dict`, built deterministically inside `Coder` before file generation, alongside the existing shared generation context.

The contract is a **coordination mechanism**, not an engineering framework. It describes responsibilities and relationships. It does **not** prescribe canonical function names, class names, or repository templates.

| Property | Value |
|----------|-------|
| Location | `Coder._build_repository_contract()` |
| Type | `dict[str, object]` |
| Persisted | No |
| Workflow artifact | No |
| LLM call | No |
| Validation pipeline | No |
| Pydantic model | No |

### Relationship to Shared Generation Context

```text
PaperModel + TaskModel + TaskRoutingTable
        ↓
_build_shared_generation_context()   → engineering themes (from paper)
_build_repository_contract()          → interface roles (from routing)
        ↓
both injected into every file-generation prompt
        ↓
during population: interface_registry updated after upstream files
```

Shared context answers *what the paper requires*. Repository contract answers *what each file role must provide or consume*.

### Interface roles (replace canonical exports)

Instead of `exports: { get_dataset, build_model }`, the contract declares **module roles** derived from routing targets:

```python
{
    "module_roles": {
        "src/dataset.py": {
            "role": "Dataset Provider",
            "module_path": "src.dataset",
            "provides": [
                "training data access for the training script",
                "validation data access for the training script",
            ],
            "expected_interface": (
                "Callable or factory that returns data structures "
                "required by the training script (e.g. dataloaders or datasets)."
            ),
            "consumers": ["scripts/train.py", "scripts/evaluate.py"],
        },
        "src/model.py": {
            "role": "Model Builder",
            "module_path": "src.model",
            "provides": ["trainable model construction from configuration"],
            "expected_interface": (
                "Callable or class that builds a model object usable by the training script."
            ),
            "consumers": ["scripts/train.py"],
            # omitted entirely when src/model.py not in routing table
        },
    },
    "configuration_roles": {
        "configs/train.yaml": {
            "role": "Training Configuration",
            "serves": ["scripts/train.py"],
            "must_expose": [
                "dataset selection or reference",
                "batch size",
                "optimizer hyperparameters referenced in shared context",
            ],
            "style_expectation": (
                "Use one consistent top-level key layout; scripts will read "
                "the same keys this file defines."
            ),
        },
        "configs/dataset.yaml": {
            "role": "Dataset Configuration",
            "serves": ["src/dataset.py"],
            "must_expose": [
                "dataset paths or download settings",
            ],
        },
    },
    "execution_expectations": {
        "scripts/train.py": {
            "role": "Training Entrypoint",
            "runner_invocation": "python scripts/train.py",
            "must_succeed_without_extra_cli_args": true,
            "loads_configuration_from": "configs/train.yaml",
            "must_consume": [
                "Dataset Provider interface",
                "Model Builder interface if model module routed",
                "Training Configuration keys",
            ],
        },
        "scripts/evaluate.py": {
            "role": "Evaluation Entrypoint",
            "must_reuse": [
                "Dataset Provider interface (same access pattern as training)",
            ],
        },
    },
    "relationships": [
        {
            "from": "scripts/train.py",
            "to": "src/dataset.py",
            "relationship": "imports dataset access from Dataset Provider",
        },
        {
            "from": "scripts/train.py",
            "to": "configs/train.yaml",
            "relationship": "reads training hyperparameters and dataset reference",
        },
        # additional edges derived from routing table
    ],
    "file_responsibilities": {
        "requirements.txt": "Declare packages imported by all generated Python files.",
        "src/dataset.py": "Fulfill Dataset Provider role; no training loop.",
        "src/model.py": "Fulfill Model Builder role when routed.",
        "configs/*.yaml": "Fulfill configuration role for served modules/scripts.",
        "scripts/train.py": "Orchestrate training using upstream interfaces only.",
        "scripts/evaluate.py": "Evaluate using Dataset Provider; do not redefine dataset access.",
    },
}
```

**The contract does not contain symbol names.** It contains roles, obligations, consumers, and relationships.

### Interface registry (in-loop coordination)

To connect roles without preset APIs, Coder maintains an internal **`interface_registry`** during `_populate_repository()`:

```python
# Example shape — implementation detail, not persisted
{
    "src/dataset.py": {
        "public_symbols": ["load_dataloaders"],  # recorded after file generation
        "symbol_kinds": {"load_dataloaders": "function"},
    },
    "configs/train.yaml": {
        "top_level_keys": ["dataset", "batch_size", "learning_rate", "momentum"],
    },
}
```

**Recording mechanism (implementation detail):**

- After each `source` or `config` file is written, Coder extracts a lightweight summary (e.g. top-level `def`/`class` names from Python; top-level YAML keys from config).
- No extra LLM call. No workflow artifact. Registry exists only for the duration of `Coder.run()`.
- Subsequent prompts include: repository contract + **current interface registry**.

This realizes the flow:

```text
Repository Contract (roles)
        ↓
Prompt → LLM chooses implementation
        ↓
Interface recorded in registry
        ↓
Later files reuse recorded interfaces (not invented names)
```

Scripts are instructed to import **only symbols listed in the registry** for upstream modules and to read **only keys listed in the registry** for upstream configs.

### Deterministic derivation rules

Contract **roles** are derived from `TaskRoutingTable.targets` and shared context themes — not from paper-specific hardcoding.

| Routing signal | Contract rule |
|----------------|---------------|
| `src/dataset.py` routed | Add **Dataset Provider** role |
| `src/model.py` routed | Add **Model Builder** role; train script must consume it |
| `src/model.py` not routed | Omit Model Builder; train script may define model inline |
| `configs/train.yaml` routed | Add **Training Configuration** role with `must_expose` from shared context (`optimizer`, `dataset`) |
| `configs/dataset.yaml` routed | Add **Dataset Configuration** role |
| `scripts/train.py` routed | Add **Training Entrypoint** execution expectations |
| `scripts/evaluate.py` routed | Must reuse Dataset Provider per relationship edges |

Relationships are generated as edges between routed paths (script → source, script → config, source → config).

### Entrypoint alignment with Runner

`ExecutionPlanner` (unchanged) produces `[venv_python, "scripts/train.py"]`.

The contract states an **execution expectation**, not a CLI template:

- Training entrypoint must succeed when invoked exactly as the Runner runs it
- No `required=True` CLI arguments unless Runner is extended (out of scope)
- Configuration path may default internally; behavior is an implementation choice

**No `ExecutionPlanner` or orchestrator change** required.

---

## 3. Generation Flow

### Before (integration_fix_02)

```text
_build_shared_generation_context()
        ↓
for target in sorted(routing_table.targets):
    prompt = shared_context + task + target + [path list]
    LLM → one file
        ↓
_finalize_readme()
```

### After (integration_fix_03, revised)

```text
shared_context = _build_shared_generation_context(...)
contract = _build_repository_contract(routing_table, shared_context)
interface_registry = {}
        ↓
for target in sorted(routing_table.targets):
    prompt = shared_context
           + repository_contract
           + target-specific role slice
           + interface_registry (commitments from prior files)
           + task + target + [path list]
           + role obedience instructions
    LLM → one file
    update interface_registry if target is source or config
        ↓
_finalize_readme(unique populated_paths)
```

### Generation order (unchanged)

```text
requirements.txt → src/ → configs/ → scripts/ → README.md
```

Order ensures: source interfaces recorded before configs/scripts; config keys recorded before scripts.

### Target-specific contract slices (unchanged pattern, revised content)

| Category | Slice emphasizes |
|----------|------------------|
| `dependencies` | Packages needed for declared roles and registry commitments |
| `source` | Module role, `provides`, `expected_interface`; establish symbols downstream will import |
| `config` | Configuration role, `must_expose`; establish keys downstream will read |
| `script` | Consumption obligations; import from registry; fulfill entrypoint execution expectations |

### README deduplication (minor)

`_finalize_readme()` lists **unique** `populated_paths` (preserve order) to fix DEFECT-05.

---

## 4. Prompt Changes

No new prompt files. Category prompts and user prompt updated.

### User prompt (`_format_generation_request`)

```text
Shared generation context:
{json}

Repository contract (interface roles):
{json}

Interface registry (commitments from files already generated):
{json or "No interfaces recorded yet."}

Contract obligations for this target:
{target-specific role slice}

Rules:
- Fulfill the interface role for this file; choose appropriate names for this paper.
- If you are a source or config file, expose a clear public interface downstream files can use.
- If you are a script, import ONLY symbols listed in the interface registry for upstream modules.
- If you are a script, read ONLY configuration keys listed in the interface registry for config files.
- Do not invent alternate dataset/model access patterns if a provider module exists.
- Training entrypoint must run as: python scripts/train.py (no required CLI args).
```

### Category prompt updates

| File | Addition |
|------|----------|
| `prompts/coder/source.md` | Fulfill the module role in the repository contract; export a stable public interface for consumers. |
| `prompts/coder/script.md` | Consume interfaces from the registry; satisfy execution expectations; do not duplicate provider logic. |
| `prompts/coder/config.md` | Fulfill configuration role; expose keys scripts will read; keep layout consistent. |
| `prompts/coder/dependencies.md` | Cover imports used by role implementations in this repository. |

### Mock provider

`CoderMockLLMProvider` produces registry-consistent symbols across mock files (symbols align between mock `dataset.py` and `train.py`) without hardcoding paper-specific names in the contract itself.

---

## 5. Files Modified

| File | Change |
|------|--------|
| `agents/coder.py` | `_build_repository_contract()`; `interface_registry` in population loop; registry extraction helper; role-based prompt slices; README dedupe |
| `prompts/coder/source.md` | Role fulfillment |
| `prompts/coder/script.md` | Registry consumption, execution expectations |
| `prompts/coder/config.md` | Configuration role |
| `prompts/coder/dependencies.md` | Role-driven dependencies |
| `llm/coder_mock_provider.py` | Registry-aligned mock output |
| `tests/test_coder_population.py` | Contract + registry in prompts; cross-file alignment |
| `tests/test_coder_contract.py` | **New** — role derivation from routing table; registry recording |

### Unchanged (frozen)

| Component | Reason |
|-----------|--------|
| `Coder.run(paper, task, patch_plan=None) -> Workspace` | Public API |
| `WorkflowOrchestrator` | No orchestration changes |
| `ExecutionPlanner` | Runner command fixed; execution expectations align generation |
| `TaskRouter` | Routing unchanged |
| New agents, models, validation modules | Out of scope |

---

## 6. Remaining Limitations

| Limitation | Description |
|------------|-------------|
| **Prompt- and registry-enforced** | No full AST validation; extraction may miss dynamic exports. |
| **Registry extraction fragility** | Complex `__all__` or re-exports may not be captured; MVP uses simple top-level scan. |
| **LLM may violate registry** | Scripts may still invent imports; no auto-retry in this fix. |
| **Role vocabulary is internal** | Role names (Dataset Provider, etc.) are Coder coordination labels, not user-facing APIs. |
| **Routing coverage** | Omitted routes omit roles; contract cannot require files not in routing table. |
| **evaluate.py not run by Runner** | Evaluation entrypoint aligned by prompt; not E2E-validated until executed. |
| **LLM / data variance** | Passing import stage does not imply successful training. |

---

## 7. Acceptance Checklist

### Repository contract

- [ ] `_build_repository_contract()` runs once per `Coder.run()` before file generation
- [ ] Contract derived from `TaskRoutingTable` + shared context — no LLM call
- [ ] Contract describes **roles and relationships**, not canonical symbol names
- [ ] Contract not persisted to workspace or workflow history

### Interface registry

- [ ] Registry updated after each generated `source` and `config` file
- [ ] Registry included in prompts for downstream targets
- [ ] Registry discarded after `Coder.run()` completes

### Cross-file consistency

- [ ] `scripts/train.py` imports only symbols present in registry for upstream modules
- [ ] `scripts/evaluate.py` uses same dataset access pattern as recorded for Dataset Provider
- [ ] No duplicate dataset/model provider logic across scripts and source modules

### Configuration

- [ ] `scripts/train.py` reads configuration keys that appear in registry for `configs/train.yaml`
- [ ] Config and script use the same top-level key layout (no nested vs flat mismatch)

### Entrypoint

- [ ] `scripts/train.py` runs with `python scripts/train.py` (no required CLI args)
- [ ] Matches `ExecutionPlanner` command
- [ ] No orchestrator or ExecutionPlanner changes

### Repository / README

- [ ] README lists unique generated files after population
- [ ] No manual post-processing of generated repositories

### Architecture / regression

- [ ] `Coder.run()` signature unchanged
- [ ] No new workflow artifacts
- [ ] No additional LLM calls per run
- [ ] All unit tests pass
- [ ] Integration run: `train.py` passes import stage (training may still fail on data/runtime)

---

## How This Improves Consistency Without Expanding Architecture

Integration Fix #2 answered: *“What engineering world are we building?”*  
Integration Fix #3 answers: *“How do files depend on each other?”*

The revised design coordinates generation through **roles and recorded interfaces**, not through a predefined API catalog. The Research Agent remains a paper-driven reproduction system; Coder gains an internal mechanism to prevent each file from inventing incompatible wires.

The contract coordinates. The LLM implements. The registry propagates. Architecture stays frozen.

---

## Related Documents

| Document | Relationship |
|----------|--------------|
| [integration_fix_02/validation_report.md](../integration_fix_02/validation_report.md) | DEFECT-01 through DEFECT-04 motivate this fix |
| [integration_fix_02/design_review.md](../integration_fix_02/design_review.md) | Shared generation context baseline |
| [CURRENT_STATUS.md](../../CURRENT_STATUS.md) | Active integration blockers |
| `execution/execution_planner.py` | Fixed Runner command reference |
| `agents/coder.py` | Implementation target |
