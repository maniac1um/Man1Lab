# Man1Lab Architecture

**Version:** v1.1.0  
**Status:** Living document — platform-level design  
**Audience:** Architects, contributors, and long-term maintainers  
**Horizon:** 3–5 years

This document describes **what Man1Lab is**, how its layers relate, and where responsibility boundaries lie. It is the highest-level architecture reference for the project.

For **specific decisions** (orchestrator ownership, parsing backend, canonical analysis artifact), see [Architecture Decision Records](../adr/README.md). ADRs record *why* a choice was made; this document records *what the system is*.

For **implementation status and benchmarks**, see [CURRENT_STATUS.md](../CURRENT_STATUS.md) and [CAPABILITIES.md](CAPABILITIES.md).

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
| **v1.0.x** | **MVP** — one paper in, one reproduction pipeline out |
| **v1.1.x (now)** | **Platform Foundation** — infrastructure adoption, canonical analysis artifact, governance |
| **v1.2+ (next)** | **Platform Capability** — repository discovery, environment generation, verification, failure recovery |

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

### Planning Layer

| | |
|--|--|
| **Responsibility** | Transform analysis into an **ordered engineering task graph** |
| **Input** | `PaperReproductionAnalysis` |
| **Output** | `TaskModel` — executable engineering steps with dependencies |
| **Does** | Decompose reproduction into concrete steps (environment, data, model, training, evaluation, etc.) |
| **Does NOT** | Re-read the PDF, rediscover paper facts, write source code, or execute scripts |

Planning answers: *In what order should engineering work happen?*  
It does **not** re-understand the paper — that belongs to Analysis.

See [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) and [ADR-0005](../adr/ADR-0005-Planner-Capability.md).

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
| **Responsibility** | Run the reproduction project in a prepared runtime |
| **Input** | `Workspace` |
| **Output** | `ExecutionResult` — exit status, logs, duration |
| **Does** | Prepare environment (e.g. virtualenv, dependencies), plan invocation, execute entrypoint scripts |
| **Does NOT** | Generate or modify repository source, parse papers, or perform LLM-based paper analysis |

Execution is **runtime-only**. Repository artifacts and runtime artifacts have distinct ownership — see [ADR-0006](../adr/ADR-0006-Runtime-Artifact-Ownership.md) and [ADR-0007](../adr/ADR-0007-Execution-Capability.md).

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
| **Future extensibility** | Repository discovery, environment discovery, and benchmark modules attach to analysis modules and gaps — not a second paper parse |

Schema versioning (`schema_version`) allows evolution without breaking the architectural rule: **one canonical analysis artifact per paper run**.

See [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md).

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
                          │ Planning Layer  │
                          └────────┬────────┘
                                   ↓
                              TaskModel
                         (engineering task graph)
                                   ↓
                          ┌─────────────────────┐
                          │ Implementation Layer│
                          └────────┬────────────┘
                                   ↓
                              Workspace
                                   ↓
                          ┌─────────────────┐
                          │ Execution Layer │
                          └────────┬────────┘
                                   ↓
                           ExecutionResult
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
| **Planning** | `TaskModel` | `PaperReproductionAnalysis` |
| **Implementation** | `Workspace` | `PaperReproductionAnalysis`, `TaskModel` |
| **Execution** | `ExecutionResult` | `Workspace` |
| **Verification** | `VerificationResult` | `Workspace`, `ExecutionResult`, analysis goal/evaluation (criteria) |
| **Review** | Review report, patch plan | Analysis (context), tasks, verification result |
| **Reporting** | Final report | Full workflow history |

**Invariant:** No stage below Analysis re-parses the PDF for reproduction facts. No stage above Implementation executes code. No stage in Analysis searches outside the paper.

---

## 6. Current Scope (v1.x)

### Completed

| Layer | Status | Notes |
|-------|--------|-------|
| **Parsing** | ✅ Complete | Docling default; PyMuPDF fallback; adapter architecture |
| **Analysis** | ✅ Complete | `PaperReproductionAnalysis`; pipeline-wide migration (Phase 2.4) |
| **Planning** | ✅ Implemented | Consumes modular analysis; produces `TaskModel` |
| **Implementation** | ✅ Implemented | Repository generation with validation and acceptance gate |
| **Execution** | ✅ Implemented | Environment prep + script execution |
| **Verification** | ✅ Implemented | Deterministic checks feeding review |
| **Reporting** | ✅ Implemented | Workflow summary report |
| **Experiment tracking** | ✅ Implemented | MLflow via `ExperimentTracker` port; optional noop backend |

### In progress / partial

| Item | Status |
|------|--------|
| Review loop re-implementation | Patch plan produced; automatic Citation retry not enabled |
| Analysis prompt alignment | Schema landed; prompt refinement for gaps/scope ongoing |
| Full training reproduction success | Pipeline runs end-to-end; successful training not guaranteed |

### Planned (architecture reserved, not yet productized)

| Capability | Relationship to architecture |
|------------|------------------------------|
| **Repository discovery** | Consumes `reproduction_gaps` + metadata; does not replace Analysis |
| **Environment discovery** | Resolves dependencies at runtime; does not rewrite analysis |
| **Continuous research** | Lineage and iteration atop existing artifacts |
| **Benchmark analysis** | Extends evaluation module consumption |

---

## 7. Future Extensions

Future capabilities **attach to the same layer cake**. They consume `PaperReproductionAnalysis`; they do not require re-designing Parsing or re-defining the canonical object.

| Extension | Layer | Consumes from analysis |
|-----------|-------|----------------------|
| **Repository discovery** | Post-analysis, pre- or co-planning | `reproduction_gaps` (repository), `resources.external_resources`, metadata |
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

When this document and an ADR disagree, **the ADR wins** for the specific decision; update this document in the same documentation pass.

---

## Version History

| Version | Name | Summary |
|---------|------|---------|
| **v1.1.0** | Foundation Release | Platform foundation complete. Analysis layer canonical artifact is `PaperReproductionAnalysis`. Infrastructure (Docling, Hydra, Pixi, MLflow) adopted via Provider / Adapter ports. Documentation and infrastructure governance established. |
| v1.0.0 | MVP | End-to-end single-paper reproduction pipeline with real LLM integration, repository generation, execution, verification, review, and reporting. |

Release notes: [releases/v1.1.0.md](../releases/v1.1.0.md) · [release/v1.0.0.md](../../release/v1.0.0.md)

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
| **Search the open web during analysis** | Repository and resource discovery are separate future layers |
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

**Last aligned with:** Man1Lab v1.1.0 — Foundation Release (Parsing + Analysis + Infrastructure adoption)
