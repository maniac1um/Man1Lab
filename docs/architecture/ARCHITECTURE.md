# Man1Lab Architecture

**Version:** v1.3 architecture baseline
**Status:** Living document — platform-level design  
**Audience:** Architects, contributors, and long-term maintainers  
**Horizon:** 3–5 years

This document describes **what Man1Lab is**, how its layers relate, and where responsibility boundaries lie. It is the highest-level architecture reference for the project.

For **specific decisions** (orchestrator ownership, parsing backend, canonical analysis artifact), see [Architecture Decision Records](../adr/README.md). ADRs record *why* a choice was made; this document records *what the system is*.

For **implementation status and benchmarks**, see [CURRENT_STATUS.md](../CURRENT_STATUS.md) and [CAPABILITIES.md](CAPABILITIES.md).

For **Platform Runtime** (process lifecycle, resources, session, console), see [RUNTIME.md](RUNTIME.md). For Runtime-owned execution persistence, see [EXECUTION_RUNTIME.md](EXECUTION_RUNTIME.md).

For **infrastructure governance** (Hydra, Pixi, adoption matrix), see [infrastructure.md](infrastructure.md).

---

## 1. Vision

### What Man1Lab Is

Man1Lab is an **AI-native research engineering platform** whose primary job is to turn a research paper into a **reproducible engineering outcome** — structured understanding, an executable plan, generated artifacts, runtime execution, and verified results.

The platform treats a paper as the **source of truth** for what should be reproduced, then applies AI at each engineering stage while keeping stages **independent, replaceable, and boundary-respecting**.

### What Man1Lab Is Not

| Misclassification | Why it does not fit |
|-------------------|---------------------|
| **AI coding agent** | Code generation is one layer among many. Man1Lab does not start from a chat prompt; it starts from a paper and a canonical analysis artifact that downstream stages share. |
| **Workflow engine** | Orchestration exists, but the product is not generic DAG execution. The workflow is domain-specific: paper → analysis → engineering → execution → verification. |
| **Auto research system** | Man1Lab does not invent research questions, run open-ended exploration, or close the scientific loop autonomously. It **reproduces and engineers** what a paper already claims. |

### Current Focus and Platform Trajectory

| Horizon | Focus |
|---------|--------|
| **v1.1.x** | **Foundation** — infrastructure adoption, canonical analysis artifact |
| **v1.2.x (now)** | **Platform Capability** — CLI, SDK, Discovery, Execution Planning, GitHub Provider |
| **v1.3 (current architecture milestone)** | Execution Engine Foundation → Runtime-owned persistence → Local execution integration |
| **v1.4+** | Repository Understanding → Adaptation → Knowledge Memory |

The architecture is intentionally **paper-first** and **analysis-first** so that future capabilities attach to stable layers rather than re-implementing paper understanding in every feature.

---

## 2. Core Design Philosophy

| Principle | Meaning |
|-----------|---------|
| **Paper-first** | The PDF and its stated content anchor every stage. External knowledge does not override what the paper says unless a dedicated future layer (e.g. repository discovery) explicitly adds it. |
| **Analysis-first** | Structured paper understanding is produced once and reused. Downstream stages consume analysis; they do not re-read the PDF for the same facts. |
| **Engineering-oriented** | Outputs are actionable for implementation and execution — not literature summaries or open-ended reasoning. |
| **Native AI workflow** | LLM-assisted extraction and generation live **inside** bounded stages, each with explicit inputs, outputs, and forbidden behaviors. |
| **Ports & adapters** | Swappable backends (e.g. document parsers) sit behind stable interfaces. Parsing technology can change without rewriting analysis or planning. |
| **Single domain object** | After analysis, the pipeline shares one canonical artifact — `PaperReproductionAnalysis` — avoiding duplicate understanding and divergent prompts. |
| **Module independence** | Each layer has a single responsibility. Stages do not call each other directly; a coordinator schedules them and passes typed artifacts. |
| **Long-term evolvability** | Layers, artifact versioning, and ADRs allow extension (new backends, new post-analysis stages) without collapsing boundaries. |

---

## 3. Layered Architecture

Man1Lab is organized as a **vertical pipeline** of layers. Each layer transforms or consumes **typed artifacts**. A workflow coordinator schedules stages; layers themselves do not embed scheduling logic.

