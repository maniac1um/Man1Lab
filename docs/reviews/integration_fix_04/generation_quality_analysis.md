# Generation Quality Analysis — Integration Fix #4

**Milestone:** integration_fix_04 (design investigation)  
**Type:** Design analysis only — no code, prompt, or architecture changes  
**Prerequisite:** [M8.1 acceptance report](../M8.1/acceptance_report.md), [integration_fix_03 design](../integration_fix_03/design_review.md)  
**Scope:** Why coordinated generation still permits inconsistent repositories for arbitrary papers

---

## 1. Executive Summary

Integration Fix #2 (Shared Generation Context) and Integration Fix #3 (Repository Contract + Interface Registry) measurably improved cross-file coordination. The M8.1 acceptance run confirmed partial success: symbol naming between `dataset.py` and `train.py` aligned (`create_data_loaders`), README deduplication worked, and environment preparation installed declared packages successfully.

The repository still failed acceptance because coordination is **informational, not enforced**. Every consistency mechanism stops at the LLM prompt boundary. There is no deterministic validation, reconciliation pass, or feedback loop inside `Coder` after a file is written.

The dominant structural weakness is a **temporal ordering paradox**: `requirements.txt` is generated first, before any Python file exists and before the interface registry contains import information. The contract assigns `requirements.txt` the responsibility to “declare packages imported by all generated Python files,” but the system provides no downstream data to fulfill that obligation at generation time.

Secondary weaknesses cluster into four categories:

| Category | Core gap |
|----------|----------|
| **Incomplete contract** | Roles describe semantics in prose; no machine-checkable obligations for framework, imports, nested config shape, or cross-script consistency |
| **Shallow registry** | Records symbol names and top-level YAML keys only; omits imports, nested keys, framework choice, and script-to-script alignment |
| **Weak constraint language** | Prompts and inline rules use “Follow,” “Fulfill,” and “If you are…” — suggestions the LLM can override per file |
| **Upstream routing loss** | `TaskRouter` keyword heuristics drop or collapse TaskModel steps before Coder sees them; duplicate paths are regenerated and last-write-wins |

**Conclusion:** The current system is a **soft-coordination pipeline** (context injection + advisory registry), not a **closed-loop generation contract**. Inconsistency is an expected emergent property when a real LLM independently interprets loosely worded obligations across 10+ sequential calls.

This document explains *why* that happens generically, using M8.1 symptoms as illustrations rather than as the analysis subject.

---

## 2. Root Cause Analysis

### RC-01 — Coordination without enforcement

```text
PaperModel + TaskModel
        ↓
Shared Context + Repository Contract (deterministic dicts)
        ↓
Per-file LLM call (stochastic interpretation)
        ↓
File written unconditionally
        ↓
Lightweight registry append (symbols / top-level keys only)
        ↓
Next file (repeat)
```

Nothing between “file written” and “next prompt” verifies:

- imports ⊆ `requirements.txt`
- `framework` consistency across files
- config key paths match between producer and consumer
- routed files exist for all TaskModel categories

Fix #2 and Fix #3 improved **what information is shown** to the LLM. They did not add **what the system rejects or repairs**. A coordinated generation system that only *suggests* alignment will still permit divergence whenever the LLM’s per-call optimum differs from the repository-wide optimum.

### RC-02 — Requirements generated before evidence exists

Canonical generation order (`agents/coder.py`):

```text
dependencies (0) → source (1) → config (2) → script (3)
```

Within each category, targets sort by `relative_path`. For a typical multi-task plan this yields:

1. `requirements.txt` — **interface registry empty**
2. `src/dataset.py` — registry updated
3. `configs/dataset.yaml` — registry updated
4. `configs/train.yaml` — registry updated
5. `scripts/evaluate.py` — registry has upstream symbols (alphabetically before `train.py`)
6. `scripts/train.py` — registry complete for upstream, but requirements already finalized

At step 1, the contract slice for `requirements.txt` says:

> “Declare packages imported by all generated Python files.”

The user prompt’s registry block says:

> “No interfaces recorded yet.”

The dependencies category prompt (`prompts/coder/dependencies.md`) instructs:

> “Include packages required by the module roles and recorded interfaces in this repository.”

**There are no recorded interfaces yet.** The LLM must guess future imports from `PaperModel.framework`, task descriptions, and role prose. That is prediction, not propagation.

