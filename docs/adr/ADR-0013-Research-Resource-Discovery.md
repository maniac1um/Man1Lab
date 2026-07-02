# ADR-0013 — Research Resource Discovery

## Status

Draft

## Date

2026-07-02

## Context

Man1Lab v1.1 established `PaperReproductionAnalysis` as the canonical Analysis artifact ([ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md)). Analysis answers **what** the paper states is needed for reproduction — goal, method, resources, evaluation, and recorded `reproduction_gaps`.

Analysis is intentionally **paper-grounded**. It does not search the open web, verify link liveness, judge repository quality, or resolve which external engineering artifact best matches the paper.

| Analysis answers | Analysis does not answer |
|------------------|---------------------------|
| What resources does the paper mention? | Which GitHub repo is the official implementation? |
| What gaps remain unstated in the paper? | Is a candidate repo maintained and runnable? |
| What scope does reproduction require? | Which checkpoint matches the paper's reported model? |
| | Where do datasets, weights, and configs live externally? |

Sending Analysis directly to Planning (v1.1 `TaskModel` generation) or to future Execution Planning forces downstream stages to **infer missing resources** or **assume greenfield code generation**. That conflates three distinct concerns:

1. **Understanding** — what the paper says (Analysis)
2. **Resource resolution** — what exists externally and is verified (Discovery)
3. **Engineering strategy** — how to reproduce using selected resources (Execution Planning)

v1.1 benchmarks show high failure rates when reproduction gaps (repository, checkpoint, dataset, config) remain unresolved at planning time. A dedicated stage is required between Analysis and Execution Planning.

This ADR records the architectural decision only. It does **not** specify APIs, classes, prompts, or implementation code. Detailed capability design lives in [research-resource-discovery.md](../design/research-resource-discovery.md).

## Decision

Adopt **Research Resource Discovery** as a dedicated **Platform Capability layer** between Analysis and Execution Planning.

### Pipeline placement

```text
PaperReproductionAnalysis
        ↓
Research Resource Discovery
        ↓
Execution Planning          (future — not in scope of this ADR)
        ↓
Execution
```

Discovery sits **after Analysis** and **before Execution Planning**. It consumes the canonical analysis artifact and produces a separate discovery artifact. It does **not** modify `PaperReproductionAnalysis`.

The v1.1 path (Analysis → Planning → Coder → Execution) remains valid when gaps are acceptable or the user supplies resources manually. Discovery becomes **required** when `reproduction_gaps` block reproduction.

### Canonical object

| Stage | Input | Output |
|-------|-------|--------|
| Analysis | `ParsedDocument` | `PaperReproductionAnalysis` |
| **Research Resource Discovery** | `PaperReproductionAnalysis` | **`ResearchResourceDiscovery`** |
| Execution Planning (future) | `PaperReproductionAnalysis`, `ResearchResourceDiscovery` | Execution Strategy |

`ResearchResourceDiscovery` is the **canonical artifact** of the Discovery layer — a structured, evidence-backed record of candidates, verification, rankings, selections, and unresolved gaps per resource category. It is distinct from the analysis object and is the sole external-resource input Execution Planning may consume.

### Discovery responsibilities

Discovery runs an internal five-stage pipeline:

```text
Candidate Collection
        ↓
Evidence Collection
        ↓
Verification
        ↓
Ranking
        ↓
Selection
```

| Stage | Responsibility |
|-------|----------------|
| **Candidate Collection** | Gather plausible resource URLs and identifiers from paper-stated links, metadata signals, and controlled external indexes |
| **Evidence Collection** | Attach observable facts supporting or refuting each candidate (README claims, citation match, file signals, model card text, recency) |
| **Verification** | Apply shallow reproducibility checks before selection (reachability, identity, scope alignment, structural viability, license) |
| **Ranking** | Order verified candidates by evidence strength, officiality, scope match, and reproduction suitability |
| **Selection** | Commit primary (and optional fallback) resources per gap; retain full candidate history and record unresolved gaps |

### Capability boundary

Discovery **finds and validates** resources. It does **not**:

- clone repositories, install dependencies, or execute code (Execution / Environment layers)
- modify repository source (Repository Adaptation — future)
- generate code from scratch (Implementation / Coder layer)
- re-read or rewrite the paper (Analysis layer)
- define engineering task order or reproduction strategy (Planning / Execution Planning)