```text
Paper (PDF)
    ↓
Parsing Layer
    ↓
Analysis Layer
    ↓
Discovery Layer
    ↓
Execution Planning Layer
    ↓
Execution Materialization Layer
    ↓
Planning Layer
    ↓
Implementation Layer
    ↓
Execution Layer
    ↓
Verification Layer
    ↓
Reporting Layer
```

Cross-cutting concerns — orchestration, prompt infrastructure, validation — support layers but are not substitutes for them.

---

### Platform Interface Layer

| | |
|--|--|
| **Responsibility** | Provide the **only public entry** to Man1Lab for all future interfaces |
| **Input** | User intent (paper path, partial operations, configuration) |
| **Output** | Typed platform artifacts (`ReportModel`, `PaperReproductionAnalysis`, etc.) |
| **Does** | Load configuration (Hydra), compose dependencies, initialize tracking, delegate to workflow |
| **Does NOT** | Implement analysis, discovery, planning, coding, or execution logic |

Future interfaces share this layer:

```text
CLI  ·  Interactive Console  ·  Python SDK  ·  (Future MCP)  ·  (Future REST)
                    ↓
          Man1Lab (Platform Facade)
                    ↓
          PlatformRuntime
                    ↓
       TrackedWorkflowOrchestrator
                    ↓
Parsing → Analysis → Discovery → Execution Planning
                    ↓
 Planner → Coder → Runner → Verification → Review → Report
```

Legacy maintainer entry: `scripts/legacy_app.py` — not a public interface.

**CLI (v1.2):** `interfaces/cli/` — Typer commands delegate exclusively to `Man1Lab`.

```text
man1lab init      → Man1Lab.init() + optional setup_first_model()
man1lab doctor    → Man1Lab.doctor() (environment + LLM checks)
man1lab clean     → Man1Lab.clean()
man1lab reproduce → Man1Lab.reproduce()
man1lab analyze   → Man1Lab.analyze()
man1lab discover  → Man1Lab.discover()
man1lab plan      → Man1Lab.plan_from_paper()
man1lab execute   → Man1Lab.execute_from_paths()
man1lab config    → Man1Lab.configuration()
man1lab model     → Man1Lab.list_models() / use_model() / export_models() / import_models() / …
man1lab profile   → Man1Lab.profile_startup()
man1lab           → Interactive Console (no args)
man1lab version   → Man1Lab.version()
```

**Package distribution (v1.2):** `pip install man1lab`, console script `man1lab`, module entry `python -m man1lab`. Public exports: `Man1Lab`, `PLATFORM_VERSION`, `__version__`.

Future: `interfaces/mcp/`, `interfaces/api/` (reserved, not implemented).

**Python SDK (v1.2):** `interfaces/sdk/` + `man1lab/` package — `from man1lab import Man1Lab`.

Public API (`application.facade.Man1Lab`):

| Method | Operation |
|--------|-----------|
| `reproduce()` | Full workflow |
| `analyze()` | Analysis only |
| `discover()` | Discovery only |
| `plan()` | Execution planning only |
| `execute()` | Implementation + runtime from existing strategy |
| `doctor()` | Environment validation |
| `version()` | Platform version |
| `configuration()` | Effective runtime settings |

Interfaces must **never** call `WorkflowOrchestrator` directly.

---

### Platform Runtime Layer

| | |
|--|--|
| **Responsibility** | Own process lifecycle, infrastructure resources, lazy initialization, profiling, and user session lifetime |
| **Input** | Startup/shutdown signals from facade; resource factory registration from application wiring |
| **Output** | Ready runtime context; resolved infrastructure (configuration, prompts, LLM platform); session scope |
| **Does** | Lifecycle FSM, resource manager, startup profiling, interactive console substrate |
| **Does NOT** | Interpret papers, run Discovery, commit strategies, generate code, or execute training |

```text
PlatformRuntime
    ├── RuntimeContext → RuntimeResourceManager → lazy infrastructure
    │                    └── ExecutionStore (v1.3 Phase 1–2 ✅)
    ├── RuntimeSession → SessionWorkspace (references + disk hydration)
    │     └── WorkspaceArtifactStore → analysis/, discovery/, planning/, decision/
    └── RuntimeProfiler (per observation run)
```

