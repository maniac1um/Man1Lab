# ResearchAgent MVP

**Version:** v1.0.0  
**Status:** Research prototype — MVP implementation complete

ResearchAgent is an autonomous engineering pipeline for research paper reproduction. Given a PDF research paper, the system extracts structured information, plans engineering tasks, generates a reproduction repository, prepares a Python environment, executes the training script, verifies results, reviews failures, and produces a final report.

This release is intended for **academic demonstration**. It is not yet a community-driven open-source project. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Architecture Overview

A single `WorkflowOrchestrator` schedules isolated agents. Agents communicate only through typed artifacts (Pydantic models), never directly.

```text
Research Paper (PDF)
        ↓
Reader → PaperModel
        ↓
Planner → TaskModel
        ↓
Coder → Workspace
        │   (generation validation + Repository Acceptance Gate)
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

Full design: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)

---

## Current Capabilities

| Capability | Output | Status |
|------------|--------|--------|
| Reader | `PaperModel` | Implemented |
| Planner | `TaskModel` | Implemented |
| Coder | `Workspace` | Implemented (includes GQ-1 + RAG) |
| Runner | `ExecutionResult` | Implemented |
| Verification | `VerificationResult` | Implemented |
| Reviewer | `ReviewReport` | Implemented |
| Patch Planner | `PatchPlan` | Implemented |
| Reporter | `ReportModel` | Implemented |

Details: [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) · [docs/architecture/CAPABILITIES.md](docs/architecture/CAPABILITIES.md)

---

## Current Limitations

- The pipeline runs end-to-end on real papers but **does not guarantee successful training reproduction**
- The review loop does **not** re-invoke Coder or Runner when a patch is recommended
- The Repository Acceptance Gate blocks delivery defects but not runtime API breakage
- LLM API instability can fail Reviewer independently of code quality

Full list: [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md#known-limitations)

---

## Quick Start

### Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

### Install and test

```bash
git clone https://github.com/maniac1um/Research_Agent_MVP.git
cd Research_Agent_MVP
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/ -v
```

### Run on a paper

```bash
PYTHONPATH=. python app.py
```

Set `PAPER_PATH` to your PDF (default: `paper.pdf`).

### LLM configuration (optional)

Copy `.env.example` to `.env`:

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
```

Without `OPENAI_API_KEY`, mock providers return deterministic fixtures.

### Full integration run

```bash
PYTHONPATH=. python scripts/run_integration_m7_1.py
```

Requires an API key. Results: `outputs/` and `logs/`.

More detail: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## Benchmark Status

End-to-end runs on real papers with a configured LLM (see [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)):

| Run | Paper | Pipeline | RAG | Execution |
|-----|-------|----------|-----|-----------|
| M8.1 | ResNet | All stages SUCCESS | N/A | FAILED — missing `torch` in requirements |
| M8.2 | DeiT | All stages SUCCESS | N/A | FAILED — stub `requirements.txt` |
| RAG re-run | DeiT | Reader–Coder SUCCESS | **ACCEPTED** | FAILED — timm runtime API |

**Summary:** Delivery quality improved through GQ-1 and RAG; full training reproduction is not yet validated on benchmark papers.

Evidence: [docs/reviews/M8.1/](docs/reviews/M8.1/) · [docs/reviews/M8.2/](docs/reviews/M8.2/) · [RAG review](docs/reviews/repository_acceptance_gate/implementation_review.md)

---

## Documentation

| Document | Location |
|----------|----------|
| **Current status** | [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) |
| **Getting started** | [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Capabilities | [docs/architecture/CAPABILITIES.md](docs/architecture/CAPABILITIES.md) |
| Release notes | [release/v1.0.0.md](release/v1.0.0.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Development (maintainer) | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Reviews | [docs/reviews/README.md](docs/reviews/README.md) |
| ADRs | [docs/adr/README.md](docs/adr/README.md) |

---

## Repository Structure

```text
agents/          # Reader, Planner, Coder, Runner, Reviewer, Reporter
models/          # Pydantic domain models
workflow/        # WorkflowOrchestrator
services/        # PDF, environment, execution, verification
execution/       # ExecutionPlanner
planning/        # PatchPlanner
routing/         # TaskRouter
workspace/       # WorkspaceManager
prompt/          # Prompt loader and builder
prompts/         # Agent prompt resources
llm/             # LLM provider abstraction
tests/           # Unit tests (126 passing)
docs/            # Architecture, roadmap, ADRs, reviews
release/         # GitHub release notes
scripts/         # Integration runner
```

---

## Citation

If you use this prototype in academic work, please cite:

```bibtex
@software{researchagent_mvp_2026,
  author       = {maniac1um},
  title        = {ResearchAgent MVP: Autonomous Research Paper Reproduction Pipeline},
  year         = {2026},
  version      = {1.0.0},
  url          = {https://github.com/maniac1um/Research_Agent_MVP},
  note         = {Research prototype. v1.0.0 release.}
}
```

_Citation metadata is a placeholder for academic use. A formal publication reference may be added in a future release._

---

## Maintainer

**maniac1um** — sole author and maintainer of this repository.