External indexes (GitHub API, HuggingFace, HTTP fetch) sit behind **Discovery ports** — the same thin-integration pattern as Docling ([ADR-0008](ADR-0008-Document-Parsing-Docling.md)) and MLflow ([ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md)). Business agents **do not call vendor APIs directly**.

## Alternatives

**Direct GitHub Search:** Rejected. Search returns URLs ranked by keyword relevance, not by paper identity, evidence, or verification. It conflates discovery with ranking and produces unverified hits unsuitable as Execution Planning input.

**Direct Git Clone:** Rejected. Clone is an Execution-layer operation. Running clone during resource resolution blurs failure attribution, adds cost and latency, and violates separation between *finding* resources and *operating* them.

**Search within Analysis:** Rejected. Analysis must remain paper-grounded ([ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md)). Web search, link verification, and repository ranking are external augmentation — not paper interpretation. Merging them into Reader would break the single-responsibility Analysis boundary and duplicate search whenever analysis is reused.

**Planner performs its own search:** Rejected. v1.1 Planner decomposes engineering tasks from analysis ([ADR-0004](ADR-0004-Planning-Strategy.md), [ADR-0005](ADR-0005-Planner-Capability.md)); it is not a resource resolver. Embedding search in Planner would repeat discovery on every plan, mix task decomposition with evidence collection, and prevent audit of resource decisions independent of task structure.

## Consequences

**Positive:**

- **Capability boundary** — Understanding, resource resolution, and engineering strategy remain separate layers with clear ownership
- **Long-term evolution** — Discovery is the first v1.2 Platform Capability layer; Execution Planning, Repository Understanding, and Repository Adaptation attach downstream without re-searching
- **Provider pattern** — External backends plug in behind ports per [infrastructure.md](../architecture/infrastructure.md) governance; internal pipeline stages stay stable
- **Evidence-based decisions** — Every selection traces to collected evidence; unresolved gaps are first-class outputs, not silent omissions
- **Future resource types** — Tiered resource taxonomy (official repo, checkpoint, HuggingFace, Docker, future Zenodo/Papers With Code) extends via adapters without changing the five-stage pipeline
- **Preserves Analysis canonical object** — `PaperReproductionAnalysis` remains the single paper interpretation; Discovery augments with externally verified facts

**Negative:**

- New pipeline stage increases workflow complexity and coordinator logic (mandatory vs optional invocation)
- v1.1 Planner and Coder paths must coexist with Discovery until Execution Planning replaces implicit resource inference
- Discovery backends require adoption review and operational handling (rate limits, partial results, backend degradation)
- Shallow verification does not guarantee runnable repos — Execution may still fail after selection

## Relationship to Other ADRs

- [ADR-0009](ADR-0009-Analysis-Canonical-Artifact.md): Discovery **consumes** `PaperReproductionAnalysis`; it does not replace or mutate the analysis artifact
- [ADR-0010](ADR-0010-Hydra-Configuration.md): Discovery settings (backends, thresholds, invocation triggers) compose via Hydra `conf/` groups — infrastructure only; Discovery agents do not import Hydra
- [ADR-0011](ADR-0011-Pixi-Environment.md): Developer environment supplies Discovery backend dependencies; Pixi is repo infrastructure, not a runtime concern of Discovery logic
- [ADR-0012](ADR-0012-Experiment-Tracking-MLflow.md): Discovery runs and `ResearchResourceDiscovery` snapshots may be logged via `ExperimentTracker` — tracking wraps at composition root; Discovery does not import MLflow

Companion design: [research-resource-discovery.md](../design/research-resource-discovery.md)

## Future Work

Out of scope for this ADR — recorded for downstream architecture only:

| Capability | Direction |
|------------|-----------|
| **Execution Planning** | Consume `PaperReproductionAnalysis` + `ResearchResourceDiscovery`; decide official repo vs fork vs hybrid vs greenfield generation; output Execution Strategy without re-searching |
| **Repository Understanding** | Semantic mapping between selected repo structure and analysis modules (method, evaluation); informs Execution Planning and optional Coder context — read-only, no modification |
| **Repository Adaptation** | Patches, version pins, or forks to align discovered repo with paper requirements — owned by Implementation / patch workflow, not Discovery |

Evolution roadmap:

```text
v1.1  Foundation          Analysis → Planning → Coder → Execution
v1.2  Discovery           Analysis → Discovery → Execution Planning → Execution
v1.3  Repo Understanding  Discovery → Repo Analysis → Repo Understanding → Adaptation
```

Each stage produces a typed artifact. No stage re-parses the PDF for reproduction facts.