Business workflows run **below** Runtime. Agents receive injected dependencies resolved through `RuntimeInfrastructure` — they do not import runtime internals.

Full specification: [RUNTIME.md](RUNTIME.md).

Execution persistence is a Runtime-owned infrastructure concern, while execution transitions and scheduling remain Execution Engine concerns. Application composition injects the Runtime-provided store through a narrow Execution port. See [EXECUTION_RUNTIME.md](EXECUTION_RUNTIME.md).

---

### LLM Provider Layer

Business capabilities must not call vendor SDKs directly. Inference flows through a single manager, model registry, and provider registry.

```text
Business Logic (Reader, Planner, Coder, Reviewer, PatchPlanner)
        ↓
LLMManager
        ↓
ModelRegistry
        ↓
ProviderRegistry
        ↓
LLMProvider (infrastructure contract)
        ↓
OpenAIProvider / DeepSeekProvider / AnthropicProvider / (future providers)
```

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **LLMManager** | `providers/llm/manager.py` | Resolve active profile, delegate `generate()` / `stream()` / `health_check()` |
| **ModelRegistry** | `providers/llm/registry.py` | Profile lifecycle — load, validate, activate, register, rename, remove |
| **ModelProfile** | `providers/llm/models.py` | Canonical configured model descriptor (no runtime state) |
| **ProviderRegistry** | `providers/llm/provider_registry.py` | Register provider adapters, resolve by provider name |
| **LLMProvider** | `providers/llm/base.py` | Infrastructure contract — no provider-specific logic outside adapters |
| **OpenAIProvider** | `providers/llm/openai_provider.py` | OpenAI chat-completions adapter |
| **AnthropicProvider** | `providers/llm/anthropic_provider.py` | Anthropic Messages API adapter (non-OpenAI-compatible SDK) |
| **Legacy port** | `llm/provider.py` | Business `complete()` port; bridged by `llm/compat.py` during migration |

**Implemented providers:** OpenAI, DeepSeek, Anthropic.

**Reserved for future phases:** Gemini, OpenRouter, Ollama, Azure OpenAI.

Configuration uses `LLMConfig.active` and `LLMConfig.profiles` in `resources/conf/llm/default.yaml`. Legacy flat `OPENAI_*` fields remain supported and are auto-migrated into a `default` profile when profiles are absent.

---

### Parsing Layer

| | |
|--|--|
| **Responsibility** | Convert a paper file into a structured document representation suitable for analysis |
| **Input** | Paper PDF |
| **Output** | `ParsedDocument` (primary field today: structured markdown; reserved fields for richer structure) |
| **Does** | Layout-aware extraction, reading order, tables and headings where supported |
| **Does NOT** | Understand the paper, extract reproduction facts, plan tasks, search the web, or execute code |

Default backend: **Docling**. Legacy fallback: **PyMuPDF**. Backend selection is a parsing concern only — see [ADR-0008](../adr/ADR-0008-Document-Parsing-Docling.md).

---

### Analysis Layer

| | |
|--|--|
| **Responsibility** | Extract **paper-stated** reproduction information and record **reproduction gaps** (what the paper omits) |
| **Input** | `ParsedDocument` |
| **Output** | `PaperReproductionAnalysis` — the platform's **canonical domain object** |
| **Does** | Populate goal, resources, method, evaluation, and gaps from paper text; assign reproduction scope when the paper states it |
| **Does NOT** | Search for repositories, order engineering tasks, generate code, create environments, run experiments, or infer facts not grounded in the paper |

Analysis answers: *What does the paper say is needed to reproduce its claims, and what does it fail to state?*

It is **not** a task plan, specification for code generation, or execution result.

---

### Discovery Layer

| | |
|--|--|
| **Responsibility** | Collect, verify, and rank external resources that may satisfy reproduction needs |
| **Input** | `PaperReproductionAnalysis` (read-only) |
| **Output** | `ResearchResourceDiscovery` |
| **Does** | Candidate collection, evidence gathering, verification, ranking, **selection** |
| **Does NOT** | Choose engineering strategy, decompose tasks, generate code, or execute repositories |

See [ADR-0016](../adr/ADR-0016-GitHub-Discovery-Provider.md).

