# Execution Planning — Capability Design

**Project:** Man1Lab  
**Version:** Design draft  
**Status:** Design Only — no implementation commitment  
**Audience:** Architects, platform maintainers  
**Horizon:** Platform Capability (v1.2+)  
**Last updated:** 2026-07-03

Related documents:

- [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) — architectural decision
- [ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md) — upstream Discovery capability
- [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md) — upstream Analysis artifact
- [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) / [ADR-0005](../adr/ADR-0005-Planner-Capability.md) — downstream Planner capability
- [research-resource-discovery.md](research-resource-discovery.md) — companion Discovery design

This document defines **what Execution Planning is** as a platform capability. It does **not** specify schemas, workflows, APIs, classes, prompts, or implementation code.

---

## 1. Purpose

Execution Planning exists because **knowing which resources exist is not the same as knowing how to use them**.

Analysis records what the paper requires. Discovery records which external resources were found, verified, ranked, and selected. Neither artifact answers the engineering question that must be settled before implementation begins: **how should reproduction proceed given what we know?**

Execution Planning converts:

```text
PaperReproductionAnalysis
        +
ResearchResourceDiscovery
        ↓
ExecutionStrategy
```

Its responsibility is **making engineering decisions** — binding resources into a coherent reproduction path, committing to reuse versus adaptation versus generation, and recording assessed risks and fallbacks.

Execution Planning **does not execute** those decisions. It does not clone repositories, install dependencies, generate code, or run training scripts. It produces a durable record of **engineering intent** that downstream capabilities consume without re-deriving strategy from scattered facts.

Without Execution Planning, the Planner must implicitly choose engineering direction while decomposing tasks. That conflates strategy with task ordering, hides decisions inside task text, and prevents audit of *why* a reproduction campaign chose one path over another.

---

## 2. Capability Position

### 2.1 Platform stack

```text
PDF
    ↓
Parsing
    ↓
Analysis
    ↓
PaperReproductionAnalysis
    ↓
Discovery
    ↓
ResearchResourceDiscovery
    ↓
Execution Planning                    ← this capability
    ↓
ExecutionStrategy
    ↓
Planner
    ↓
TaskModel
    ↓
Implementation
    ↓
Execution
```

### 2.2 Why Execution Planning sits between Discovery and Planner

| Upstream (Discovery) | Gap | Downstream (Planner) |
|----------------------|-----|----------------------|
| Records **what resources exist** and **which were selected** per gap | Neither selects **how** those resources combine into a reproduction campaign | Decomposes a **committed strategy** into ordered engineering tasks |

Discovery stops at resource resolution. It validates facts and commits selections with evidence — it does not decide whether to run the official repository as-is, patch a community fork, or generate code from scratch when gaps remain.

The Planner decomposes work. It orders tasks for Coder and Runner — it should not simultaneously infer engineering strategy from analysis gaps and discovery rankings.

Execution Planning is the **single engineering decision point** between verified resource facts and task decomposition. It absorbs the strategy responsibility that v1.1 Planner performed implicitly, freeing Planner to focus on *what tasks* follow from a committed strategy.

---

## 3. Inputs

Execution Planning consumes **only canonical artifacts**:

| Input | Role |
|-------|------|
| **`PaperReproductionAnalysis`** | Reproduction scope, method, evaluation intent, paper-stated resources, and recorded gaps |
| **`ResearchResourceDiscovery`** | Evidence-backed candidates, verification outcomes, rankings, selections, and unresolved discovery gaps |

Both artifacts are consumed **read-only**. Execution Planning does not mutate upstream artifacts, re-parse the paper, or re-run Discovery.

### 3.1 What Execution Planning never reads

Execution Planning has **no direct access** to:

| Source | Why excluded |
|--------|--------------|
| **PDF** | Paper interpretation is Analysis responsibility |
| **GitHub** | Resource search and verification are Discovery responsibility |
| **OpenAlex** | Bibliographic enrichment is outside capability scope |
| **HuggingFace** | Model/dataset index access is Discovery provider territory |
| **HTTP** | No live network calls — strategy derives from artifacts |
| **Repositories** | No clone, no file tree inspection, no README fetch |