Mock-based tests mask this: `CoderMockLLMProvider` always emits `torch>=2.0.0` in `requirements.txt` regardless of registry state. Real LLM runs are not bound by mock behavior.

### RC-03 — Framework is context, not constraint

`shared_generation_context["framework"]` is copied from `PaperModel.framework` and injected into every prompt as JSON. Neither the repository contract nor category prompts contain a **hard framework obligation**:

| Location | Framework treatment |
|----------|---------------------|
| `prompts/coder/source.md` | No framework mention |
| `prompts/coder/script.md` | No framework mention |
| `prompts/coder/dependencies.md` | No framework-to-package mapping |
| `repository_contract` | No `framework_binding` or per-file framework role |
| Inline `Rules:` in `_format_generation_request` | No framework rule |

The LLM may therefore choose PyTorch for `train.py`, Caffe for `evaluate.py`, and NumPy/PIL for `dataset.py` while `framework: "Caffe"` sits inert in the JSON block. README finalization (`_finalize_readme`) copies `framework` from shared context into documentation, which can disagree with generated code — documentation reflects PaperModel, code reflects per-file LLM choices.

This is generic: any paper whose historical framework differs from modern defaults (Caffe→PyTorch, Theano→TensorFlow, custom C++ bindings) will expose the same split unless framework is a **binding contract field**, not a **theme field**.

### RC-04 — Registry records names, not semantics

`_record_interface_registry()` extracts:

- Python: top-level `def` / `class` names via regex
- YAML: top-level keys only (lines not indented)

It does **not** record:

| Missing signal | Consequence |
|----------------|-------------|
| `import` / `from` statements | Requirements cannot be derived from scripts |
| Nested YAML paths (`model.arch`, `lr_schedule.base_lr`) | Scripts can legally diverge on nested access while top-level keys “match” |
| Function signatures / parameter expectations | `create_data_loaders(config)` vs `create_data_loaders(dataset_dir, batch_size)` undetected |
| Framework imports (`torch`, `caffe`) | Cross-file framework mixing undetected |
| Which config file a consumer actually reads | `train.py` passing `train.yaml` to a dataset API expecting `dataset.yaml` shape |

Script prompts say “read ONLY configuration keys listed in the interface registry.” If `train.yaml` registers top-level key `dataset` (string) but `train.py` accesses `cfg['dataset']['name']` (nested), the rule is already violated — and nothing detects it.

### RC-05 — Configuration roles are siloed

Repository contract defines separate configuration roles:

- `configs/dataset.yaml` → serves `src/dataset.py`
- `configs/train.yaml` → serves `scripts/train.py`

Relationships include `src/dataset.py → configs/dataset.yaml` and `scripts/train.py → configs/train.yaml`. There is **no relationship** governing what config object flows across the dataset boundary when `train.py` calls `create_data_loaders(cfg)`.

Each config file is generated in its own LLM call with its own `task_step` context. The training script call does not receive a machine-readable commitment of which keys `create_data_loaders` expects — only the symbol name from registry.

For arbitrary papers, multi-file config composition (train hyperparameters vs data paths vs model architecture) is a primary source of schema mismatch. Role-based contracts describe *who reads a file*, not *what object crosses module boundaries*.

### RC-06 — TaskRouter collapses TaskModel before Coder runs

`TaskRouter._classify_step()` uses keyword heuristics on `name + description`. Effects that apply to any paper:

| Pattern | Effect |
|---------|--------|
| Step text lacks both `model` and (`implement` \| `implementation`) | Model steps produce **zero** `src/model.py` targets |
| Multiple dataset steps | Duplicate `src/dataset.py` + `configs/dataset.yaml` targets; last generation overwrites |
| Multiple training steps | Duplicate `scripts/train.py` + `configs/train.yaml`; last wins |
| Multiple evaluation steps | Duplicate `scripts/evaluate.py`; last wins |
| Steps without env/dataset/model/train/eval keywords | **Silently dropped** — no file, no contract role |

Coder faithfully generates files for **routed targets only**. TaskModel may list ten engineering steps while the routing table collapses to six unique paths with repeated overwrites. README lists all TaskModel steps as “complete” after population regardless of routing coverage.

This is upstream of Fix #3 but directly explains “task plan not reflected in repository layout” without blaming the ResNet run specifically.

