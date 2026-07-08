# Current Status

**Project:** Man1Lab  
**Single source of truth for implementation and integration state.**  
**Last updated:** 2026-07-08

| Field | Value |
|-------|-------|
| **Current Version** | **v1.2.2** |
| **License** | MIT ([LICENSE](../../LICENSE)) |
| **Milestone** | **Platform Capability** |
| **Previous Release** | v1.2.1 (Execution Planning Stabilization) |
| **Next Milestone** | **Repository Understanding (v1.3)** |

Release notes: [releases/v1.2.2.md](releases/v1.2.2.md) · Previous: [v1.2.1](releases/v1.2.1.md) · Roadmap: [ROADMAP.md](../ROADMAP.md)

For install and run: [GETTING_STARTED.md](GETTING_STARTED.md). Architecture: [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md).

---

## Platform Interfaces (v1.2)

All public entry points route through the **Platform Facade** (`application/facade.py` → `Man1Lab`):

```text
CLI (man1lab)  ·  Python SDK (man1lab package)  ·  Future MCP  ·  Future REST
                              ↓
                    Man1Lab (Platform Facade)
                              ↓
                 TrackedWorkflowOrchestrator
```

| Interface | Location | Status |
|-----------|----------|--------|
| **CLI** | `interfaces/cli/` | ✅ Typer — `man1lab init\|doctor\|clean\|model\|reproduce\|…` |
| **Python SDK** | `man1lab/` + `interfaces/sdk/` | ✅ `from man1lab import Man1Lab` |
| **Package** | `pyproject.toml` | ✅ `pip install man1lab` (v1.2.2) |
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
| Discovery | ✅ | `ResearchResourceDiscovery` |
| GitHub Discovery Provider | ✅ | Collection · Evidence · Verification · Ranking |
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
| **Unit tests** | **614 passing** (`pixi run test`) |
| Platform facade | `tests/test_platform_facade.py` |
| CLI | `tests/test_cli.py` |
| SDK | `tests/test_sdk.py` |
| Model CLI / init wizard | `tests/test_model_cli.py`, `tests/test_init_wizard.py` |
| Package | `tests/test_package_distribution.py` |
| Platform integration | `tests/test_platform_integration.py` |
| Discovery / GitHub / Execution Planning | Dedicated test modules |
| Integration runner | `scripts/run_integration_m7_1.py` (manual, API key) |

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

Full benchmark history: [benchmark section in prior releases](releases/v1.1.0.md).

---

## Next Milestone — Repository Understanding (v1.3)

| Capability | Direction |
|------------|-----------|
| **Repository Understanding** | Semantic mapping of selected repo structure to analysis modules |
| **RepositoryKnowledge artifact** | New canonical object (design TBD) |
| **Downstream** | Informs Execution Planning refinements and Coder context |

See [ROADMAP.md](../ROADMAP.md).

---

## Documentation Map

| Need | Document |
|------|----------|
| Install and run | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Architecture | [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Roadmap | [ROADMAP.md](../ROADMAP.md) |
| Release notes | [releases/v1.2.2.md](releases/v1.2.2.md) |
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
