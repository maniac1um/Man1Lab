# Implementation Review — Integration Fix #3 Cross-file Contract Consistency

**Fix:** integration_fix_03 — Cross-file Contract Consistency  
**Type:** Implementation review  
**Status:** Complete  
**Design:** [design_review.md](design_review.md) (revised, accepted)  
**Integration run:** Not performed (deferred to next milestone)

---

## 1. Files Modified

| File | Change |
|------|--------|
| `agents/coder.py` | Repository contract, interface registry, extraction helpers, prompt assembly, README deduplication |
| `prompts/coder/source.md` | Module role fulfillment |
| `prompts/coder/script.md` | Registry consumption, execution expectations |
| `prompts/coder/config.md` | Configuration role, top-level key layout |
| `prompts/coder/dependencies.md` | Registry-aware dependencies |
| `llm/coder_mock_provider.py` | Registry-aligned mock content; dynamic train/evaluate scripts |
| `tests/test_coder_contract.py` | **New** — contract derivation and extraction tests |
| `tests/test_coder_population.py` | Contract/registry prompt tests; recording delegate to mock provider |

### Unchanged

| Component | Status |
|-----------|--------|
| `Coder.run()` signature | Unchanged |
| `WorkflowOrchestrator` | Unchanged |
| `ExecutionPlanner` | Unchanged |
| `TaskRouter` | Unchanged |
| New workflow artifacts / agents / Pydantic models | None added |

---

## 2. Implementation Summary

Integration Fix #3 extends Fix #2 with two internal coordination structures inside `Coder.run()`:

1. **Repository Contract** — deterministic role-based dict from `TaskRoutingTable` + shared generation context. Describes module roles, configuration roles, execution expectations, relationships, and file responsibilities. No symbol names.

2. **Interface Registry** — in-memory dict updated after each generated `source` or `config` file. Records top-level Python `def`/`class` names and YAML top-level keys via lightweight regex/line parsing.

Every file-generation prompt now includes: shared context, full contract, contract slice for the target, current interface registry, repository path list, and role obedience rules.

Generation order, README finalization, and LLM call count per target are unchanged.

---

## 3. Registry Implementation

### Recording

After writing a `source` or `config` target, `Coder._record_interface_registry()` stores:

| File type | Recorded fields |
|-----------|-----------------|
| `source` | `public_symbols`, `symbol_kinds` (`function` / `class`) |
| `config` | `top_level_keys` |

### Extraction (lightweight)

| Method | Mechanism |
|--------|-----------|
| `_extract_python_symbols()` | Regex `^def name` and `^class name` at line start |
| `_extract_yaml_top_level_keys()` | Non-indented lines matching `key:` |

No AST module. No PyYAML parse in extraction.

### Example registry after dataset + config generation

```json
{
  "src/dataset.py": {
    "public_symbols": ["load_dataloaders"],
    "symbol_kinds": {"load_dataloaders": "function"}
  },
  "configs/train.yaml": {
    "top_level_keys": ["dataset", "batch_size", "learning_rate", ...]
  }
}
```

Subsequent `scripts/train.py` prompt includes this registry; mock provider generates imports from recorded symbols.

### README deduplication

`_finalize_readme()` uses `list(dict.fromkeys(populated_paths))` to avoid duplicate Generated Files entries (Fix #2 DEFECT-05).

---

## 4. Prompt Updates

### User prompt (`_format_generation_request`)

Added blocks:

- `Repository contract (interface roles)`
- `Interface registry (commitments from files already generated)`
- `Contract obligations for this target` (slice)
- Role obedience rules (no invented imports/keys; no required CLI args for train)

### Category prompts

Updated `source.md`, `script.md`, `config.md`, `dependencies.md` to reference contract and registry instead of only shared context.

### Target-specific slices (`_contract_slice_for_target`)

Selects relevant `module_role`, `configuration_role`, `execution_expectation`, `file_responsibility`, and `relationships` edges for the current target path.

---

## 5. Validation Results

### Unit tests

| Metric | Result |
|--------|--------|
| **Total tests** | 110 |
| **Passed** | 110 |
| **Failed** | 0 |
| **Duration** | ~0.84s |

### New / updated test coverage

| Test | Verifies |
|------|----------|
| `test_coder_contract.py` | Contract includes Dataset Provider; omits Model Builder when not routed; symbol/YAML extraction; registry recording; execution slice |
| `test_repository_contract_included_in_prompts` | Contract JSON in user prompt |
| `test_interface_registry_in_train_prompt_after_upstream_files` | Registry symbols/keys visible before train generation |
| `test_train_script_imports_registry_symbols` | Mock train.py imports `load_dataloaders`; reads config keys |

### Integration run

**Not executed** per milestone scope. Real-paper validation deferred to next milestone.

### Expected impact (design intent)

| Acceptance goal | Unit test proxy | Integration status |
|-----------------|-----------------|-------------------|
| Imports resolve | `test_train_script_imports_registry_symbols` | Pending E2E |
| Consistent config keys | Registry keys in train prompt | Pending E2E |
| Runner-compatible train.py | Mock train has no required CLI args | Pending E2E |
| Import stage passes | Not tested without integration run | Pending E2E |

---

## 6. Remaining Limitations

| Limitation | Notes |
|------------|-------|
| Prompt-enforced contract | LLM may still violate registry rules on real API runs |
| Regex extraction | Misses `__all__`, re-exports, indented-only definitions |
| Nested YAML | Only top-level keys recorded; nested structures not validated |
| Mock vs real LLM | Unit tests use `CoderMockLLMProvider`; real LLM compliance unverified |
| evaluate.py | Registry-aligned in mock; not executed by Runner in E2E |
| No integration run | Import-stage and training-start acceptance not yet observed on ResNet paper |

---

## 7. Architecture Check

| Constraint | Met |
|------------|-----|
| No new workflow artifacts | Yes — contract and registry are Coder-local |
| No new agents | Yes |
| No orchestration changes | Yes |
| No additional LLM calls | Yes — same one-call-per-target loop |
| No new public APIs | Yes — `Coder.run()` unchanged |
| No new Pydantic models | Yes |
| No validation pipeline | Yes |
| Generation order preserved | Yes — dependencies → source → config → script |
| README finalization preserved | Yes — with deduplication |
| Repository contract is coordination, not framework | Yes — role-based, no canonical API catalog |

---

## Related Documents

| Document | Relationship |
|----------|--------------|
| [design_review.md](design_review.md) | Approved design (revised) |
| [integration_fix_02/validation_report.md](../integration_fix_02/validation_report.md) | Baseline defects |
| [CURRENT_STATUS.md](../../CURRENT_STATUS.md) | Update after next integration run |
