# Current Status

**Project:** Man1Lab  
**Single source of truth for implementation and integration state.**  
**Last updated:** 2026-07-13

| Field | Value |
|-------|-------|
| **Current Version** | **v1.2.4** |
| **License** | MIT ([LICENSE](../../LICENSE)) |
| **Milestone** | **Platform Capability** |
| **Previous Release** | v1.2.3 (Platform Runtime & Interactive Console) |
| **Next Milestone** | **Execution Runtime Integration (v1.3)** |

Release notes: [releases/v1.2.4.md](releases/v1.2.4.md) · Previous: [releases/v1.2.3.md](releases/v1.2.3.md) · Roadmap: [ROADMAP.md](../ROADMAP.md)

For install and run: [GETTING_STARTED.md](GETTING_STARTED.md). Architecture: [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md).

---

## Platform Interfaces (v1.2)

All public entry points route through the **Platform Facade** (`application/facade.py` → `Man1Lab`):

```text
CLI (man1lab)  ·  Interactive Console  ·  Python SDK  ·  Future MCP  ·  Future REST
                              ↓
                    Man1Lab (Platform Facade)
                              ↓
                    PlatformRuntime
                              ↓
                 TrackedWorkflowOrchestrator
```

| Interface | Location | Status |
|-----------|----------|--------|
| **CLI** | `interfaces/cli/` | ✅ Typer — `man1lab init\|doctor\|clean\|model\|reproduce\|profile\|…` |
| **Interactive Console** | `runtime/console/` | ✅ `man1lab` (no args) — guided REPL, pipeline commands, workspace persistence |
| **Python SDK** | `man1lab/` + `interfaces/sdk/` | ✅ `from man1lab import Man1Lab` |
| **Package** | `pyproject.toml` | ✅ `pip install man1lab` (v1.2.4) |
| **Lifecycle** | `application/lifecycle/` | ✅ `init` (+ first-model wizard), `doctor` (+ LLM checks), `clean` |
| **LLM Providers** | `providers/llm/` | ✅ `LLMManager`, `ModelRegistry`, `ProviderRegistry`, OpenAI, DeepSeek, Anthropic |
| **Model CLI** | `interfaces/cli/commands/model.py` | ✅ `man1lab model list\|current\|use\|add\|remove\|rename\|test\|validate\|export\|import` |
| MCP | `interfaces/mcp/` | Reserved |
| REST | `interfaces/api/` | Reserved |

Legacy maintainer entry: `app.py` / `pixi run run` — **not** the recommended user path.

---

## Canonical Artifact Pipeline

### Implemented

```text
Paper (PDF)
    ↓
PaperReproductionAnalysis       ← Analysis
    ↓
ResearchResourceDiscovery       ← Discovery
    ↓
ExecutionStrategy               ← Execution Planning
    ↓
TaskModel                       ← Planner
    ↓
Workspace                       ← Coder
    ↓
ExecutionResult                 ← Runner
    ↓
ReportModel                     ← Reporter
```

### Planned (roadmap only)

| Artifact | Milestone |
|----------|-----------|
| `RepositoryKnowledge` | v1.3 Repository Understanding |

---

## Current Pipeline

```text
Research Paper (PDF)
    ↓
Reader (Analysis)
    ↓
DiscoveryWorkflow
    ↓
ExecutionPlanningWorkflow
    ↓
Planner → Coder → Runner → Verification → Reviewer → Reporter
```

---

## Capability Status

