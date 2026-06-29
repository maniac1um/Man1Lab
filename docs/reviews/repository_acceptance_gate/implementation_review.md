# Repository Acceptance Gate — Implementation Review

**Milestone:** RAG (Repository Acceptance Gate)  
**Type:** Coder internal delivery-quality gate  
**Prerequisite:** [GQ-1 implementation review](../generation_quality_upgrade_v1/implementation_review.md), [M8.2 cross-paper report](../M8.2/cross_paper_acceptance_report.md)

---

## 1. Design Summary

The Repository Acceptance Gate is the **final step inside `Coder.run()`**, after repository generation and deterministic validation. It reuses `validate_generated_repository()` from `agents/coder_quality.py` and adds `decide_repository_acceptance()` to classify findings into **blocking errors** vs **warnings**.

```text
Repository Generation (LLM population + requirements reconciliation)
        ↓
Deterministic Repository Validation (existing validate_generated_repository)
        ↓
Repository Acceptance Decision (decide_repository_acceptance)
        ↓
ACCEPT → finalize README → return Workspace
REJECT → raise RepositoryAcceptanceError (Runner never invoked)
```

**Not introduced:** new Agent, workflow stage, LLM call, orchestrator change, or public API change.

**Artifacts written on every run:**

| Log | Path |
|-----|------|
| Validation findings | `logs/generation_validation.log` |
| Acceptance decision | `logs/repository_acceptance.log` |

---

## 2. Acceptance Criteria

A generated repository is **accepted** when `decide_repository_acceptance()` returns zero blocking errors. Warnings do not prevent acceptance.

A repository is **rejected** when any blocking error is present. `Coder.run()` raises `RepositoryAcceptanceError` with structured `blocking_errors` (category, code, message). The orchestrator propagates this exception; **Runner does not execute**.

---

## 3. Blocking Error Rules

| Category | Validation codes | Rule |
|----------|------------------|------|
| **import_closure_failure** | `import_not_in_requirements` | Every third-party import in generated `.py` files must appear in `requirements.txt` |
| **framework_binding_failure** | `forbidden_framework_import`, `framework_mixing`, `framework_binding_violation` | No forbidden framework roots; no mixed frameworks; required framework roots must appear when PaperModel binds a known framework |
| **broken_internal_import** | `import_not_in_registry` | Scripts must import only symbols recorded in the interface registry for upstream `src/` modules |
| **missing_training_entrypoint** | `missing_training_entrypoint` | `scripts/train.py` must exist, be non-empty (Runner always executes this path) |

### Non-blocking (warnings only)

| Code | Examples |
|------|----------|
| `missing_routed_file` | Routed non-entrypoint file absent (except `scripts/train.py`) |
| `config_key_not_in_registry` | Config schema drift |
| `missing_script_entrypoint_guard` | Missing `if __name__ == "__main__"` |

README, documentation, and symbol-naming preferences remain warnings.

---

## 4. Unit Tests

**File:** `tests/test_coder_acceptance.py`

| Test | Verifies |
|------|----------|
| `test_accepted_repository_returns_workspace` | Mock pipeline with env + dataset + training → `ACCEPTED` log |
| `test_rejected_repository_raises_error` | Model-only task → `RepositoryAcceptanceError` (`missing_training_entrypoint`) |
| `test_warning_only_repository_is_accepted` | Config key warning without blocking codes → accepted |
| `test_blocking_error_classification_import_closure` | Category mapping |
| `test_blocking_error_classification_framework_binding` | Category mapping |
| `test_blocking_error_classification_broken_internal_import` | Category mapping |

**Updated tests:** `tests/test_coder_population.py`, `tests/test_task_routing.py` for rejection/acceptance expectations.

**Suite result:** `126 passed`

---

## 5. Benchmark Comparison (DeiT / `2012.12877v2.pdf`)

| Metric | M8.2 Run 3 (pre-RAG) | RAG Run (2026-06-29) |
|--------|----------------------|----------------------|
| Coder stage | SUCCESS | SUCCESS (~229s) |
| Acceptance gate | N/A (not implemented) | **ACCEPTED** |
| `requirements.txt` | Stub comment only | `PyYAML`, `timm`, `torch`, `torchvision`, `tqdm` |
| Runner invoked | Yes | Yes |
| Execution error | `No module named 'yaml'` (0.03s) | `ImportError: _pil_interp` from timm (5.78s) |
| Failure class | Import closure (undeclared deps) | **Runtime / paper-specific** (timm private API) |

### Expected RAG behavior on M8.2 defective repo

If the M8.2 repository (stub `requirements.txt`, undeclared imports) were generated today:

- `generation_validation.log` would list `import_not_in_requirements` errors
- `repository_acceptance.log` would show **REJECTED**
- `Coder.run()` would raise `RepositoryAcceptanceError`
- **Runner would not execute**

### Observed RAG behavior on current DeiT run

The regenerated DeiT repository **passed** the acceptance gate (import closure satisfied after reconciliation, framework consistent, symbols aligned, train entrypoint present). Runner executed and failed at a **runtime timm API** issue — outside RAG scope.

This demonstrates the intended split:

- **Delivery defects** (missing deps, broken imports) → blocked at Coder
- **Runtime / environment / paper-specific issues** → may still fail at Runner

---

## 6. Architecture Impact

| Constraint | Status |
|------------|--------|
| No new Agent | ✓ |
| No new workflow stage | ✓ |
| No additional LLM calls | ✓ |
| No Orchestrator changes | ✓ |
| No public API changes | ✓ (`Coder.run()` signature unchanged) |
| Reuses existing validation | ✓ |

**Additional fixes bundled with RAG testing:**

| Fix | Location | Purpose |
|-----|----------|---------|
| Environment routing priority | `routing/task_router.py` | Step **name** environment keywords checked before evaluation text (fixes M8.2 ROUTER-01) |
| Always reconcile requirements | `agents/coder.py` | Reconcile when any `.py` generated, even if env step mis-routed |
| `__future__` stdlib filter | `agents/coder_quality.py` | Avoid false third-party package |

`RepositoryAcceptanceError` is defined in `agents/coder_quality.py` (Coder-internal).

---

## 7. Remaining Limitations

| ID | Limitation |
|----|------------|
| L-01 | Gate does not validate nested YAML schemas or config semantic completeness (by design — warnings only) |
| L-02 | Gate does not detect runtime API breakage (e.g. timm private imports) — Runner may still fail |
| L-03 | `import_not_in_registry` relies on regex extraction of `from src.X import` — complex import forms may evade detection |
| L-04 | Framework binding only applies profiles for PyTorch, TensorFlow, JAX, Caffe — unknown frameworks skip required-root enforcement |
| L-05 | Rejection leaves a partially generated workspace (useful for debugging but not auto-cleaned) |
| L-06 | Reviewer API timeouts remain an external failure mode unrelated to RAG |

---

## Evidence Index

| Artifact | Path |
|----------|------|
| Acceptance gate logic | `agents/coder_quality.py` (`decide_repository_acceptance`, `RepositoryAcceptanceError`) |
| Coder integration | `agents/coder.py` (`_validate_and_accept`) |
| DeiT RAG run log | `logs/integration_deit_rag.log` |
| Acceptance log (accepted) | `workspace/tasks/.../logs/repository_acceptance.log` |
| M8.2 baseline report | `docs/reviews/M8.2/cross_paper_acceptance_report.md` |
