# Changelog

All notable changes to ResearchAgent MVP are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [1.0.0] - 2026-06-29

First public release. MVP implementation complete — autonomous single-paper reproduction pipeline with real LLM integration, repository generation, execution, verification, review, and reporting.

### Added

#### Pipeline capabilities

- **Reader** — PDF ingestion and structured `PaperModel` extraction via LLM
- **Planner** — Engineering task planning producing `TaskModel`
- **Coder** — Workspace construction, task routing, and per-file LLM generation
- **Runner** — Environment preparation and `scripts/train.py` execution
- **Verification** — `VerificationService` deterministic execution checks (`VerificationResult`)
- **Reviewer** — LLM-based failure analysis (`ReviewReport`)
- **Patch Planner** — Structured repair planning (`PatchPlan`)
- **Reporter** — Final workflow report (`ReportModel`)

#### Coder delivery quality

- **Generation Quality Upgrade (GQ-1)** — Framework binding, import closure, requirements reconciliation, generation validation log
- **Repository Acceptance Gate (RAG)** — Final Coder gate; blocks Runner on import closure, framework binding, broken internal imports, or missing `scripts/train.py`

#### Tooling and tests

- Integration runner: `scripts/run_integration_m7_1.py`
- 126 unit tests covering agents, routing, coder quality, and acceptance gate

#### Documentation governance

- Documentation index (`docs/README.md`), current status (`docs/CURRENT_STATUS.md`), getting started guide
- Architecture reference (`docs/architecture/`), capability summary, roadmap (M1–M8)
- ADRs ADR-0001 through ADR-0007
- Milestone and integration review archive (`docs/reviews/`)
- Release preparation audit (`docs/reviews/release_preparation/`)
- GitHub release notes (`release/v1.0.0.md`)

### Known limitations (v1.0.0)

- Review loop does not re-invoke Coder or Runner when `PatchPlan.requires_patch` is true
- Full training reproduction not validated on benchmark papers (ResNet, DeiT)
- RAG blocks delivery defects but not runtime API breakage (e.g. timm private imports)
- LLM API timeouts can fail Reviewer independently of code quality
- Research prototype — pull requests not accepted; see [CONTRIBUTING.md](CONTRIBUTING.md)

[1.0.0]: https://github.com/maniac1um/Research_Agent_MVP/releases/tag/v1.0.0