| Capability | Status | Artifact |
|------------|--------|----------|
| Reader / Analysis | ✅ | `PaperReproductionAnalysis` |
| Discovery | ✅ | `ResearchResourceDiscovery` — collection, evidence, verification, ranking, **selection** |
| GitHub Discovery Provider | ✅ | Collection · Evidence · Verification · Ranking (selection consumes ranking) |
| Execution Planning | ✅ Complete | `ExecutionStrategy` — six embedded providers + Decision Foundation |
| LLM Platform | ✅ Complete | `ModelRegistry`, `ProviderRegistry`, OpenAI / DeepSeek / Anthropic |
| Model Management CLI | ✅ Complete | Profile lifecycle, export/import, doctor validation |
| First-run Experience | ✅ Complete | Interactive `man1lab init` wizard |
| Planner (strategy-driven) | ✅ | `TaskModel` |
| Coder | ✅ | `Workspace` |
| Runner | ✅ | `ExecutionResult` |
| Verification | ✅ | `VerificationResult` |
| Reviewer | ✅ | `ReviewReport` |
| PatchPlanner | ✅ | `PatchPlan` |
| Reporter | ✅ | `ReportModel` |
| Experiment Tracking | ✅ | MLflow (optional noop) |
| Platform Runtime | ✅ | Lifecycle, resources, profiling, session |
| Execution Engine Foundation | 🚧 Foundation complete | Canonical models, decomposition, sequential scheduler, state machine, trace, artifact tracking, report, memory-level resume |
| Runtime Execution Persistence | ✅ Phase 1–2 + audit | Journal replay, revision-tagged snapshots, O_EXCL locks, typed runtime wiring |

### Execution Engine maturity (v1.3 foundation)

| Component | Status |
|-----------|--------|
| `ExecutionRun`, `ExecutionTask`, `ExecutionResult`, `ExecutionTrace`, `ExecutionReport` | ✅ |
| Graph validation and task decomposition | ✅ |
| Sequential scheduler and state transitions | ✅ |
| Artifact model/tracker port | ✅ |
| Memory-level resume and reconciliation contracts | ✅ |
| Runtime-owned `ExecutionStore` | ✅ Phase 1–2 |
| Cross-process crash recovery | ✅ Phase 1–2 (file store; LocalExecutor E2E deferred) |
| Real `LocalExecutor` | ❌ |
| Facade/console execution integration | ❌ |

### Execution Planning maturity (v1.2.1+)

**Execution Planning complete** — six embedded engineering decision providers with shared Decision Foundation.

| Component | Status |
|-----------|--------|
| `ExecutionStrategy` canonical model | ✅ |
| Validation layer | ✅ |
| Runtime stage models | ✅ |
| `ExecutionStrategyBuilder` | ✅ |
| `ExecutionPlanningWorkflow` | ✅ |
| Service layer (6 services) | ✅ |
| Provider ports (6 ports) | ✅ |
| Embedded providers (6 stages) | ✅ |
| Decision Foundation | ✅ |
| NoOp providers | ✅ |

Internal layering: Workflow → Services → Providers → Decision Foundation → Builder → `ExecutionStrategy`.

See [architecture/EXECUTION_PLANNING.md](architecture/EXECUTION_PLANNING.md), [ADR-0017](adr/ADR-0017-Execution-Planning-Service-Architecture.md), [ADR-0018](adr/ADR-0018-Execution-Planning-Decision-Foundation.md).

**Decision Quality Phase 1 (2026-07-09):** Discovery selection stage implemented; Planning consumes selections end-to-end; Golden Benchmark regression suite added. See [reviews/decision_quality_improvement_phase_1/audit.md](reviews/decision_quality_improvement_phase_1/audit.md).

**Decision Quality Phase 2 (2026-07-09):** Unified Research Asset model, explainable confidence composition, `DecisionTrace` and `ExecutionGraph` runtime artifacts, extended Golden Benchmarks. See [reviews/decision_quality_improvement_phase_2/audit.md](reviews/decision_quality_improvement_phase_2/audit.md).

### LLM Platform maturity (v1.2.2)

| Component | Status |
|-----------|--------|
| `LLMProvider` foundation | ✅ |
| `ModelRegistry` + persistence | ✅ |
| `ProviderRegistry` | ✅ |
| OpenAI / DeepSeek / Anthropic providers | ✅ |
| `man1lab model` CLI | ✅ |
| Interactive init wizard | ✅ |
| Model export/import (portable, no secrets) | ✅ |
| Doctor LLM validation | ✅ |