### RC-07 — Tests validate prompt presence, not repository validity

`tests/test_coder_contract.py` and `tests/test_coder_population.py` verify:

- Contract JSON appears in prompts
- Registry symbols appear before `train.py` generation
- Mock provider imports registry symbols

They do **not** verify:

- Import closure against `requirements.txt`
- Framework homogeneity
- Nested config alignment
- Full TaskModel coverage in routing table

The test suite optimizes for **coordination data reachability**, not **coordination outcome**. Passing tests are compatible with failing acceptance.

---

## 3. Information Flow Review

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         UPSTREAM (deterministic)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  PDF → Reader → PaperModel.framework, dataset, model, ...               │
│  PaperModel → Planner → TaskModel.steps (rich, paper-specific)          │
│  TaskModel → TaskRouter → TaskRoutingTable.targets (collapsed, lossy)   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    CODER PRE-GENERATION (deterministic)                  │
├─────────────────────────────────────────────────────────────────────────┤
│  _build_shared_generation_context()                                      │
│    • engineering themes from PaperModel                                  │
│    • file lists from routing table (not full TaskModel)                  │
│  _build_repository_contract()                                            │
│    • role prose from routing paths                                       │
│    • relationships as labeled edges (no schemas)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│              PER-TARGET LOOP (stochastic LLM, weak feedback)             │
├─────────────────────────────────────────────────────────────────────────┤
│  Inputs per call:                                                        │
│    • system prompt (category template — soft language)                   │
│    • shared context JSON (full, every call)                              │
│    • full repository contract JSON (every call — not sliced only)      │
│    • contract_slice (target-specific obligations)                        │
│    • interface_registry (partial, grows during loop)                     │
│    • task_step for THIS target (may differ on duplicate paths)           │
│    • repository_context (path list only — not file contents)           │
│    • inline Rules (7 bullets, advisory)                                  │
│                                                                          │
│  Output: one file, unconditionally persisted                             │
│                                                                          │
│  Registry update: symbols / top-level keys IF source or config         │
│    (requirements and scripts NOT recorded)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    POST-GENERATION (deterministic)                       │
├─────────────────────────────────────────────────────────────────────────┤
│  _finalize_readme() — lists files + PaperModel themes                  │
│  No import audit, no config diff, no framework check, no rerender        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Signal strength by stage

| Signal | Strength at script generation | Strength at requirements generation |
|--------|------------------------------|-------------------------------------|
| `framework` in shared context | Low (informational JSON field) | Low (must predict future imports) |
| Repository contract roles | Medium (prose obligations) | Low (no import inventory) |
| Interface registry | Medium for symbol names | **None** (empty) |
| Task step description | High for local intent | Medium (env task ≠ all imports) |
| Prior file contents | **Not injected** — only path list | **Not injected** |

**Critical observation:** `repository_context` lists *that* `src/dataset.py` exists, not *what it contains*. Downstream files cannot see upstream implementations — only registry summaries. If registry extraction misses a signal (imports, nested keys), downstream prompts are blind.

---

## 4. Constraint Propagation Analysis

### 4.1 Requirements ↔ imports

| Expected propagation | Actual propagation |
|---------------------|-------------------|
| All `import X` in generated `.py` → `requirements.txt` | None — requirements generated first; scripts never feed back |
| Framework → primary package (`Caffe` → `caffe`, `PyTorch` → `torch`) | Framework in JSON only; no package mapping in contract |
| Transitive role needs (Dataset Provider using `torch.utils.data`) | LLM must infer from role prose |

**Verdict:** Import closure is **not propagated**; it is **hoped for** at the earliest generation step when evidence does not exist.

### 4.2 Framework ↔ all Python files

| Expected | Actual |
|----------|--------|
| Single framework across `src/`, `scripts/` | Per-file independent choice |
| README matches code | README from PaperModel; code from LLM |
| Evaluate script same stack as train | No cross-script framework edge in contract |

**Verdict:** Framework propagates to README and JSON context only. **No lateral constraint** between scripts.

### 4.3 Config producer ↔ config consumer

| Expected | Actual |
|----------|--------|
| `train.yaml` keys match `train.py` access paths | Top-level keys in registry; nested access unregulated |
| `dataset.yaml` shape matches what dataset module reads | Separate generation calls; no shared schema object |
| Object passed `train.py` → `create_data_loaders()` matches provider expectation | **No contract edge** for cross-module config handoff |

