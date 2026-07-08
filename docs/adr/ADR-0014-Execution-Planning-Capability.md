# ADR-0014 — Execution Planning Capability

## Status

Accepted

## Date

2026-07-03

## Implementation Status (2026-07-08)

Execution Planning Foundation (Phase 5.2) is **implemented**. Internal service/port/provider layering is recorded in [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md). `ExecutionStrategy` schema, validation, runtime models, builder, workflow, and strategy-driven Planner integration are in production. Business reasoning in providers is pending the next implementation phase.

## Context

Man1Lab v1.2 introduced **Research Resource Discovery** ([ADR-0013](ADR-0013-Research-Resource-Discovery.md)) as the second core **Platform Capability** after Analysis ([ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md)). The platform now separates paper understanding from external resource resolution.

Current target capability pipeline:

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
Planner                    ← v1.1 path (strategy + decomposition mixed)
    ↓
TaskModel
    ↓
Implementation (Coder)
    ↓
Execution (Runner)
```

### The missing capability

Discovery produces **`ResearchResourceDiscovery`** — evidence-backed candidates, verification, rankings, selections, and discovery gaps. Discovery **intentionally stops** after resource selection. It records *which external resources exist and were chosen*; it does **not** decide *how those resources should be used* in a reproduction campaign.

The v1.1 **Planner** ([ADR-0004](ADR-0004-Planning-Strategy.md), [ADR-0005](ADR-0005-Planner-Capability.md)) currently sits immediately after Analysis (or after Discovery in the target pipeline) and implicitly performs **two distinct responsibilities**:

| Responsibility | Question | Correct owner |
|----------------|----------|---------------|
| **Engineering strategy** | Which repository path? Reuse discovered repo or regenerate? Patch or rewrite? Official repo, community fork, or greenfield? | **Execution Planning** (missing) |
| **Task decomposition** | Given a committed strategy, what ordered engineering tasks must Coder and Runner execute? | **Planner** (existing) |

Mixing strategy and decomposition in Planner causes:

- **Opaque resource decisions** — task plans embed strategy choices without an auditable strategy artifact
- **Discovery underutilization** — Planner cannot consistently consume `ResearchResourceDiscovery`; it re-infers strategy from analysis alone
- **Implementation confusion** — Coder receives tasks without explicit reuse/adaptation/generation intent
- **Blocked downstream evolution** — Repository Understanding and Repository Adaptation lack a natural upstream capability that commits engineering direction

Discovery must never decide which selected candidate becomes the **execution strategy**. Selection answers *what resource was chosen per gap*; Execution Planning answers *how reproduction will use those resources*.

This ADR records the architectural decision only. It does **not** define APIs, classes, schemas, prompts, or workflow implementation.

## Decision

Adopt **Execution Planning** as a dedicated **Platform Capability layer** — the third core platform capability after **Analysis** and **Discovery**.

### Target capability pipeline

```text
PaperReproductionAnalysis
        ↓
ResearchResourceDiscovery
        ↓
Execution Planning
        ↓
ExecutionStrategy
        ↓
Planner
        ↓
TaskModel
        ↓
Implementation (Coder)
        ↓