Architecture: CLI → Facade → `LLMManager` → `ModelRegistry` → `ProviderRegistry` → `LLMProvider`.

Phase audits: [reviews/7.1_llm_provider_foundation/](reviews/7.1_llm_provider_foundation/) through [reviews/7.5_first_run_experience/](reviews/7.5_first_run_experience/).

### Platform Runtime maturity (v1.2.4)

**Console UX and workspace persistence** — guided workflow, pipeline commands, runtime-owned artifact storage.

| Component | Status |
|-----------|--------|
| `PlatformRuntime` lifecycle | ✅ |
| `RuntimeContext` + `RuntimeResourceManager` | ✅ |
| Lazy initialization | ✅ |
| Runtime profiling (`man1lab profile`) | ✅ |
| `RuntimeSession` + `SessionWorkspace` | ✅ |
| Runtime infrastructure integration (8.5.1) | ✅ |
| Interactive Console (`man1lab` no args) | ✅ |
| Guided console output + pipeline commands | ✅ |
| `WorkspaceArtifactStore` persistence | ✅ |
| Resume utilities (load + diagnostics) | ✅ |

Architecture: Interfaces → Facade → `PlatformRuntime` → Business workflows. See [architecture/RUNTIME.md](architecture/RUNTIME.md).

Phase audits: [reviews/8.1_runtime_performance_audit/](reviews/8.1_runtime_performance_audit/) through [reviews/8.6.1_console_user_experience/](reviews/8.6.1_console_user_experience/), [reviews/8.5.1_runtime_integration/](reviews/8.5.1_runtime_integration/).

---

## Foundation Infrastructure (v1.1)

| Capability | Tool | Status | ADR |
|------------|------|--------|-----|
| Paper Parsing | Docling (+ PyMuPDF) | Adopted | [ADR-0008](adr/ADR-0008-Document-Parsing-Docling.md) |
| Configuration | Hydra | Adopted | [ADR-0010](adr/ADR-0010-Hydra-Configuration.md) |
| Environment | Pixi | Adopted | [ADR-0011](adr/ADR-0011-Pixi-Environment.md) |
| Experiment Tracking | MLflow | Adopted | [ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md) |
| GitHub Discovery | GitHub REST | Adopted | [ADR-0016](adr/ADR-0016-GitHub-Discovery-Provider.md) |

---

## Tests

| Metric | Value |
|--------|-------|
| **Unit tests** | **109 Execution Engine + persistence tests passing** (verified 2026-07-13); full `tests/` suite requires project dependencies |
| Runtime | `tests/test_runtime_*.py`, `tests/test_man1lab_console.py` |
| Platform facade | `tests/test_platform_facade.py` |
| CLI | `tests/test_cli.py` |
| SDK | `tests/test_sdk.py` |
| Model CLI / init wizard | `tests/test_model_cli.py`, `tests/test_init_wizard.py` |
| Package | `tests/test_package_distribution.py` |
| Platform integration | `tests/test_platform_integration.py` |
| Discovery / GitHub / Execution Planning | Dedicated test modules |
| Execution persistence | `tests/test_execution_store.py`, `tests/test_execution_runtime_integration.py` |
Execution Engine + persistence (109 tests):

```bash
python -m pytest tests/test_execution_engine_models.py tests/test_execution_graph_validation.py tests/test_execution_decomposition.py tests/test_execution_scheduler.py tests/test_execution_resume.py tests/test_execution_ports.py tests/test_execution_audit_remediation.py tests/test_execution_second_audit_remediation.py tests/test_execution_store.py tests/test_execution_runtime_integration.py -q
```

The 109-test verification was also executed with the equivalent `unittest` module list in the available audit runtime. The broader `test_execution*.py` discovery reached 166 tests but 9 Execution Planning modules could not be collected because that audit runtime does not include `fitz`; this is an environment limitation, not recorded as a passing full-suite result.