#### Internal capability layering

```text
DiscoveryWorkflow                  ← orchestration only
        ↓
Discovery Services                 ← provider orchestration (execute)
        ↓
Provider Ports
        ↓
Providers (GitHub, Embedded, NoOp)
        ↓
Selection (discovery/selection.py)   ← commits primary/fallback per resource need
        ↓
Research assets + explainable confidence (discovery/assets.py, discovery/confidence.py)
        ↓
ResearchResourceDiscoveryBuilder ← canonical assembly
        ↓
ResearchResourceDiscovery        ← only exported artifact
```

---

### Execution Planning Layer

| | |
|--|--|
| **Responsibility** | Commit engineering strategy before task decomposition |
| **Input** | `PaperReproductionAnalysis`, `ResearchResourceDiscovery` (both read-only) |
| **Output** | `ExecutionStrategy`, `DecisionTrace`, `ExecutionGraph` (runtime-persisted) |
| **Does** | Strategy decision, resource binding, reuse/adaptation/generation planning, risk assessment |
| **Does NOT** | Re-run discovery, decompose tasks, generate code, or execute repositories |

See [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) and [ADR-0017](../adr/ADR-0017-Execution-Planning-Service-Architecture.md).

#### Internal capability layering

```text
ExecutionPlanningWorkflow          ← orchestration only
        ↓
Execution Planning Services      ← provider orchestration (execute)
        ↓
Provider Ports
        ↓
Embedded Providers               ← runtime snapshots
        ↓
Decision Foundation              ← internal reasoning
        ↓
ExecutionStrategyBuilder         ← canonical assembly
        ↓
Validation
        ↓
ExecutionStrategy                ← only exported artifact
```

| Layer | Owns |
|-------|------|
| **Workflow** | Stage ordering, timestamps, provenance envelope, builder invocation |
| **Services** | Provider orchestration, ordering, per-stage merge |
| **Providers** | Runtime metadata and snapshot mapping from decisions |
| **Decision Foundation** | Observed facts, dimensions, per-stage engineering decisions |
| **Builder** | Canonical artifact assembly from runtime results |
| **Validation** | Structural correctness of `ExecutionStrategy` |

**Maturity:** Execution Planning complete (v1.2.1). Six embedded providers with shared Decision Foundation.

See [architecture/EXECUTION_PLANNING.md](EXECUTION_PLANNING.md), [ADR-0017](../adr/ADR-0017-Execution-Planning-Service-Architecture.md), [ADR-0018](../adr/ADR-0018-Execution-Planning-Decision-Foundation.md).

---

### Execution Materialization Layer

| | |
|--|--|
| **Responsibility** | Convert committed Planning decisions and abstract graph nodes into validated backend-ready instructions |
| **Input** | `ExecutionStrategy`, `ResearchResourceDiscovery`, abstract `ExecutionGraph`, application-provided workspace context |
| **Output** | `ExecutionMaterialization` containing a materialized `ExecutionGraph` and `MaterializationReport` |
| **Does** | Resolve deterministic paths/references, select versioned task templates, produce typed invocation specifications, validate readiness |
| **Does NOT** | Change strategy/topology, clone/download/install, execute commands, schedule tasks, or manage Runtime |

Only a `READY` materialization may create an `ExecutionRun`. Missing entrypoints or output contracts are reported as `BLOCKED`; they are never guessed from stage labels.

See [EXECUTION_MATERIALIZATION.md](EXECUTION_MATERIALIZATION.md).

---

### Planning Layer

| | |
|--|--|
| **Responsibility** | Transform committed strategy into an **ordered engineering task graph** |
| **Input** | `ExecutionStrategy` |
| **Output** | `TaskModel` — executable engineering steps with dependencies |
| **Does** | Decompose reproduction into concrete steps (environment, data, model, training, evaluation, etc.) |
| **Does NOT** | Choose repository, greenfield, adaptation, or reuse; re-read the PDF; write source code; execute scripts |

Planning answers: *In what order should engineering work happen given the committed strategy?*  
It does **not** infer engineering strategy — that belongs to Execution Planning.

See [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) and [ADR-0005](../adr/ADR-0005-Planner-Capability.md).

---

### Planning Layer (legacy note)