Execution (Runner)
```

### Canonical inputs and output

| Capability | Input | Output |
|------------|-------|--------|
| Analysis | `ParsedDocument` | `PaperReproductionAnalysis` |
| Discovery | `PaperReproductionAnalysis` | `ResearchResourceDiscovery` |
| **Execution Planning** | `PaperReproductionAnalysis`, `ResearchResourceDiscovery` | **`ExecutionStrategy`** |
| Planner | `ExecutionStrategy` (+ analysis context as needed) | `TaskModel` |

**`ExecutionStrategy`** is the **canonical artifact** of the Execution Planning layer — a structured record of engineering decisions: which resources to use, how to use them (reuse, adapt, generate), and assessed risks. It is distinct from both analysis and discovery artifacts.

Execution Planning **does not** modify `PaperReproductionAnalysis` or `ResearchResourceDiscovery`. It **does not** re-run Discovery or re-read the paper.

The v1.1 path (Analysis → Planner → Coder → Execution, without Discovery or Execution Planning) remains valid during migration when resources are user-supplied or gaps are acceptable.

### Execution Planning responsibilities

Execution Planning **is responsible for**:

| Decision area | Examples |
|---------------|----------|
| **Resource decision** | Bind discovery selections to reproduction path; resolve multi-resource combinations (repo + checkpoint + dataset) |
| **Reuse decision** | Use official repo as-is vs community fork vs hybrid |
| **Adaptation decision** | Whether Repository Adaptation (future) is required; scope of patches or pins |
| **Generation decision** | Greenfield code generation when discovery gaps block reuse |
| **Risk assessment** | Confidence, fallback paths, blocking vs degraded reproduction scope |

Execution Planning **is not responsible for**:

| Out of scope | Correct owner |
|--------------|---------------|
| Reading papers | Analysis |
| Searching external indexes | Discovery |
| Collecting evidence | Discovery |
| Repository verification | Discovery |
| Repository cloning | Execution |
| Code generation | Implementation (Coder) |
| Running training or scripts | Execution (Runner) |
| Engineering task ordering | Planner |

### Capability classification

Execution Planning is a **Platform Capability** — native Man1Lab domain logic operating on canonical artifacts.

It is **not**:

| Misclassification | Why |
|---------------------|-----|
| **Agent** | It is a capability layer, not an LLM agent stage like Reader or Planner |
| **Provider** | It does not call external indexes; it consumes discovery output |
| **Adapter** | It is not infrastructure wrapping a vendor tool |
| **Infrastructure layer** | It does not manage Hydra, Pixi, MLflow, or external SDKs |

Execution Planning operates **only on canonical artifacts**. Configuration and tracking remain infrastructure concerns at the composition root ([ADR-0010](ADR-0010-Hydra-Configuration.md), [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md)).

## Alternatives

**Planner performs strategy:** Rejected. Planner's accepted role is **task decomposition** ([ADR-0004](ADR-0004-Planning-Strategy.md), [ADR-0005](ADR-0005-Planner-Capability.md)) — converting a committed strategy into ordered `TaskModel` tasks. Embedding reuse/generation/adaptation decisions in Planner conflates strategy with task ordering, prevents audit of engineering decisions independent of task structure, and blocks clean consumption of `ResearchResourceDiscovery`.

**Discovery performs selection as strategy:** Rejected. Discovery **discovers and validates facts** ([ADR-0013](ADR-0013-Research-Resource-Discovery.md)). Its Selection stage commits resource choices per gap with evidence — not engineering strategy. Merging strategy into Discovery would violate evidence-over-guessing boundaries and force Discovery to decide reuse vs greenfield without a dedicated strategy artifact.

**Coder decides strategy:** Rejected. Implementation must not decide architecture. Coder generates artifacts **from** an explicit strategy and task plan. Allowing Coder to infer reuse vs regeneration duplicates Planning responsibilities and produces inconsistent workspaces.

**Direct Analysis → Planner (skip Discovery and Execution Planning):** Rejected for papers with unresolved resource gaps. Without Discovery, Planner lacks verified external resources; without Execution Planning, Planner must implicitly choose engineering strategy. This was the v1.1 failure mode on benchmark papers. The path remains a **compatibility fallback**, not the target architecture.

## Consequences

**Positive:**

- **Planner simplification** — Planner decomposes tasks only; strategy moves to a dedicated artifact
- **Discovery remains evidence-based** — Discovery does not absorb engineering strategy concerns
- **Explicit implementation input** — Coder and downstream layers receive `ExecutionStrategy` intent (reuse, adapt, generate)
- **Natural upstream for Repository Understanding and Adaptation** — both consume committed strategy, not raw discovery rankings
- **Extensible execution modes** — new modes (official-repo, fork, hybrid, greenfield) extend Execution Planning without changing Discovery pipeline or Planner decomposition rules
- **Third core capability formalized** — Analysis → Discovery → Execution Planning completes the pre-implementation platform stack

**Negative:**

- **Additional capability layer** — workflow coordinator gains invocation and artifact passing logic
- **New canonical artifact required** — `ExecutionStrategy` schema and validation are future design work
- **Planner migration** — Planner input evolves from analysis-only to strategy-first; v1.1 interface coexistence during transition
- **Partial artifact handling** — Execution Planning must define behavior when `ResearchResourceDiscovery` is partial or discovery gaps remain blocking

## Relationship to Other ADRs

- [ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md): Execution Planning **consumes** `PaperReproductionAnalysis` read-only; it does not replace or mutate the analysis artifact. Analysis remains the single paper interpretation.
- [ADR-0013](ADR-0013-Research-Resource-Discovery.md): Execution Planning **consumes** `ResearchResourceDiscovery` read-only; it does not re-run Discovery or override discovery selections without recording strategy rationale. Discovery remains independent.
- [ADR-0004](ADR-0004-Planning-Strategy.md) / [ADR-0005](ADR-0005-Planner-Capability.md): Planner **decomposes** `ExecutionStrategy` into `TaskModel`; engineering strategy decisions migrate out of Planner scope over time.
- [ADR-0001](ADR-0001-Workflow-Orchestrator.md): Orchestrator schedules capabilities; Execution Planning is a new scheduled stage — topology change requires coordinator update in a future implementation ADR or migration note.
- [ADR-0007](ADR-0007-Execution-Capability.md): **Execution** (Runner) runs scripts in workspace — distinct from **Execution Planning** (strategy). Naming similarity is intentional at platform level; artifacts differ (`ExecutionStrategy` vs `ExecutionResult`).
- [ADR-0010](ADR-0010-Hydra-Configuration.md) / [ADR-0011](ADR-0011-Pixi-Environment.md) / [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md): Infrastructure only — Execution Planning logic does not import Hydra, Pixi, MLflow, GitHub, OpenAlex, or HuggingFace.

Companion design (Discovery): [research-resource-discovery.md](../design/research-resource-discovery.md), [research-resource-discovery-schema.md](../design/research-resource-discovery-schema.md), [research-resource-discovery-workflow.md](../design/research-resource-discovery-workflow.md)

Companion design (Execution Planning): [execution-planning.md](../design/execution-planning.md), [execution-strategy-schema.md](../design/execution-strategy-schema.md), [execution-planning-workflow.md](../design/execution-planning-workflow.md)

Implementation architecture: [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md)

## Future Work

Remaining work after foundation (Phase 5.2):

| Topic | Direction |
|-------|-----------|
| **Embedded Execution Planning providers** | Complete (v1.2.1) — see [ADR-0018](ADR-0018-Execution-Planning-Decision-Foundation.md) |
| **Repository Understanding** | Read-only semantic mapping after strategy commits to repo-based path |
| **Repository Adaptation** | Patch/pin/fork execution when strategy selects adaptation mode |
| **Execution modes** | Official repo, community fork, hybrid, greenfield — extensible enum in strategy artifact |
| **Policy Engine** | Org rules (license block, approved postures) — optional pre/post hooks |

Completed (foundation):

| Topic | Status |
|-------|--------|
| `ExecutionStrategy` canonical artifact | ✅ Implemented |
| Execution Planning workflow | ✅ `ExecutionPlanningWorkflow` |
| Service/port/provider architecture | ✅ [ADR-0017](ADR-0017-Execution-Planning-Service-Architecture.md) |
| Planner migration | ✅ Strategy-driven `Planner.run(execution_strategy)` |
| Platform coordinator integration | ✅ `execution_planning.enabled` (default true) |

Evolution roadmap:

```text
v1.1  Foundation           Analysis → Planner → Coder → Execution
v1.2  Discovery            Analysis → Discovery → Execution Planning → Planner → …
v1.3  Repo Understanding    Execution Planning → Repo Understanding → Adaptation
```

Each capability produces a typed artifact. No capability re-parses the PDF for reproduction facts.

---

# ADR-0014 Audit

Audit performed after drafting ADR-0014. Architecture documentation only — no code, schema, or workflow changes.

### New file

| Item | Result |
|------|--------|
| `docs/adr/ADR-0014-Execution-Planning-Capability.md` | ✅ Created |
| ADR index updated | ✅ `docs/adr/README.md` |

### Architecture motivation

| Check | Result |
|-------|--------|
| Missing capability identified (strategy vs decomposition) | ✅ Pass |
| Discovery stops at resource resolution; strategy gap explicit | ✅ Pass |
| Third core platform capability after Analysis and Discovery | ✅ Pass |

### Capability boundary

| Check | Result |
|-------|--------|
| Execution Planning is Capability (not Agent/Provider/Adapter/Infrastructure) | ✅ Pass |
| Responsibilities: resource, reuse, adaptation, generation, risk | ✅ Pass |
| Non-responsibilities: paper read, search, evidence, verify, clone, codegen, execute | ✅ Pass |
| Operates only on canonical artifacts | ✅ Pass |
| Independent from Hydra, Pixi, MLflow, GitHub, OpenAlex, HuggingFace | ✅ Pass |

### Relationship to Analysis

| Check | Result |
|-------|--------|
| Consumes `PaperReproductionAnalysis` read-only | ✅ Pass |
| Does not replace or mutate Analysis ([ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md)) | ✅ Pass |

### Relationship to Discovery

| Check | Result |
|-------|--------|
| Consumes `ResearchResourceDiscovery` read-only | ✅ Pass |
| Does not re-run Discovery ([ADR-0013](ADR-0013-Research-Resource-Discovery.md)) | ✅ Pass |
| Discovery does not decide execution strategy | ✅ Pass |

### Relationship to Planner

| Check | Result |
|-------|--------|
| Planner limited to task decomposition ([ADR-0004](ADR-0004-Planning-Strategy.md), [ADR-0005](ADR-0005-Planner-Capability.md)) | ✅ Pass |
| Planner future input: `ExecutionStrategy` → `TaskModel` | ✅ Pass |
| Strategy removed from Planner scope over migration | ✅ Pass |

### Migration impact

| Check | Result |
|-------|--------|
| v1.1 path coexistence acknowledged | ✅ Pass |
| Planner input change deferred to future migration | ✅ Pass |
| No existing ADR modified | ✅ Pass |
| ADR-0007 naming distinction documented (Execution vs Execution Planning) | ✅ Pass |

### Future milestones

| Milestone | Recorded |
|-----------|----------|
| `ExecutionStrategy` schema | ✅ Future Work |
| Execution Planning workflow | ✅ Future Work |
| Planner migration | ✅ Future Work |
| Repository Understanding / Adaptation | ✅ Future Work |
| Execution modes | ✅ Future Work |

### Conflicts

| Check | Result |
|-------|--------|
| Conflicts with ADR-0013 | ❌ None — ADR-0013 already reserved Execution Planning slot |
| Conflicts with ADR-0009 | ❌ None |
| Requires modifying existing ADRs | ❌ No — future Planner narrowing via migration note or ADR amendment when implemented |

---

## Verdict

**Ready for Execution Planning Capability Design**

The repository formally recognizes **Execution Planning** as the third core Platform Capability after Analysis and Discovery. Capability boundary, artifact contract (`ExecutionStrategy`), and Planner migration direction are recorded. Schema, workflow, and implementation remain out of scope for this ADR.
