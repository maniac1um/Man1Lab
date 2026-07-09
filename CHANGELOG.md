# Changelog

All notable changes to Man1Lab are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.4] - 2026-07-09

**Console UX & Workspace Persistence** — guided console workflow, pipeline commands, runtime-owned artifact persistence, and resume utilities.

### Added

- **Guided console output** — success messages, generated artifacts, and next-step hints after `analyze`, `discover`, and `plan`
- **Pipeline commands** — `plan-all`, reserved `execute-all` and `reproduce`
- **Workspace artifact persistence** — runtime-owned `WorkspaceArtifactStore` under `analysis/`, `discovery/`, `planning/`, `decision/`
- **Resume utilities** — `hydrate_workspace_from_disk`, deterministic diagnostics for missing artifacts
- **Console enhancements** — ASCII startup banner, optional `prompt_toolkit` input (history, completion) with fallback
- **Decision Quality Phase 1** — Discovery selection stage; Planning consumes selections end-to-end
- **Decision Quality Phase 2** — `ResearchAsset`, explainable confidence, `DecisionTrace`, `ExecutionGraph` artifacts
- **Golden Benchmark framework** — regression suite for decision trace and execution graph
- **LLM reliability** — connection timeouts, structured exception chains for provider failures
- Release notes: [docs/releases/v1.2.4.md](docs/releases/v1.2.4.md)

### Changed

- Interactive console help documents the full analyze → discover → plan workflow
- `PLATFORM_VERSION` → 1.2.4

### Compatibility

- No breaking changes to facade APIs, CLI subcommands, or canonical artifacts
- Console remains presentation-only; business logic unchanged

### Tests

- 826 unit tests passing

[1.2.4]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.2.4

## [1.2.3] - 2026-07-08

**Platform Runtime & Interactive Console** — process-level infrastructure, runtime resource ownership, and REPL-style interface.

### Added

- **Platform Runtime** — `PlatformRuntime` lifecycle, `RuntimeContext`, lazy initialization, resource manager (phases 8.1–8.5)
- **Runtime profiling** — `RuntimeProfiler`, `man1lab profile` startup observation
- **Runtime integration** — `RuntimeInfrastructure`; configuration, prompts, and LLM platform resolved through runtime resources (8.5.1)
- **Interactive Console** — `man1lab` with no arguments enters `Man1LabConsole` (8.6)
- **Canonical architecture** — [docs/architecture/RUNTIME.md](docs/architecture/RUNTIME.md)
- Release notes: [docs/releases/v1.2.3.md](docs/releases/v1.2.3.md)

### Changed

- Agents require injected `PromptBuilder`; facade resolves infrastructure via runtime
- `LLMManager` created only through runtime-owned resources

### Compatibility

- No breaking changes to canonical artifacts or reproduction workflow semantics
- Existing CLI subcommands unchanged; console is additive (`man1lab` with no args)

### Tests

- 765 unit tests passing

[1.2.3]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.2.3

## [1.2.2] - 2026-07-08

**LLM Platform & First-run Experience** — model registry, multi-provider support, model management CLI, interactive initialization, and release hardening.

### Added

- **LLM Provider foundation** — `LLMManager`, `ModelRegistry`, `ProviderRegistry` ([reviews/7.1](docs/reviews/7.1_llm_provider_foundation/))
- **Model Registry** — named profiles, active profile resolution, validation, persistence to `conf/llm/user_profiles.yaml`
- **Anthropic provider** — `claude-sonnet-4` and compatible models
- **Model Management CLI** — `man1lab model list|current|use|add|remove|rename|test|validate`
- **First-run Experience** — interactive `man1lab init` wizard for first model setup; `man1lab model export|import`
- **Doctor LLM checks** — profile count, active profile, API key, connection health, validation
- Release notes: [docs/releases/v1.2.2.md](docs/releases/v1.2.2.md)

### Changed

- `man1lab doctor` includes LLM configuration section
- `man1lab init` optionally configures first model profile (skip with `--skip-model-config`)
- Documentation synchronized for v1.2.2; `docs/reviews/` directories normalized to `x.x_feature_name` format

### Compatibility

- No breaking changes to workflow, canonical artifacts, or existing CLI commands
- Skipping init wizard produces identical behavior to v1.2.1

### Tests

- 614 unit tests passing

[1.2.2]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.2.2

## [1.2.1] - 2026-07-08

**Execution Planning Stabilization** — six embedded providers with Decision Foundation; documentation and architecture cleanup.

### Added

- Decision Foundation package (`providers/embedded/decision_foundation/`)
- [ADR-0018](docs/adr/ADR-0018-Execution-Planning-Decision-Foundation.md)
- Release notes: [docs/releases/v1.2.1.md](docs/releases/v1.2.1.md)