When `execution_planning.enabled=false`, the orchestrator uses a transitional `Planner.run_legacy(analysis)` path. Strategy decisions are not produced; this path exists for compatibility only.

---

### Implementation Layer

| | |
|--|--|
| **Responsibility** | Generate the reproduction **repository** — structure, source, configs, scripts, dependencies |
| **Input** | `PaperReproductionAnalysis`, `TaskModel`, optional repair plan from review |
| **Output** | `Workspace` — on-disk project plus workspace metadata |
| **Does** | Map tasks to files, generate implementation artifacts, validate repository coherence before execution |
| **Does NOT** | Execute training, install runtime environments beyond declaration, or reinterpret the paper independently of analysis |

Implementation **consumes** analysis modules (goal, resources, method, evaluation) as generation context; it does not replace analysis.

---

### Execution Layer

| | |
|--|--|
| **Responsibility** | Execute a validated task graph and durably record its lifecycle and outcomes |
| **Input** | `READY` materialized `ExecutionGraph` plus Runtime-provided execution services |
| **Output** | `ExecutionReport`, `ExecutionTrace`, task results, and registered artifacts |
| **Does** | Decompose, schedule, dispatch to an executor, persist state transitions, and collect outcomes |
| **Does NOT** | Invent commands or paths, generate or modify repository source, parse papers, or perform LLM-based analysis |

Execution is **runtime-only**. Repository artifacts and runtime artifacts have distinct ownership — see [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) and [ADR-0007](../adr/ADR-0007-Execution-Capability.md).

The v1.3 `Execution Engine Foundation` adds canonical run/task/result/trace/report models, decomposition, scheduling, state transitions, artifact tracking, reporting, and resume. Runtime provides durable persistence through `ExecutionStore`; `LocalExecutor` and Facade/Console integration are implemented. Planning-to-Execution Materialization remains the gate required to turn ordinary Planning graphs into runnable local instructions.

---

### Verification Layer

| | |
|--|--|
| **Responsibility** | Deterministically check whether execution outcomes meet expectations derived from analysis |
| **Input** | `Workspace`, `ExecutionResult`, and implicitly the **goal** and **evaluation** modules of analysis |
| **Output** | `VerificationResult` — structured pass/fail signals |
| **Does** | Inspect logs, exit codes, artifact presence, and other objective checks |
| **Does NOT** | Replace human judgment on scientific validity; LLM review is a separate review stage |

Verification provides **ground truth** for the review stage. It verifies against **stated** success criteria — not against novel inference.

A **review sub-loop** (review report → patch plan → optional re-implementation) sits after verification. In v1.x the loop is partially wired: patch planning exists; automatic re-coding is not yet enabled.

---

### Reporting Layer

| | |
|--|--|
| **Responsibility** | Consolidate workflow history into a final human-readable outcome |
| **Input** | Workflow history (analysis, tasks, workspace, execution, verification, reviews) |
| **Output** | `ReportModel` / persisted report |
| **Does** | Summarize reproduction attempt, implementation location, execution history, and final status |
| **Does NOT** | Change plans, regenerate code, or alter analysis |

Reporting is **descriptive**, not decision-making.

---

## 4. Canonical Domain Object

### One Object, Many Consumers

After Parsing, Man1Lab standardizes on a **single canonical domain object**:

**`PaperReproductionAnalysis`**

All agents and services downstream of Analysis consume this object (directly or through derived context views). There is no parallel “flat paper model” or permanent adapter projection in the runtime pipeline.

| Module | Question it answers |
|--------|---------------------|
| **metadata** | Which paper? |
| **goal** | What to reproduce? (includes reproduction scope) |
| **resources** | What to prepare? (datasets, models, dependencies, links, artifacts) |
| **method** | How to engineer it? (framework, architecture, procedure, hyperparameters) |
| **evaluation** | How to judge success? (metrics, benchmarks, protocol, baselines) |
| **reproduction_gaps** | What does the paper **not** provide? |

### Why a Single Object

| Benefit | Explanation |
|---------|-------------|
| **No duplicate understanding** | The paper is interpreted once at Analysis; Planner and Implementation read the same facts |
| **Consistent prompts** | Context builders derive views from one schema instead of ad hoc field subsets |
| **Clear boundaries** | Parsing output (`ParsedDocument`) and planning output (`TaskModel`) remain separate artifact types |
| **Future extensibility** | Discovery and future modules attach to analysis modules and gaps — not a second paper parse |