**Verdict:** Registry propagates **identifier names**, not **data shape**. Config consistency relies on LLM memory across calls.

### 4.4 TaskModel ↔ repository layout

| Expected | Actual |
|----------|--------|
| Each engineering step → corresponding artifact | Router may return `[]` or duplicate paths |
| Model implementation steps → `src/model.py` | Requires `model` + `implement*` keywords in step text |
| Multi-dataset papers → extensible layout | Fixed `src/dataset.py` singleton per dataset step |

**Verdict:** TaskModel intentions **decay at TaskRouter**. Coder contract is derived from routing table, not TaskModel directly.

### 4.5 Repository contract completeness

The contract contains sufficient information to **describe a textbook example** of a reproduction repo. It lacks information to **mechanically enforce** one:

| Present | Absent |
|---------|--------|
| Role names (Dataset Provider, Model Builder) | Framework binding per role |
| Consumer lists | Import manifests |
| `must_expose` semantic fields (batch size, optimizer) | Concrete key paths or schema templates |
| `style_expectation` prose | Validation rules |
| `must_succeed_without_extra_cli_args` | CLI argument registry |
| Relationship edges (file A → file B) | Payload contracts on edges |

Fix #3 intentionally removed canonical API names to preserve paper generality. The tradeoff is that **all cross-file binding pressure moves to registry + LLM obedience**, which is insufficiently reliable.

---

## 5. Weak Enforcement Points

Ordered by impact on arbitrary-paper repository quality:

### WEP-01 — No post-generation validation gate (Coder exit)

**Location:** End of `_populate_repository()`  
**Issue:** Files persist regardless of cross-file checks.  
**Symptom class:** Any inconsistency that deterministic rules could detect.

### WEP-02 — Requirements-first ordering without reconciliation

**Location:** `_CATEGORY_ORDER["dependencies"] = 0`  
**Issue:** Dependency file finalized before import evidence exists; no second pass.  
**Symptom class:** Missing packages (`torch`, `caffe`, framework-specific libs).

### WEP-03 — Registry does not capture imports

**Location:** `_record_interface_registry()` — source/config only  
**Issue:** Third-party packages used in scripts and modules are invisible to requirements and cross-file framework checks.  
**Symptom class:** Missing deps; undetected framework mixing.

### WEP-04 — Framework not in contract obligations

**Location:** `_build_repository_contract()`, all `prompts/coder/*.md`  
**Issue:** `PaperModel.framework` is theme, not rule.  
**Symptom class:** PyTorch train + Caffe eval; README vs code divergence.

### WEP-05 — Config registry is top-level only

**Location:** `_extract_yaml_top_level_keys()`  
**Issue:** Nested schema mismatches evade registry; script rule references top-level keys only.  
**Symptom class:** `cfg['dataset']['name']` vs `dataset: cifar10`.

### WEP-06 — No cross-module config handoff contract

**Location:** `relationships` in contract — file-to-file only  
**Issue:** Dataset Provider consumer may receive wrong config object type/shape.  
**Symptom class:** `create_data_loaders(full_train_cfg)` vs flat `dataset.yaml` schema.

### WEP-07 — Prompt language is advisory

**Location:** `prompts/coder/*.md`, `_format_generation_request` Rules  
**Issue:** “Follow,” “Fulfill,” “If you are a script…” — no MUST/NEVER with rejection semantics.  
**Symptom class:** LLM Output variance across sequential calls.

### WEP-08 — Full contract JSON on every call

**Location:** `_format_generation_request()` lines 497–498  
**Issue:** Injects entire contract plus slice — redundancy without added enforcement; may dilute focus.  
**Symptom class:** Low-priority; primarily prompt noise.

### WEP-09 — TaskRouter keyword lossiness

**Location:** `routing/task_router.py`  
**Issue:** Model/dataset/train/eval classification drops or duplicates tasks.  
**Symptom class:** Missing `src/model.py`; overwritten files; plan vs layout gap.

### WEP-10 — Duplicate path regeneration (last-write-wins)

**Location:** `_populate_repository()` loop over all targets without deduplication  
**Issue:** Second dataset or training step overwrites first with different `task_step` prompt.  
**Symptom class:** Wrong dataset scope; wrong training configuration baked in.