### Tests

- 526 unit tests passing

[1.2.1]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.2.1

## [1.2.0] - 2026-07-03

**Platform Capability Release** — unified installable platform with public CLI and Python SDK; Discovery and Execution Planning integrated into the workflow.

### Added

- **Platform Facade** — `Man1Lab` as single composition root for all interfaces
- **CLI** — `man1lab` Typer application (`init`, `doctor`, `reproduce`, `analyze`, `discover`, `plan`, `execute`, `config`, `version`)
- **Python SDK** — `pip install man1lab` · `from man1lab import Man1Lab`
- **Package distribution** — PEP 621 `pyproject.toml`, console script, `python -m man1lab`
- **Lifecycle commands** — `man1lab init`, `man1lab doctor`
- **Research Resource Discovery** — `DiscoveryWorkflow` → `ResearchResourceDiscovery` ([ADR-0013](docs/adr/ADR-0013-Research-Resource-Discovery.md))
- **GitHub Discovery Provider** — collection, evidence, verification, ranking ([ADR-0016](docs/adr/ADR-0016-GitHub-Discovery-Provider.md))
- **Execution Planning** — `ExecutionPlanningWorkflow` → `ExecutionStrategy` ([ADR-0014](docs/adr/ADR-0014-Execution-Planning-Capability.md))
- **Strategy-driven Planner** — `TaskModel` from `ExecutionStrategy`
- Release notes: [docs/releases/v1.2.0.md](docs/releases/v1.2.0.md)
- Roadmap: [ROADMAP.md](ROADMAP.md)

### Changed

- **Recommended entry point** — `man1lab reproduce` or Python SDK; `app.py` retained for maintainers only
- Planner consumes `ExecutionStrategy` when execution planning is enabled (default)

### Migration

- Replace `PYTHONPATH=. python app.py` with `man1lab reproduce paper.pdf` or SDK `client.reproduce(...)`
- Hydra flags `discovery.enabled` and `execution_planning.enabled` default to enabled; set `false` for transitional legacy paths

### Tests

- 419 unit tests passing

[1.2.0]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.2.0

## [1.1.0] - 2026-06-30

**Foundation Release** — platform infrastructure complete. Not a feature-expansion release.

### Added

- **Analysis pipeline refactor** — `PaperReproductionAnalysis` replaces `PaperModel` as canonical domain object ([ADR-0009](docs/adr/ADR-0009-Analysis-Canonical-Artifact.md))
- **Docling parsing** — default document parser via ports & adapters ([ADR-0008](docs/adr/ADR-0008-Document-Parsing-Docling.md))
- **Hydra configuration** — composed settings behind `SettingsProvider` ([ADR-0010](docs/adr/ADR-0010-Hydra-Configuration.md))
- **Pixi environment** — lockfile-driven developer environment ([ADR-0011](docs/adr/ADR-0011-Pixi-Environment.md))
- **MLflow experiment tracking** — thin tracking via `ExperimentTracker` port ([ADR-0012](docs/adr/ADR-0012-Experiment-Tracking-MLflow.md))
- **Documentation governance** — public `docs/` for decisions; local `private/` for research process
- **Infrastructure governance** — [infrastructure.md](docs/architecture/infrastructure.md) adoption matrix
- Release notes: [docs/releases/v1.1.0.md](docs/releases/v1.1.0.md)

### Changed

- Public project identity rebranded from ResearchAgent to **Man1Lab**; GitHub repository URL updated to `github.com/maniac1um/Man1Lab`
- `WorkflowHistory.paper` removed; use `WorkflowHistory.analysis`
- Work documents (reviews, audits, benchmarks, roadmaps) migrated to local `private/` (gitignored)

### Breaking

- `Reader.run()` returns `PaperReproductionAnalysis` (supersedes ADR-0002 return type for analysis pipeline)
- `PaperModel` removed from runtime pipeline

### Tests

- 172 unit tests passing

[1.1.0]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.1.0

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
- GitHub release notes (`release/v1.0.0.md`)

### Known limitations (v1.0.0)

- Review loop does not re-invoke Coder or Runner when `PatchPlan.requires_patch` is true
- Full training reproduction not validated on benchmark papers (ResNet, DeiT)
- RAG blocks delivery defects but not runtime API breakage (e.g. timm private imports)
- LLM API timeouts can fail Reviewer independently of code quality
- Research prototype — pull requests not accepted; see [CONTRIBUTING.md](CONTRIBUTING.md)

[1.0.0]: https://github.com/maniac1um/Man1Lab/releases/tag/v1.0.0