Schema versioning (`schema_version`) allows evolution without breaking the architectural rule: **one canonical analysis artifact per paper run**.

See [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md).

### Platform capability artifacts (v1.2+)

After Analysis, additional **canonical artifacts** carry platform capability outputs:

| Artifact | Layer | Input | Purpose |
|----------|-------|-------|---------|
| **`ResearchResourceDiscovery`** | Discovery | `PaperReproductionAnalysis` | Evidence-backed external resource resolution |
| **`ExecutionStrategy`** | Execution Planning | Analysis + Discovery | Committed engineering strategy before task decomposition |

Downstream planning consumes **`ExecutionStrategy`**, not raw discovery rankings.

### Roadmap artifacts (planned — not implemented)

| Artifact | Milestone | Notes |
|----------|-----------|-------|
| **`RepositoryKnowledge`** | v1.3 | Semantic repo structure mapping |

`ExecutionResult` and `ReportModel` are **implemented** runtime/report outputs at Execution and Reporting layers.

See [ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md), [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md), [ROADMAP.md](../../ROADMAP.md).

---

## 5. End-to-End Data Flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT: Research paper (PDF)                                          │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    ↓
                          ┌─────────────────┐
                          │ Parsing Layer   │
                          └────────┬────────┘
                                   ↓
                          ParsedDocument
                                   ↓
                          ┌─────────────────┐
                          │ Analysis Layer  │
                          └────────┬────────┘
                                   ↓
                    PaperReproductionAnalysis  ← canonical domain object
                                   ↓
                          ┌─────────────────┐
                          │ Discovery Layer │
                          └────────┬────────┘
                                   ↓
                    ResearchResourceDiscovery
                                   ↓
                    ┌──────────────────────────┐
                    │ Execution Planning Layer │
                    └────────┬─────────────────┘
                                   ↓
                 ExecutionStrategy + abstract ExecutionGraph
                                   ↓
                    ┌───────────────────────────┐
                    │ Execution Materialization │
                    └─────────────┬─────────────┘
                                   ↓
                 READY materialized ExecutionGraph
                                   ↓
                          ┌─────────────────┐
                          │ Execution Layer │
                          └────────┬────────┘
                                   ↓
                  ExecutionReport + ExecutionTrace
                                   ↓
                          ┌───────────────────┐
                          │ Verification Layer│
                          └────────┬──────────┘
                                   ↓
                          VerificationResult
                                   ↓
                    Review → PatchPlan (optional retry path)
                                   ↓
                          ┌─────────────────┐
                          │ Reporting Layer │
                          └────────┬────────┘
                                   ↓
                              Report