If strategy requires facts not present in the two canonical inputs, Execution Planning must record that as **risk or gap** in its output — not fetch new external evidence.

---

## 4. Output

Execution Planning produces **`ExecutionStrategy`** — the canonical artifact of this capability.

### 4.1 What ExecutionStrategy is

`ExecutionStrategy` is a structured record of **engineering decisions**: which discovered resources anchor the campaign, how they will be used (reuse, adapt, generate), what risks and fallbacks apply, and what scope degradations are acceptable.

It is the auditable answer to: *Given this analysis and these discovered resources, how should Man1Lab attempt reproduction?*

### 4.2 What ExecutionStrategy is not

`ExecutionStrategy` is **not** `TaskModel`.

| Artifact | Concern |
|----------|---------|
| **`ExecutionStrategy`** | Engineering intent — strategy, bindings, risks |
| **`TaskModel`** | Task decomposition — ordered work units for Coder and Runner |

The Planner converts `ExecutionStrategy` into `TaskModel`. Tasks inherit strategy decisions; they do not replace them. A task plan without an explicit strategy artifact cannot be audited independently of task wording.

### 4.3 Downstream consumption

| Consumer | Uses ExecutionStrategy for |
|----------|---------------------------|
| **Planner** | Task decomposition aligned to committed strategy |
| **Implementation (Coder)** | Reuse/adapt/generate intent per module |
| **Repository Understanding** (future) | Which repo path to map against analysis modules |
| **Repository Adaptation** (future) | Whether and how much modification is authorized |
| **Review / Report** | Strategy rationale and risk disclosure |

---

## 5. Core Responsibilities

Execution Planning makes decisions across five categories. This section describes **what each category means** — not field names, schemas, or algorithms.

### 5.1 Resource Decision

Bind discovery selections into a coherent reproduction resource set.

Discovery may select a primary repository, checkpoint, dataset portal, and configuration artifact independently per gap. Execution Planning decides **how those selections combine** into one reproduction path: which resource anchors the campaign, which are supporting assets, and whether multi-resource combinations are viable for the stated reproduction scope.

Resource decision respects discovery selections as the factual baseline. It may record rationale for preferring a fallback candidate or accepting a partial discovery outcome — but it does not re-search or re-verify.

### 5.2 Reuse Decision

Commit to how much existing engineering artifact will be reused unchanged.

When Discovery identifies a viable official or community repository, Execution Planning decides whether reproduction should **run that artifact as-is**, lean on a **community fork** with different maintenance characteristics, or pursue a **hybrid** path that reuses some components while replacing others.

Reuse decision considers verification status, discovery confidence, and analysis scope — without inspecting repository contents directly.

### 5.3 Adaptation Decision

Authorize whether downstream modification of discovered resources is required.

When reuse alone is insufficient — framework version mismatch, missing config, scope gap between repo and paper evaluation — Execution Planning decides whether **Repository Adaptation** (future) is in scope, at what granularity (pin versions, patch scripts, fork), and what must remain untouched.

Adaptation decision records intent only. It does not apply patches or modify repositories.

### 5.4 Generation Decision

Commit to greenfield or partial generation when discovery gaps block reuse.

When no viable resource supports the required reproduction scope, Execution Planning decides whether to **generate code from scratch**, generate only missing modules, **narrow reproduction scope** to what existing resources support, or **abort** with explicit rationale.

Generation decision prevents Implementation from silently assuming greenfield when discovery partially succeeded — and prevents Planner from embedding generation choices inside individual tasks without a strategy-level commitment.

### 5.5 Risk Decision

Assess confidence, fallbacks, and acceptable degradation.

Execution Planning records **blocking versus degraded risks**: unresolved discovery gaps, low verification confidence, ambiguous multi-official situations, license concerns surfaced by Discovery, and scope mismatches between analysis goal and available resources.

