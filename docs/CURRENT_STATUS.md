# Current Status

**Project:** Man1Lab  
**Single source of truth for implementation and integration state.**  
**Last updated:** 2026-06-30

| Field | Value |
|-------|-------|
| **Current Version** | **v1.1.0** |
| **Milestone** | **Foundation Complete** |
| **Next Milestone** | **Platform Capability (v1.2)** |

For how to run the project, see [GETTING_STARTED.md](GETTING_STARTED.md). For architecture detail, see [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md). Release notes: [releases/v1.1.0.md](releases/v1.1.0.md).

---

## Foundation Status

v1.1.0 completes **Platform Foundation** — infrastructure adoption, analysis pipeline refactor, and documentation governance. This is not a feature-expansion release.

### Completed Infrastructure

| Capability | Tool | Status | ADR |
|------------|------|--------|-----|
| Paper Parsing | Docling (+ PyMuPDF fallback) | **Adopted** | [ADR-0008](adr/ADR-0008-Document-Parsing-Docling.md) |
| Configuration | Hydra | **Adopted** | [ADR-0010](adr/ADR-0010-Hydra-Configuration.md) |
| Environment | Pixi | **Adopted** | [ADR-0011](adr/ADR-0011-Pixi-Environment.md) |
| Experiment Tracking | MLflow | **Adopted** | [ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md) |
| Dataset Versioning | DVC | Pending | — |
| Workflow Engine | TBD | Research | — |

Full matrix: [architecture/infrastructure.md](architecture/infrastructure.md).

### Current Native Components

These remain Man1Lab-native — not replaced by infrastructure tools:

| Component | Agent / Module | Output |
|-----------|----------------|--------|
| **Analysis** | Reader | `PaperReproductionAnalysis` |
| **Planning** | Planner | `TaskModel` |
| **Coding** | Coder | `Workspace` |
| **Review** | Reviewer + PatchPlanner | `ReviewReport`, `PatchPlan` |
| **Report** | Reporter | `ReportModel` |

Orchestration: `WorkflowOrchestrator` (topology frozen, [ADR-0001](adr/ADR-0001-Workflow-Orchestrator.md)). Experiment tracking wraps at composition root via `TrackedWorkflowOrchestrator` ([ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md)).

---

## Next Milestone — Platform Capability (v1.2)

Foundation complete. Future work focuses on **platform capabilities**:

| Capability | Direction |
|------------|-----------|
| **Repository Discovery** | Consume `reproduction_gaps` + metadata |
| **Environment Generation** | Beyond workspace venv bootstrap |
| **Verification** | Deeper alignment with analysis evaluation module |
| **Failure Recovery** | Close review loop — re-invoke Coder/Runner |
| **DVC** | Dataset versioning (pending adoption review) |
| **Workflow Engine** | Research only — Man1Lab orchestrator remains native |

Working roadmap: `private/roadmap/` (local).

---

## Implemented Capabilities

| Capability | Status | Output artifact | Notes |
|------------|--------|-----------------|-------|
| Reader | Implemented | `PaperReproductionAnalysis` | [ADR-0002](adr/ADR-0002-Stable-Reader-Interface.md), [ADR-0009](adr/ADR-0009-Analysis-Canonical-Artifact.md) |
| Planner | Implemented | `TaskModel` | [ADR-0004](adr/ADR-0004-Planning-Strategy.md), [ADR-0005](adr/ADR-0005-Planner-Capability.md) |
| Coder | Implemented | `Workspace` | GQ-1 + Repository Acceptance Gate (RAG) |
| Runner | Implemented | `ExecutionResult` | [ADR-0007](adr/ADR-0007-Execution-Capability.md) |
| Verification | Implemented | `VerificationResult` | `VerificationService` in orchestrator |
| Reviewer | Implemented | `ReviewReport` | LLM-based failure analysis |
| PatchPlanner | Implemented | `PatchPlan` | Deterministic repair planning |
| Reporter | Implemented | `ReportModel` | Persisted to `outputs/report.md` |
| Experiment Tracking | Implemented | MLflow runs | Optional; disable via `TRACKING_BACKEND=noop` |

**Coder delivery quality (post-M5):**

| Layer | Module | Purpose |
|-------|--------|---------|
| GQ-1 | `agents/coder_quality.py` | Framework binding, import closure, requirements reconciliation, validation |
| RAG | `agents/coder_quality.py` | `decide_repository_acceptance()` — blocks Runner on delivery defects |