Regression subset:

```bash
python -m pytest tests/test_execution_store.py tests/test_execution_runtime_integration.py -q
```

Full suite (`python -m pytest tests/`) requires project dependencies (`python-dotenv`, `PyMuPDF`/fitz, etc.); collection fails in minimal environments without them.

---

## Known Limitations

| ID | Limitation | Severity |
|----|------------|----------|
| L-01 | Review loop does not re-run Coder/Runner on patch | By design (v1.3+ ) |
| L-02 | Full training reproduction not validated on benchmark papers | Product |
| L-03 | RAG does not catch runtime API breakage | Coder/Runner boundary |
| L-04 | LLM API errors can fail Reviewer independently of code quality | External |
| L-05 | Discovery verification is shallow — not guaranteed runnable | Discovery |
| L-06 | MCP / REST interfaces not implemented | Roadmap |
| L-07 | `execution_planning.enabled=false` uses legacy Planner path | Transitional |
| L-08 | SDK does not expose model management methods | Optional polish |
| L-09 | Console `execute-all` / `reproduce` await execution engine | Runtime |
| L-10 | Real-backend artifact materialization/restore deferred until LocalExecutor | Phase 3 |
| L-11 | Execution runs, attempts, and trace durably persisted | Resolved (v1.3 Phase 1–2) |
| L-12 | Interrupted `RUNNING` tasks reconciled across processes | Resolved (v1.3 Phase 2; LocalExecutor E2E deferred) |

Full benchmark history: [benchmark section in prior releases](releases/v1.1.0.md).

---

## Next Milestone — Execution Runtime Integration (v1.3)

| Capability | Direction |
|------------|-----------|
| **ExecutionStore** | ✅ Phase 1–2 complete |
| **Runtime injection** | ✅ Phase 1–2 complete |
| **Crash resume** | ✅ Phase 1–2 (file store + engine; E2E with LocalExecutor deferred) |
| **First backend** | Durable LocalExecutor followed by facade/console integration |

See [architecture/EXECUTION_RUNTIME.md](architecture/EXECUTION_RUNTIME.md) and [ROADMAP.md](ROADMAP.md).

---

## Documentation Map

| Need | Document |
|------|----------|
| Install and run | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Architecture | [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md), [architecture/RUNTIME.md](architecture/RUNTIME.md) |
| Execution Runtime architecture | [architecture/EXECUTION_RUNTIME.md](architecture/EXECUTION_RUNTIME.md) |
| Execution Runtime roadmap | [ROADMAP.md](ROADMAP.md) |
| Product roadmap | [ROADMAP.md](../ROADMAP.md) |
| Release notes | [releases/v1.2.4.md](releases/v1.2.4.md) |
| ADRs | [adr/README.md](adr/README.md) |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) |

---

## Related ADRs

| Topic | ADR |
|-------|-----|
| Analysis canonical artifact | [ADR-0009](adr/ADR-0009-Analysis-Canonical-Artifact.md) |
| Research Resource Discovery | [ADR-0013](adr/ADR-0013-Research-Resource-Discovery.md) |
| Execution Planning | [ADR-0014](adr/ADR-0014-Execution-Planning-Capability.md), [ADR-0017](adr/ADR-0017-Execution-Planning-Service-Architecture.md), [ADR-0018](adr/ADR-0018-Execution-Planning-Decision-Foundation.md) |
| GitHub Discovery Provider | [ADR-0016](adr/ADR-0016-GitHub-Discovery-Provider.md) |
| Experiment tracking | [ADR-0012](adr/ADR-0012-Experiment-Tracking-MLflow.md) |
| Workflow orchestration | [ADR-0001](adr/ADR-0001-Workflow-Orchestrator.md) |

Phase audits: [reviews/](reviews/) (implementation audit reports).