Risk decision defines fallback paths (alternate discovery selections, reduced scope, manual intervention) so downstream capabilities do not rediscover strategy under failure.

---

## 6. Out of Scope

Execution Planning **never**:

| Activity | Correct owner |
|----------|---------------|
| **Search** external indexes for resources | Discovery |
| **Verify** candidate viability or collect evidence | Discovery |
| **Clone** repositories | Execution |
| **Generate** code or configs | Implementation (Coder) |
| **Run** training, evaluation, or scripts | Execution (Runner) |
| **Evaluate** reproduction success | Verification / Review |
| **Read** repository file trees or README content | Repository Understanding (future) |
| **Order** engineering tasks | Planner |
| **Modify** analysis or discovery artifacts | Forbidden — read-only consumption |

Execution Planning decides. It does not operate.

---

## 7. Capability Boundary

Each platform capability answers a distinct question. Execution Planning occupies the **strategy** layer between resource facts and task plans.

| Capability | Question |
|------------|----------|
| **Analysis** | What is required? |
| **Discovery** | What resources exist? |
| **Execution Planning** | How should reproduction proceed? |
| **Planner** | What tasks should be executed? |
| **Implementation** | How are tasks implemented? |
| **Execution** | Can they run? |

### 7.1 Boundary diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│  ANALYSIS                                                            │
│  PaperReproductionAnalysis — paper-stated facts + gaps               │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│  DISCOVERY                                                           │
│  ResearchResourceDiscovery — evidence, verification, selection       │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│  EXECUTION PLANNING (this capability)                                │
│  ExecutionStrategy — engineering decisions + risks                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│  PLANNER → IMPLEMENTATION → EXECUTION                                │
│  TaskModel → code/workspace → ExecutionResult                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Classification

Execution Planning is a **Platform Capability** — native Man1Lab domain logic on canonical artifacts.

It is **not**:

| Misclassification | Why |
|-------------------|-----|
| **Agent** | Capability layer, not an LLM agent stage |
| **Provider** | Does not call external indexes |
| **Adapter** | Not infrastructure wrapping a vendor tool |
| **Infrastructure** | Does not manage Hydra, Pixi, MLflow, or SDK bindings |

---

## 8. Engineering Strategy

Execution Planning commits to a **strategy family** — a conceptual reproduction posture, not a task list. The following families describe common decision outcomes. They are **design vocabulary**, not schema enumerations.

### 8.1 Official Repository

Reproduction anchors on the paper-linked or discovery-verified official implementation. Minimal modification expected. Best when verification passes, officiality is strong, and analysis scope aligns with repo capabilities.

### 8.2 Community Fork

Reproduction anchors on a non-official but viable community reimplementation. May trade officiality for maintenance, documentation, or framework compatibility. Execution Planning records why the official path was not selected.

### 8.3 Hybrid

Reproduction combines reused artifacts from multiple sources — for example, official weights with a community training script, or official code with an external dataset portal. Execution Planning defines which component anchors the workspace and which are supporting inputs.

### 8.4 Greenfield

Reproduction generates substantial new engineering artifact because discovery gaps or verification failures block reuse. Scope may be full training reproduction or a narrowed subset explicitly recorded in strategy. Highest cost and risk — must be an explicit decision, not a Planner default.

### 8.5 Manual

Reproduction cannot proceed autonomously with available artifacts. Human input is required for resource supply, scope negotiation, or license clearance. Strategy records what is blocked and what manual action unblocks it.

Strategy families may combine with adaptation or generation sub-decisions. The artifact must make the committed posture legible without reading task text.

---

## 9. Relationship with Future Capabilities

v1.1 attached repository understanding loosely after Discovery. The target architecture attaches repository-oriented capabilities **after ExecutionStrategy**, because their work depends on a committed engineering direction.

### 9.1 Repository Understanding