Detailed implementation reviews: `private/audit/quality/` (local).

---

## Current Pipeline

```text
Research Paper (PDF)
        ↓
Parsing → ParsedDocument
        ↓
Reader → PaperReproductionAnalysis
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
        ↓
Experiment Tracking → MLflow parent run + nested stage runs
```

The review loop does **not** re-invoke Coder or Runner when `PatchPlan.requires_patch` is true. Iteration is deferred to v1.2 (Failure Recovery).

---

## Benchmark Status

End-to-end runs use `scripts/run_integration_m7_1.py` with a configured LLM API key.

| Run | Paper | Pipeline | RAG | Execution | Report |
|-----|-------|----------|-----|-----------|--------|
| M8.1 | ResNet (`1512.03385v1.pdf`) | All stages SUCCESS | N/A | **FAILED** — `No module named 'torch'` | Complete |
| M8.2 | DeiT (`2012.12877v2.pdf`) | All stages SUCCESS | N/A | **FAILED** — stub `requirements.txt` | Complete |
| RAG re-run | DeiT | Reader–Coder SUCCESS | **ACCEPTED** | **FAILED** — timm `_pil_interp` (runtime) | Reviewer API error on some runs |

Full benchmark reports: `private/benchmark/` (local only).

**Summary:** The pipeline runs end-to-end on real papers with real LLM calls. Generated repositories pass the Repository Acceptance Gate on the DeiT benchmark. Full paper reproduction (successful training execution) is **not** yet achieved.

---

## Known Limitations

| ID | Limitation | Severity |
|----|------------|----------|
| L-01 | Review loop does not re-run Coder/Runner on patch | By design (v1.2) |
| L-02 | Full training reproduction not validated on any benchmark paper | Product |
| L-03 | Framework binding covers PyTorch, TensorFlow, JAX, Caffe only | Coder |
| L-04 | RAG does not catch runtime API breakage (e.g. timm private imports) | Coder/Runner boundary |
| L-05 | LLM API timeouts/errors can fail Reviewer independently of code quality | External |
| L-06 | Caffe and other non-pip frameworks may produce installable but non-runnable envs | Paper-specific |
| L-07 | `outputs/integration_m7_1_snapshot.json` is overwritten each integration run | Tooling |

---

## Tests

| Metric | Value |
|--------|-------|
| **Unit tests** | 172 passing (`pixi run test` or `PYTHONPATH=. pytest tests/`) |
| **Integration runner** | `scripts/run_integration_m7_1.py` (manual, requires API key for real LLM) |

---

## Documentation Map

| Need | Document |
|------|----------|
| Install and run | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Architecture | [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Infrastructure governance | [architecture/infrastructure.md](architecture/infrastructure.md) |
| Capability reference | [architecture/CAPABILITIES.md](architecture/CAPABILITIES.md) |
| Engineering workflow | [DEVELOPMENT.md](../DEVELOPMENT.md) |
| Release history | [CHANGELOG.md](../CHANGELOG.md) |
| Release notes | [releases/README.md](releases/README.md) · [releases/v1.1.0.md](releases/v1.1.0.md) |
| Architecture decisions | [adr/README.md](adr/README.md) |
| Private work documents | [CONTRIBUTING.md § Documentation Policy](../CONTRIBUTING.md#documentation-policy) — `private/` (local, gitignored) |

---

## Related ADRs (public decision record)

| Topic | ADR |
|-------|-----|
| Workflow orchestration | [ADR-0001](adr/ADR-0001-Workflow-Orchestrator.md) |
| Reader interface | [ADR-0002](adr/ADR-0002-Stable-Reader-Interface.md) |
| Analysis canonical artifact | [ADR-0009](adr/ADR-0009-Analysis-Canonical-Artifact.md) |
| Document parsing (Docling) | [ADR-0008](adr/ADR-0008-Document-Parsing-Docling.md) |
| Hydra configuration | [ADR-0010](adr/ADR-0010-Hydra-Configuration.md) |
| Pixi environment | [ADR-0011](adr/ADR-0011-Pixi-Environment.md) |
| Experiment tracking (MLflow) | [ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md) |
| Execution capability | [ADR-0007](adr/ADR-0007-Execution-Capability.md) |

Historical milestone reviews, audits, and benchmarks are in `private/` — see [reviews/README.md](reviews/README.md).