```

### Step-by-step: produces and consumes

| Step | Produces | Consumes |
|------|----------|----------|
| **Parsing** | `ParsedDocument` | PDF bytes |
| **Analysis** | `PaperReproductionAnalysis` | `ParsedDocument` |
| **Discovery** | `ResearchResourceDiscovery` | `PaperReproductionAnalysis` |
| **Execution Planning** | `ExecutionStrategy`, abstract `ExecutionGraph` | `PaperReproductionAnalysis`, `ResearchResourceDiscovery` |
| **Execution Materialization** | `ExecutionMaterialization`, materialized `ExecutionGraph`, `MaterializationReport` | Strategy, discovery, abstract graph, workspace context |
| **Execution** | `ExecutionRun`, `ExecutionReport`, `ExecutionTrace`, artifacts | `READY` materialized `ExecutionGraph`, Runtime-provided services |
| **Verification** | `VerificationResult` | Execution report/artifacts, analysis goal/evaluation criteria |
| **Review** | Review report, patch plan | Analysis (context), tasks, verification result |
| **Reporting** | Final report | Full workflow history |

**Invariant:** No stage below Analysis re-parses the PDF for reproduction facts. No stage above Implementation executes code. No stage in Analysis searches outside the paper.

---

## 6. Current Scope (v1.2 implemented baseline; v1.3 in progress)

### Completed

| Layer / Interface | Status | Notes |
|-------------------|--------|-------|
| **Platform Facade** | ✅ Complete | `Man1Lab` — all interfaces |
| **CLI / SDK / Package** | ✅ Complete | `pip install man1lab` |
| **Parsing** | ✅ Complete | Docling default; PyMuPDF fallback |
| **Analysis** | ✅ Complete | `PaperReproductionAnalysis` |
| **Discovery** | ✅ Complete | `ResearchResourceDiscovery`; GitHub Provider |
| **Execution Planning** | ✅ Complete | `ExecutionStrategy`; six embedded providers + Decision Foundation |
| **Planning** | ✅ Complete | Strategy-driven `TaskModel` |
| **Implementation** | ✅ Complete | GQ-1 + RAG |
| **Execution** | ✅ Complete | Environment prep + script run |
| **Verification / Review / Report** | ✅ Complete | End-to-end |
| **Experiment tracking** | ✅ Complete | MLflow via port |

### In progress / partial

| Item | Status |
|------|--------|
| Review loop re-implementation | Patch plan produced; automatic Coder/Runner retry not enabled |
| Full training reproduction success | Pipeline runs end-to-end; success not guaranteed |
| MCP / REST interfaces | Reserved layout only |
| Execution Engine | Core models, scheduling, state machine, trace, artifacts, reports, durable persistence, and LocalExecutor implemented |
| Runtime-owned execution persistence | ✅ Phase 1–2 — `FileExecutionStore`, engine injection, cross-process resume |
| Planning-to-Execution Materialization | Implemented for complete, conflict-free, pinned execution evidence; incomplete and unsupported cases block safely |

### Planned (roadmap)

| Capability | Milestone |
|------------|-----------|
| **ExecutionStore + Runtime injection** | ✅ v1.3 Phase 1–2 |
| **LocalExecutor + facade/console** | ✅ implemented |
| **Planning-to-Execution Materialization** | ✅ v1.3 — bounded executable graph readiness contract |
| **Repository Understanding** | v1.4 — `RepositoryKnowledge` artifact |
| **Repository Adaptation** | v1.5 |
| **Knowledge Memory** | Future |
| **Failure recovery loop** | Future — re-invoke Coder/Runner on patch |

---

## 7. Future Extensions

Future capabilities **attach to the same layer cake**. They consume `PaperReproductionAnalysis`; they do not require re-designing Parsing or re-defining the canonical object.

### Implemented (v1.2)

| Extension | Layer | Consumes from analysis |
|-----------|-------|----------------------|
| **Research Resource Discovery** | Discovery | `reproduction_gaps`, `resources.external_resources`, metadata → `ResearchResourceDiscovery` |
| **Execution Planning** | Execution Planning | Analysis + Discovery → `ExecutionStrategy` |

### Planned (roadmap)

| Extension | Layer | Consumes from analysis |
|-----------|-------|----------------------|
| **Repository Understanding** | v1.3 | Selected repository → `RepositoryKnowledge` |
| **Environment discovery** | Execution support | `resources.dependencies`, method framework |
| **Benchmark evaluation** | Evaluation + verification | `evaluation.metrics`, `evaluation.benchmarks`, `goal.scope` |
| **Paper extension** | New workflow variant | `goal`, `evaluation`, lineage fields (future) |
| **Continuous research** | Orchestration + history | Versioned analysis snapshots |

**Parsing Layer remains stable** when these features ship: discovery and extension operate on analysis output, not on re-extracting markdown from PDF unless the user explicitly re-runs Analysis.

---

## 8. Architecture Decisions

This document states **structure and boundaries**. Detailed rationale lives in ADRs:

| ADR | Topic | Relevance here |
|-----|-------|----------------|
| [ADR-0001](../adr/ADR-0001-Workflow-Orchestrator.md) | Workflow orchestrator owns scheduling | Agents never call each other; coordinator passes artifacts |
| [ADR-0002](../adr/ADR-0002-Stable-Reader-Interface.md) | Reader public interface stability | `read_text()` + `run()` frozen; return type superseded by ADR-0009 |
| [ADR-0003](../adr/ADR-0003-Prompt-Infrastructure.md) | Prompt loading infrastructure | Per-stage prompts; not duplicated in this doc |
| [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) | Planner produces engineering tasks, not summaries | Planning layer boundary |
| [ADR-0005](../adr/ADR-0005-Planner-Capability.md) | Planner capability decomposition | Planning layer behavior |
| [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) | Repository vs runtime artifact ownership | Execution layer boundaries |
| [ADR-0007](../adr/ADR-0007-Execution-Capability.md) | Runner as execution coordinator | Execution layer decomposition |
| [ADR-0008](../adr/ADR-0008-Document-Parsing-Docling.md) | Docling as default parser; ports & adapters | Parsing layer design |
| [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md) | `PaperReproductionAnalysis` as sole pipeline domain object | Section 4 and data flow |
| [ADR-0010](../adr/ADR-0010-Hydra-Configuration.md) | Hydra at configuration layer only | Infrastructure; not duplicated here — see [infrastructure.md](infrastructure.md) |
| [ADR-0011](../adr/ADR-0011-Pixi-Environment.md) | Pixi at repository environment layer only | Infrastructure; not duplicated here — see [infrastructure.md](infrastructure.md) |
| [ADR-0012](../adr/ADR-0012-Experiment-Tracking-MLflow.md) | MLflow at experiment tracking layer only | Infrastructure; thin wrapper at composition root |
| [ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md) | Discovery capability and artifact | Discovery layer |
| [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) | Execution Planning capability | Execution Planning layer |
| [ADR-0017](../adr/ADR-0017-Execution-Planning-Service-Architecture.md) | Execution Planning service architecture | Execution Planning services/ports/providers |
| [ADR-0016](../adr/ADR-0016-GitHub-Discovery-Provider.md) | GitHub as first external Discovery Provider | Discovery adapters |

When this document and an ADR disagree, **the ADR wins** for the specific decision; update this document in the same documentation pass.

---

## Version History

| Version | Name | Summary |
|---------|------|---------|
| **v1.2.0** | Platform Capability | CLI, SDK, package distribution, Discovery + Execution Planning integrated, GitHub Provider, strategy-driven Planner |
| v1.1.0 | Foundation Release | Infrastructure adoption; `PaperReproductionAnalysis`; Docling, Hydra, Pixi, MLflow |
| v1.0.0 | MVP | End-to-end reproduction pipeline |

Release notes: [releases/v1.2.2.md](../releases/v1.2.2.md) · [releases/v1.2.1.md](../releases/v1.2.1.md) · [releases/v1.2.0.md](../releases/v1.2.0.md) · [release/v1.0.0.md](../../release/v1.0.0.md)

---

## 9. Non-Goals

Man1Lab v1.x explicitly **does not** aim to:

| Non-goal | Clarification |
|----------|---------------|
| **Autonomously generate research ideas** | It reproduces existing papers; it does not propose new research agendas |
| **Close the scientific loop** | It does not autonomously iterate hypothesis → experiment → publication |
| **Replace researcher judgment** | Verification checks engineering signals; scientific validity remains human-owned |
| **Open-ended exploration** | Stages are bounded; there is no free-form “research agent” browsing literature |
| **Infer beyond the paper** | Analysis records gaps instead of inventing missing hyperparameters, URLs, or methods |
| **Search the open web during analysis** | Resource discovery is a separate Discovery layer ([ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md)) |
| **Guarantee SOTA reproduction accuracy** | The platform targets engineering reproducibility infrastructure, not benchmark leadership |
| **Multi-paper autonomous research programs** | v1.x is single-paper reproduction; multi-paper orchestration is out of scope |
| **Human-in-the-loop product UX** | Not a collaborative IDE; interactive steering is future work |
| **Cloud-scale distributed execution** | Execution is local workspace–scoped in v1.x |

Non-goals are **features intentionally deferred or excluded**, not missing bugs. They protect layer boundaries and keep the platform focused on **paper-grounded research engineering**.

---

## Document Maintenance

| Change type | Update here | Update ADR |
|-------------|-------------|------------|
| New platform layer | Yes | Yes, if decision is non-obvious |
| New canonical artifact field | Brief mention in §4 | Yes, if breaking or boundary-related |
| Backend swap (e.g. parser) | §3 Parsing only | Yes |
| Implementation detail | No — use CAPABILITIES / CURRENT_STATUS | Rarely |

**Last aligned with:** Man1Lab v1.3.0 — Execution Runtime and Materialization