| Aspect | Direction |
|--------|-----------|
| **Purpose** | Semantic mapping between repository structure and analysis modules |
| **Input** | `ExecutionStrategy` (which repo path is authoritative) + canonical artifacts |
| **Why after Execution Planning** | Understanding inspects the repo **chosen by strategy** — not every discovery candidate |

Without Execution Planning, Repository Understanding would map against ambiguous or unselected candidates, producing analysis that does not align with the reproduction campaign.

### 9.2 Repository Adaptation

| Aspect | Direction |
|--------|-----------|
| **Purpose** | Apply patches, pins, or forks to align resources with paper requirements |
| **Input** | `ExecutionStrategy` adaptation authorization |
| **Why after Execution Planning** | Adaptation scope is a **strategy decision** — Discovery verifies facts; Adaptation executes modifications |

### 9.3 Environment Preparation

| Aspect | Direction |
|--------|-----------|
| **Purpose** | Resolve runtime dependencies, containers, and workspace layout |
| **Input** | `ExecutionStrategy` + `TaskModel` |
| **Why after Execution Planning** | Environment choices depend on strategy family (reuse official env vs greenfield stack) |

### 9.4 Target downstream flow

```text
ExecutionStrategy
    ↓
Repository Understanding    (when strategy selects repo-based path)
    ↓
Repository Adaptation       (when strategy authorizes modification)
    ↓
Environment Preparation
    ↓
Implementation → Execution
```

Future capabilities consume **strategy first**, then operate. Discovery remains the evidence layer; Execution Planning remains the decision layer.

---

## 10. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Single Engineering Decision Point** | All reuse/adapt/generate/risk commitments flow through `ExecutionStrategy` — not scattered across Planner tasks or Coder prompts |
| **Artifact-driven** | Inputs and outputs are canonical, versioned artifacts — not ad hoc context passed between agents |
| **Capability Isolation** | Execution Planning logic does not import Discovery providers, GitHub clients, or execution runners |
| **No Provider Awareness** | Strategy derives from `ResearchResourceDiscovery` content — not from which Discovery provider produced it |
| **No Infrastructure Awareness** | Hydra, Pixi, MLflow, and workspace layout are composition-root concerns — not Execution Planning logic |
| **Strategy Before Tasks** | `ExecutionStrategy` must exist before Planner produces `TaskModel` on the target path |
| **Read-only upstream** | Analysis and Discovery artifacts are immutable inputs — strategy records overrides with rationale, not silent mutation |
| **Partial input tolerance** | Strategy must be definable when Discovery is partial — recording degradation explicitly rather than failing silently |
| **Evidence respects Discovery** | Execution Planning does not re-litigate verification outcomes; it decides how to proceed given them |
| **Auditability** | Strategy rationale must be reconstructable years later without re-running the pipeline |

---

## 11. Future Evolution

This capability design is complete at the **responsibility** level. Downstream design and implementation proceed in separate documents.

| Topic | Document / work |
|-------|----------------|
| **`ExecutionStrategy` canonical artifact** | Schema design — fields for strategy family, resource bindings, risk, provenance |
| **Execution Planning workflow** | Internal stages (if any), partial strategy semantics, coordinator integration |
| **Planner migration** | Planner consumes `ExecutionStrategy`; strategy removed from Planner scope |
| **Implementation refactor** | Coder reads strategy intent explicitly; generation vs reuse paths separated |
| **Repository Understanding / Adaptation** | Capability designs consuming `ExecutionStrategy` |
| **v1.1 compatibility path** | Analysis → Planner without Discovery or Execution Planning when user supplies resources |

Evolution roadmap:

```text
v1.1  Foundation              Analysis → Planner → Implementation → Execution
v1.2  Discovery + Planning    Analysis → Discovery → Execution Planning → Planner → …
v1.3  Repo capabilities       Execution Planning → Understanding → Adaptation → …
```

Each capability produces a typed artifact. No capability re-parses the PDF for reproduction facts.