### WEP-11 — Script generation order within category

**Location:** `_sort_targets()` — alphabetical by path  
**Issue:** `evaluate.py` generates before `train.py`; no requirement that entrypoints share framework.  
**Symptom class:** Evaluate script diverges from training stack.

### WEP-12 — Repository context is path-only

**Location:** `_format_repository_context(populated_paths)`  
**Issue:** Downstream prompts do not see upstream file bodies — only registry summaries.  
**Symptom class:** Provider/consumer semantic drift when registry is incomplete.

### WEP-13 — Test/mock path gives false confidence

**Location:** `CoderMockLLMProvider`, population tests  
**Issue:** Mock always produces registry-aligned, torch-inclusive artifacts.  
**Symptom class:** CI green while acceptance fails on real LLM.

---

## 6. Recommended Improvement Directions

*Directions only — no implementation in this milestone.*

### DIR-01 — Close the dependency loop (import closure)

Introduce a deterministic **import inventory** after all Python files are generated (or regenerate `requirements.txt` last). Extract third-party imports from `src/` and `scripts/` via AST or regex; merge with framework-primary package mapping. This addresses WEP-01, WEP-02, WEP-03 without reintroducing global canonical API names.

### DIR-02 — Elevate framework to a binding contract field

Add `framework_binding` to repository contract: all routed Python targets must use the same framework stack; map framework → expected primary packages. Category prompts should state MUST/NEVER, not Follow. README should reflect **chosen implementation framework** (from contract enforcement), not raw PaperModel if they diverge — or generation should fail if they cannot align.

### DIR-03 — Deepen config registry beyond top-level keys

Record nested key paths consumed and produced (e.g. `training.max_iter`, `optimizer.lr`). Alternatively, designate a **single configuration authority** per consumption boundary to reduce multi-YAML composition errors. Propagate recorded paths to script prompts as the only legal access patterns.

### DIR-04 — Add cross-module payload edges

Extend contract relationships with **payload shape** obligations on edges where scripts call providers (e.g. `train.py → create_data_loaders`: parameter must be subset of keys from `configs/dataset.yaml` or documented merge rules). This preserves paper generality while making handoffs machine-checkable.

### DIR-05 — Deterministic generation validation inside Coder

Before `Coder.run()` returns, run lightweight checks: import ⊆ requirements; registry import symbols exist; top-level/nested config keys referenced in scripts appear in registry; framework imports consistent. Fail or trigger single targeted regeneration — still within Coder scope per prior fix patterns.

### DIR-06 — Repair TaskRouter fidelity

Deduplicate routing targets by `relative_path` (merge task contexts or pick canonical step). Broaden model-step classification (e.g. `resnet`, `architecture`, `network`, `block`). Emit routing coverage report into shared context so Coder knows which TaskModel steps have no artifact.

### DIR-07 — Reorder or split dependency generation

Options: (a) generate `requirements.txt` last; (b) two-phase population — skeleton imports first, reconcile after scripts; (c) dependencies category generates only `framework` pins, final merge pass adds discovered imports. Any option resolves the temporal paradox without extra LLM calls if merge is deterministic.

### DIR-08 — Strengthen prompt constraint tiering

Separate **hard constraints** (MUST import only registry symbols; MUST NOT import packages absent from requirements; MUST use `shared_context.framework`) from **soft guidance** (docstrings, comments, optional structure). Hard constraints should appear in both category templates and inline Rules.

### DIR-09 — Record script commitments in registry

After script generation, extract imports and config key access patterns into registry so a final requirements pass or validation step can use them. Scripts currently write but do not publish machine-readable commitments.

### DIR-10 — Acceptance-aligned integration tests

Add at least one real-LLM or high-fidelity fixture test asserting import closure and framework consistency — not merely prompt substring presence. Mock tests should include a “registry-empty requirements” scenario that expects failure or reconciliation.

---

## 7. Priority Ranking

Impact × generality for arbitrary papers (P1 = highest):

