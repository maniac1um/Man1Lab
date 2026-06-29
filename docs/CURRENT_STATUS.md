# Current Status

**Single source of truth for implementation and integration state.**  
**Last updated:** 2026-06-29  
**Project version:** v1.0.0 (MVP)  
**Development phase:** MVP complete — v1.0.0 release packaging

For how to run the project, see [GETTING_STARTED.md](GETTING_STARTED.md). For architecture detail, see [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md).

---

## Implemented Capabilities

| Capability | Status | Output artifact | Notes |
|------------|--------|-----------------|-------|
| Reader | Implemented | `PaperModel` | Public interface frozen since [M5.F](reviews/M5.F/design_review.md) |
| Planner | Implemented | `TaskModel` | Frozen since M5.F |
| Coder | Implemented | `Workspace` | Includes GQ-1 quality layer and Repository Acceptance Gate (RAG) |
| Runner | Implemented | `ExecutionResult` | Frozen since M5.F |
| Verification | Implemented | `VerificationResult` | `VerificationService` in orchestrator (not a separate agent stage) |
| Reviewer | Implemented | `ReviewReport` | LLM-based failure analysis; see [M6.2](reviews/M6.2/design_review.md) |
| PatchPlanner | Implemented | `PatchPlan` | Deterministic repair planning; see [M6.3](reviews/M6.3/design_review.md) |
| Reporter | Implemented | `ReportModel` | Final workflow report; persisted to `outputs/report.md` |

**Coder delivery quality (post-M5):**

| Layer | Module | Purpose |
|-------|--------|---------|
| GQ-1 | `agents/coder_quality.py` | Framework binding, import closure, requirements reconciliation, validation |
| RAG | `agents/coder_quality.py` | `decide_repository_acceptance()` — blocks Runner on delivery defects |

See [GQ-1 implementation review](reviews/generation_quality_upgrade_v1/implementation_review.md) and [RAG implementation review](reviews/repository_acceptance_gate/implementation_review.md).

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
        │   (generation validation + repository acceptance gate)
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

The review loop does **not** re-invoke Coder or Runner when `PatchPlan.requires_patch` is true. Iteration is deferred to a future milestone.

---

## Benchmark Status

End-to-end runs use `scripts/run_integration_m7_1.py` with a configured LLM API key.

| Run | Paper | Pipeline | RAG | Execution | Report |
|-----|-------|----------|-----|-----------|--------|
| [M8.1](reviews/M8.1/acceptance_report.md) | ResNet (`1512.03385v1.pdf`) | All stages SUCCESS | N/A | **FAILED** — `No module named 'torch'` | Complete |
| [M8.2](reviews/M8.2/cross_paper_acceptance_report.md) | DeiT (`2012.12877v2.pdf`) | All stages SUCCESS | N/A | **FAILED** — stub `requirements.txt` | Complete |
| [RAG](reviews/repository_acceptance_gate/implementation_review.md) | DeiT (re-run) | Reader–Coder SUCCESS | **ACCEPTED** | **FAILED** — timm `_pil_interp` (runtime) | Reviewer API error on some runs |

**Summary:** The MVP pipeline runs end-to-end on real papers with real LLM calls. Generated repositories pass the Repository Acceptance Gate on the DeiT benchmark. Full paper reproduction (successful training execution) is **not** yet achieved — remaining failures are runtime, paper-specific, or external API issues rather than undeclared dependencies or broken internal imports.

---

## Known Limitations

| ID | Limitation | Severity |
|----|------------|----------|
| L-01 | Review loop does not re-run Coder/Runner on patch | By design (deferred) |
| L-02 | Full training reproduction not validated on any benchmark paper | Product |
| L-03 | Framework binding covers PyTorch, TensorFlow, JAX, Caffe only | Coder |
| L-04 | RAG does not catch runtime API breakage (e.g. timm private imports) | Coder/Runner boundary |
| L-05 | LLM API timeouts/errors can fail Reviewer independently of code quality | External |
| L-06 | Caffe and other non-pip frameworks may produce installable but non-runnable envs | Paper-specific |
| L-07 | `outputs/integration_m7_1_snapshot.json` is overwritten each integration run | Tooling |

For RAG-specific limitations, see [RAG review §7](reviews/repository_acceptance_gate/implementation_review.md).

---

## Tests

| Metric | Value |
|--------|-------|
| **Unit tests** | 126 passing (`PYTHONPATH=. pytest tests/`) |
| **Integration runner** | `scripts/run_integration_m7_1.py` (manual, requires API key for real LLM) |

---

## Documentation Map

| Need | Document |
|------|----------|
| Install and run | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Architecture | [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Capability reference | [architecture/CAPABILITIES.md](architecture/CAPABILITIES.md) |
| Engineering workflow | [DEVELOPMENT.md](../DEVELOPMENT.md) |
| Release history | [CHANGELOG.md](../CHANGELOG.md) |
| GitHub release notes | [release/v1.0.0.md](../../release/v1.0.0.md) |
| Historical reviews | [reviews/README.md](reviews/README.md) |

---

## Related Reviews

| Topic | Document |
|-------|----------|
| Capability freeze baseline | [M5.F design review](reviews/M5.F/design_review.md) |
| Verification | [M6.1 design review](reviews/M6.1/design_review.md) |
| LLM review | [M6.2 design review](reviews/M6.2/design_review.md) |
| Patch planning | [M6.3 design review](reviews/M6.3/design_review.md) |
| MVP acceptance (ResNet) | [M8.1 acceptance report](reviews/M8.1/acceptance_report.md) |
| Cross-paper acceptance (DeiT) | [M8.2 cross-paper report](reviews/M8.2/cross_paper_acceptance_report.md) |
| Generation quality (GQ-1) | [GQ-1 implementation review](reviews/generation_quality_upgrade_v1/implementation_review.md) |
| Repository acceptance gate | [RAG implementation review](reviews/repository_acceptance_gate/implementation_review.md) |
| Release documentation governance | [release_preparation/documentation_review.md](reviews/release_preparation/documentation_review.md) |
| Release packaging | [release_packaging/release_review.md](reviews/release_packaging/release_review.md) |