---

# Execution Planning Capability Audit

Audit performed after drafting this capability design. Documentation only — no schema, workflow, or code.

### Capability responsibility

| Check | Result |
|-------|--------|
| Converts Analysis + Discovery into ExecutionStrategy | ✅ Pass |
| Makes engineering decisions, does not execute them | ✅ Pass |
| Five decision categories defined (resource, reuse, adaptation, generation, risk) | ✅ Pass |
| Strategy families described conceptually without schema enums | ✅ Pass |

### Boundary validation

| Check | Result |
|-------|--------|
| Not Agent, Provider, Adapter, or Infrastructure | ✅ Pass |
| Does not search, verify, clone, generate, run, or read repositories | ✅ Pass |
| Does not read PDF, GitHub, OpenAlex, HuggingFace, or HTTP | ✅ Pass |
| Does not mutate upstream artifacts | ✅ Pass |
| Distinct from Execution (Runner) per ADR-0007 | ✅ Pass |

### Input/output validation

| Check | Result |
|-------|--------|
| Inputs: PaperReproductionAnalysis + ResearchResourceDiscovery only | ✅ Pass |
| Output: ExecutionStrategy (not TaskModel) | ✅ Pass |
| Planner downstream conversion to TaskModel documented | ✅ Pass |
| No schema, workflow, or class definitions in this document | ✅ Pass |

### Relationship to Analysis

| Check | Result |
|-------|--------|
| Consumes PaperReproductionAnalysis read-only | ✅ Pass |
| Does not replace or reinterpret paper ([ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md)) | ✅ Pass |
| Respects analysis scope and gaps in strategy decisions | ✅ Pass |

### Relationship to Discovery

| Check | Result |
|-------|--------|
| Consumes ResearchResourceDiscovery read-only | ✅ Pass |
| Does not re-run Discovery ([ADR-0013](../adr/ADR-0013-Research-Resource-Discovery.md)) | ✅ Pass |
| Discovery does not decide execution strategy | ✅ Pass |
| Selection is factual input; strategy is separate decision | ✅ Pass |

### Relationship to Planner

| Check | Result |
|-------|--------|
| Planner decomposes ExecutionStrategy into TaskModel | ✅ Pass |
| Strategy responsibility removed from Planner scope over migration | ✅ Pass |
| Aligns with ADR-0004 / ADR-0005 decomposition role | ✅ Pass |

### Future extensibility

| Check | Result |
|-------|--------|
| Repository Understanding attaches after ExecutionStrategy | ✅ Pass |
| Repository Adaptation authorized by strategy, not Discovery | ✅ Pass |
| Environment Preparation follows strategy family | ✅ Pass |
| v1.1 compatibility path acknowledged | ✅ Pass |
| Evolution roadmap recorded without implementation detail | ✅ Pass |

### Potential architecture conflicts

| Risk | Assessment |
|------|------------|
| Planner still embeds strategy during migration | ⚠️ Transitional — Planner migration is explicit future work; v1.1 path documented as compatibility fallback |
| Naming collision: Execution vs Execution Planning | ✅ Mitigated — ADR-0014 and §7 distinguish strategy artifact from Runner capability |
| Partial Discovery blocks strategy | ⚠️ Requires schema/workflow design — principle of partial-input tolerance stated; behavior deferred to ExecutionStrategy schema |
| Discovery design doc §7.1 uses "Resource Discovery Result" naming | ✅ No conflict — same artifact as ResearchResourceDiscovery; naming harmonized in ADR-0013 |
| Coder infers strategy without ExecutionStrategy | ⚠️ Transitional — Implementation refactor listed in Future Evolution |

---

## Verdict

**Ready for ExecutionStrategy Schema Design**

Execution Planning is a clearly defined third core Platform Capability with stable architectural responsibility, canonical inputs and output, and explicit boundaries against Analysis, Discovery, Planner, Implementation, and Execution. Schema, workflow, and implementation remain out of scope for this document.