| Priority | Direction | Addresses | Rationale |
|----------|-----------|-----------|-----------|
| **P1** | DIR-01 Import closure / requirements reconciliation | WEP-01, WEP-02, WEP-03 | Blocks all execution at `pip install` or first import; structurally guaranteed by current ordering |
| **P1** | DIR-07 Reorder dependency generation | WEP-02 | Same root cause; lowest-risk fix to temporal paradox |
| **P2** | DIR-02 Framework binding | WEP-04, framework symptoms | Affects every paper where historical ≠ modern default stack |
| **P2** | DIR-05 Deterministic validation gate | WEP-01 | Converts soft coordination into enforced coordination without prescribing API names |
| **P2** | DIR-06 TaskRouter fidelity | WEP-09, WEP-10, task-layout gap | Upstream loss happens before contract is built |
| **P3** | DIR-03 Deep config registry | WEP-05, WEP-06 | Becomes blocking after imports succeed |
| **P3** | DIR-04 Cross-module payload edges | WEP-06 | Needed for multi-config papers |
| **P3** | DIR-08 Hard vs soft prompt constraints | WEP-07 | Reduces LLM variance; complements deterministic checks |
| **P4** | DIR-09 Script registry recording | WEP-03, WEP-12 | Enables DIR-01/05 without full file content in prompts |
| **P4** | DIR-10 Acceptance-aligned tests | WEP-13 | Prevents regression of coordination outcomes |
| **P5** | DIR-11 Script ordering policy | WEP-11 | Secondary to framework binding and import closure |

---

## Appendix A — Specific Analysis Questions (Summary)

### 1. Why can `requirements.txt` omit imported packages?

Because it is generated **first** with an **empty registry**, no import extraction from later files, and no reconciliation pass. Contract responsibility is **future-looking**; available data is **backward-looking** (empty).

### 2. Why is `PaperModel.framework` not consistently respected?

Framework is injected as shared context JSON but is **not a contract obligation** and **not stated as MUST** in category prompts. Each file’s LLM call may independently choose a modern implementation stack.

### 3. Why do configuration producers and consumers still disagree?

Registry records **top-level keys only**; configs are generated in **isolated calls**; no **payload contract** on module boundaries; scripts are told to match registry but **nothing validates** nested access or wrong config file passed to providers.

### 4. Why are TaskModel intentions sometimes not reflected in layout?

`TaskRouter` keyword heuristics **drop** unmatched steps and **duplicate** paths with last-write-wins. Contract and shared context derive from **routing table**, not raw TaskModel.

### 5. Does the Repository Contract contain enough information?

Enough to **coordinate human/LLM understanding** of roles. Not enough to **enforce** imports, framework, nested schemas, or config handoffs. Intentional generality tradeoff from Fix #3 leaves binding to LLM obedience.

### 6. Do prompts express hard constraints or suggestions?

**Suggestions.** Wording: “Follow,” “Fulfill,” “Include,” “If you are…” Inline Rules are advisory with no enforcement hook. Category templates do not use MUST/NEVER tiers.

### 7. Does generation ordering still allow downstream inconsistency?

**Yes.** Requirements-first creates import closure gap. Alphabetical script order generates `evaluate.py` before `train.py`. Duplicate targets overwrite without merge. Registry updates only for source/config — scripts do not publish imports back. Ordering solves **symbol visibility** (partially) but not **dependency, framework, or schema closure**.

---

## Appendix B — Relationship to Prior Fixes

| Fix | What it solved | What remains outside scope |
|-----|----------------|----------------------------|
| Fix #2 | Shared themes; generation order; README finalization | No import closure; framework non-binding; path-only context |
| Fix #3 | Symbol/key naming propagation; role-based contract | No semantic/schema enforcement; requirements timing; router fidelity |

Fix #4 should target **enforcement and closure** without reverting Fix #3’s paper-generality principle (no global canonical API catalog). The improvement space is **stronger propagation of machine-checkable commitments** and **deterministic reconciliation**, not another layer of prose in prompts alone.

---

## Evidence References

| Artifact | Path |
|----------|------|
| Coder generation loop | `agents/coder.py` |
| Task routing heuristics | `routing/task_router.py` |
| Coder category prompts | `prompts/coder/*.md` |
| M8.1 acceptance symptoms | `docs/reviews/M8.1/acceptance_report.md` |
| Fix #3 design tradeoffs | `docs/reviews/integration_fix_03/design_review.md` |
| Population / contract tests | `tests/test_coder_population.py`, `tests/test_coder_contract.py` |
