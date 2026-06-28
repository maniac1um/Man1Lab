# Current Status

**Single source of truth for implementation and integration state.**  
**Last updated:** 2026-06-28  
**Project version:** MVP v0.1  
**Development phase:** Post-capability-freeze integration hardening (product fixes)

For how to run the project, see [GETTING_STARTED.md](GETTING_STARTED.md). For architecture detail, see [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md).

---

## Implemented Capabilities

| Capability | Status | Output artifact |
|------------|--------|-----------------|
| Reader | Implemented | `PaperModel` |
| Planner | Implemented | `TaskModel` |
| Coder | Implemented | `Workspace` |
| Runner | Implemented | `ExecutionResult` |
| Verification | Implemented | `VerificationResult` (orchestrator service, not a separate agent stage) |
| Reviewer | Implemented | `ReviewReport` |
| PatchPlanner | Implemented | `PatchPlan` |
| Reporter | Implemented | `ReportModel` |

Reader, Planner, Coder, and Runner public interfaces are frozen since [M5.F](reviews/M5.F/design_review.md). See [DEVELOPMENT.md](../DEVELOPMENT.md) for freeze policy.

---

## Current Pipeline

```text
Research Paper (PDF)
        ↓
Reader → PaperModel
        ↓
Planner → TaskModel
        ↓
Coder → Workspace
        ↓
Runner → ExecutionResult
        ↓
VerificationService → VerificationResult
        ↓
Reviewer → ReviewReport
        ↓
PatchPlanner → PatchPlan
        ↓
Reporter → ReportModel
```

The review loop does not re-run Coder or Runner when `PatchPlan.requires_patch` is true (deferred to a later integration milestone).

---

## Latest Integration Result

| Field | Value |
|-------|-------|
| **Run** | 2026-06-28, `scripts/run_integration_m7_1.py` |
| **Paper** | ResNet (`1512.03385v1.pdf`) |
| **Duration** | 731 s |
| **Pipeline stages** | All SUCCESS (no uncaught exceptions) |
| **Final status** | **FAILED** |
| **Verdict** | Integration Fix #2 **Partially Fixed** — see [validation report](reviews/integration_fix_02/validation_report.md) |

**What improved since Integration Fix #1:**

- Environment preparation succeeded (`pip install` on Python 3.13)
- `scripts/train.py` was invoked
- Generated repository uses a consistent PyTorch stack and installable `requirements.txt`

**Current blocker:**

- `train.py` fails at import: `ImportError: cannot import name 'get_dataset' from 'src.dataset'`

Evidence: [integration_fix_02 validation report](reviews/integration_fix_02/validation_report.md), `outputs/report.md`, `outputs/integration_m7_1_snapshot.json`

---

## Known Active Issues

| Issue | Severity | Reference |
|-------|----------|-----------|
| Cross-module import mismatch (`get_dataset` vs actual `dataset.py` exports) | Critical | [fix_02 validation §DEFECT-01](reviews/integration_fix_02/validation_report.md) |
| `evaluate.py` imports undefined `get_cifar10_test_loader` | High | [fix_02 validation §DEFECT-02](reviews/integration_fix_02/validation_report.md) |
| Config schema mismatch between `train.yaml` and `train.py` | High | [fix_02 validation §DEFECT-03](reviews/integration_fix_02/validation_report.md) |
| Runner invokes `train.py` without required `--model` argument | High | [fix_02 validation §DEFECT-04](reviews/integration_fix_02/validation_report.md) |
| Canonical architecture docs stale (Reviewer marked planned) | Documentation | [governance audit](reviews/documentation_governance_phase1/documentation_audit.md) |

---

## Tests

| Metric | Value |
|--------|-------|
| **Unit tests** | 101 passing (`pytest tests/`) |
| **Integration runner** | `scripts/run_integration_m7_1.py` (manual, requires API key for real LLM) |

---

## Next Engineering Objective

Resolve **cross-module symbol alignment** between generated scripts and `src/` modules so the Runner entrypoint can execute `scripts/train.py` without `ImportError`. This is the highest-impact unresolved blocker from [Integration Fix #2 validation](reviews/integration_fix_02/validation_report.md).

---

## Related Reviews

| Topic | Document |
|-------|----------|
| Capability freeze baseline | [M5.F design review](reviews/M5.F/design_review.md) |
| Verification | [M6.1 design review](reviews/M6.1/design_review.md) |
| LLM review | [M6.2 design review](reviews/M6.2/design_review.md) |
| Patch planning | [M6.3 design review](reviews/M6.3/design_review.md) |
| First integration run (mock LLM) | [M7.1 integration report](reviews/M7.1/integration_report.md) |
| Integration Fix #1 analysis | [failure_analysis.md](reviews/integration_fix_01/failure_analysis.md) |
| Integration Fix #2 | [design](reviews/integration_fix_02/design_review.md) · [validation](reviews/integration_fix_02/validation_report.md) |
