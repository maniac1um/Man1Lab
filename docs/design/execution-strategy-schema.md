# ExecutionStrategy — Canonical Schema Design

**Project:** Man1Lab  
**Phase:** v1.2 — Execution Planning Phase 1  
**Version:** Schema design draft  
**Status:** Design Only — no implementation  
**Audience:** Architects, schema implementers  
**Horizon:** 3–5 years  
**Last updated:** 2026-07-03

Related documents:

- [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) — architectural decision
- [execution-planning.md](execution-planning.md) — capability and boundary design
- [research-resource-discovery-schema.md](research-resource-discovery-schema.md) — upstream Discovery artifact
- [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md) — upstream Analysis artifact
- [ADR-0004](../adr/ADR-0004-Planning-Strategy.md) / [ADR-0005](../adr/ADR-0005-Planner-Capability.md) — downstream Planner capability
- [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) — platform layers

This document defines the **canonical domain object** `ExecutionStrategy` — the Execution Planning layer artifact equivalent to `PaperReproductionAnalysis` in Analysis and `ResearchResourceDiscovery` in Discovery. It specifies schema modules, field semantics, validation rules, and downstream consumption contracts.

**Out of scope:** Python code, Pydantic models, runtime changes, workflow design, API design, prompt design, provider implementation.

---

## Executive Summary

`ExecutionStrategy` is a **long-lived, auditable record** of engineering decisions for one paper reproduction campaign. It is produced once per Execution Planning invocation, consumed by Planner, Implementation, Review, and future Repository capabilities — and never mutates `PaperReproductionAnalysis` or `ResearchResourceDiscovery`.

```text
ExecutionStrategy
├── schema_version
├── metadata
├── input_references
├── strategy
├── resource_bindings
├── reuse_plan
├── adaptation_plan
├── generation_plan
├── risk_assessment
└── provenance
```

`input_references` binds upstream artifacts by identity and content hash — it does not embed analysis or discovery modules.

---

## 1. Purpose

### 1.1 What ExecutionStrategy records

`ExecutionStrategy` records **engineering decisions** — how Man1Lab will attempt reproduction given a committed interpretation of the paper and a committed set of discovered resources.

| Records | Does not record |
|---------|-----------------|
| Strategy posture (reuse, adapt, generate, manual) | Engineering **tasks** |
| Resource bindings by **reference** to discovery candidates | **Repository metadata** (file trees, README text, stars) |
| Adaptation and generation **authorization** | **Candidate rankings** or verification dimensions |
| Risk, confidence, and fallback posture | **Provider evidence** or discovery audit chains |
| Rationale traceable to upstream artifact IDs | Full copies of Analysis or Discovery modules |

ExecutionStrategy is the **third canonical artifact** in the Man1Lab pre-implementation stack:

```text
PaperReproductionAnalysis      ← what is required (paper-grounded)
ResearchResourceDiscovery      ← what resources exist (evidence-grounded)
ExecutionStrategy              ← how reproduction will proceed (decision-grounded)
TaskModel                      ← what tasks to execute (decomposition)
```

### 1.2 Why a separate artifact is required

Merging strategy into Planner output (`TaskModel`) or Discovery output (`ResearchResourceDiscovery`) would:

1. **Hide engineering decisions** inside task wording — no independent strategy audit
2. **Duplicate Discovery** — rankings and evidence would be re-embedded at strategy time
3. **Duplicate Analysis** — scope and method modules would be copied into every plan revision
4. **Block downstream evolution** — Repository Understanding and Adaptation lack a committed strategy input
5. **Prevent partial strategy** — campaigns with degraded discovery could not record explicit risk acceptance

A dedicated `ExecutionStrategy` preserves layer independence and makes engineering intent a first-class, versioned platform object.

---

## 2. Top-Level Structure

### 2.1 Root object

**`ExecutionStrategy`** — root object for one Execution Planning run.

| Module | Purpose |
|--------|---------|
| `schema_version` | Schema evolution identifier |
| `metadata` | Identity and summary of this planning run |
| `input_references` | Immutable bindings to Analysis and Discovery inputs |
| `strategy` | Committed engineering posture and scope |
| `resource_bindings` | Which discovered resources anchor the campaign |
| `reuse_plan` | Reuse commitments and exclusions |
| `adaptation_plan` | Modification authorization and constraints |
| `generation_plan` | Greenfield or partial generation commitments |
| `risk_assessment` | Confidence, risks, fallbacks, accepted gaps |
| `provenance` | How and when the artifact was produced |

### 2.2 Object hierarchy diagram

```text
ExecutionStrategy
│
├── schema_version ........................ evolution identifier
├── metadata .............................. run identity & outcome summary
├── input_references ...................... upstream artifact bindings (read-only links)
│   ├── analysis_reference
│   └── discovery_reference
│
├── strategy .............................. committed engineering posture
├── resource_bindings ..................... candidate ID bindings by role
├── reuse_plan ............................ reuse vs fork vs hybrid decisions
├── adaptation_plan ....................... modification authorization
├── generation_plan ....................... generation scope and modules
├── risk_assessment ....................... confidence, risks, fallbacks
│
└── provenance ............................ timestamps, degradation, decision trace
```

### 2.3 Module dependency flow

```text
input_references (frozen at planning start)
        ↓
strategy (posture committed)
        ↓
resource_bindings (discovery candidate IDs selected for use)
        ↓
reuse_plan ──┬── adaptation_plan ──┬── generation_plan
             │                     │
             └──────────┬──────────┘
                        ↓
                 risk_assessment
                        ↓
                   provenance (finalized)
```

Modules are **logical groupings** on one assembled artifact — not separate runtime files. Workflow design (future document) may populate them incrementally or in one assembly pass.

---

## 3. Module Design

Each module below documents **purpose**, **responsibility**, **why it exists**, and **how downstream capabilities consume it**. Field tables describe semantics only — not JSON payloads or implementation types.

---

### 3.1 `metadata`

#### Purpose

Run-level identity and high-level outcome for `ExecutionStrategy`. Analogous to `ResearchResourceDiscovery.metadata` — summarizes the planning run without duplicating upstream paper metadata.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|-------------------|-------------|
| `strategy_id` | opaque string | Unique ID for this planning run (UUID or deterministic hash) |
| `created_at` | timestamp (ISO 8601) | When Execution Planning completed |
| `status` | enum | `complete`, `partial`, `degraded`, `manual_review`, `aborted` |
| `summary` | string | Human-readable one-line outcome (e.g. "Official repo reuse; checkpoint gap accepted with degraded scope") |
| `reproduction_scope` | enum (snapshot) | Copy of `goal.scope` from analysis at planning time |
| `invocation_reason` | enum | Why planning ran: `discovery_complete`, `discovery_partial`, `user_requested`, `policy_mandatory`, `manual_rerun` |
| `strategy_posture` | enum (snapshot) | Denormalized copy of `strategy.primary_posture` for quick filtering |
| `binding_count` | integer | Number of active resource bindings |
| `blocking_risk_count` | integer | Count of `risk_assessment.blocking_risks` |
| `manual_action_required` | boolean | True when strategy posture is manual or risks require human input |

#### Why it exists

Consumers (MLflow UI, Review, orchestrator) need a **single glance summary** without parsing strategy modules. Status communicates whether Planner may proceed autonomously.

#### Downstream consumption

| Consumer | Uses metadata for |
|----------|-------------------|
| **Planner** | Gate decomposition — `aborted` or `manual_review` may skip or narrow task generation |
| **Review / Report** | Display planning outcome in reproduction audit |
| **Orchestrator** | Branching — partial strategy may trigger user confirmation |
| **MLflow** | Run tags and artifact indexing |

---

### 3.2 `input_references`

#### Purpose

Immutable binding to upstream canonical artifacts. Prevents drift and makes cross-artifact audit possible without embedding upstream content.

#### Responsibility

**`analysis_reference`** — link to input `PaperReproductionAnalysis`:

| Field | Type | Description |
|-------|------|-------------|
| `analysis_schema_version` | string | `PaperReproductionAnalysis.schema_version` at input time |
| `paper_title` | string | Denormalized for display / audit only |
| `arxiv_id` | string | Denormalized; empty if absent |
| `analysis_content_hash` | string | Hash of canonical analysis serialization — detects analysis change between runs |
| `reproduction_scope` | string | Snapshot of `goal.scope` |
| `analysis_gap_categories` | list | Gap category values at planning time — not full gap objects |

**`discovery_reference`** — link to input `ResearchResourceDiscovery`:

| Field | Type | Description |
|-------|------|-------------|
| `discovery_schema_version` | string | `ResearchResourceDiscovery.schema_version` at input time |
| `discovery_id` | string | `metadata.discovery_id` of input artifact |
| `discovery_content_hash` | string | Hash of canonical discovery serialization |
| `discovery_status` | enum (snapshot) | `complete`, `partial`, `failed`, `skipped` at input time |
| `selection_ids_used` | list | `selection_id` values referenced by `resource_bindings` |
| `unresolved_discovery_gap_count` | integer | Snapshot of unresolved gaps at planning time |

#### Why it exists

Execution Planning must prove **which upstream artifacts** informed decisions. Hash binding detects stale strategy when Analysis or Discovery is rerun. Denormalized display fields avoid loading upstream artifacts for UI only.

#### Downstream consumption

| Consumer | Uses input_references for |
|----------|---------------------------|
| **Review** | Three-artifact lineage: Analysis → Discovery → Strategy |
| **Validation** | Verify referenced `candidate_id` values exist in linked discovery artifact |
| **Orchestrator** | Invalidate strategy when upstream hash changes |

**Invariant:** `input_references` never contains full `goal`, `method`, `candidates`, `evidence`, or `verification` modules.

---

### 3.3 `strategy`

#### Purpose

The **committed engineering posture** — the single authoritative answer to how reproduction will proceed.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|-------------------|-------------|
| `primary_posture` | enum | `official_repository`, `community_fork`, `hybrid`, `greenfield`, `manual` |
| `scope_commitment` | enum | `full_reproduction`, `partial_reproduction`, `narrowed_scope`, `eval_only`, `inference_only` |
| `scope_narrowing_rationale` | string \| null | Required when `scope_commitment` is narrowed — why reduced scope is acceptable |
| `rationale` | string | Primary human-readable strategy explanation |
| `deciding_factors` | list of strings | Named factors (e.g. `discovery_selection_official`, `verification_pass`, `unresolved_checkpoint`) |
| `confidence` | float (0.0–1.0) | Overall strategy confidence |
| `alternative_postures_rejected` | list of **RejectedPosture** | Postures considered and why rejected (audit) |

**RejectedPosture** (nested):

| Field | Description |
|-------|-------------|
| `posture` | Enum value that was not selected |
| `rejection_reason` | Short explanation |
| `related_discovery_gap_id` | Optional reference to discovery gap that motivated rejection |

#### Why it exists

Downstream capabilities need one **unambiguous posture** before tasks or code changes. Separating posture from bindings and plans keeps strategy readable independent of resource detail.

#### Downstream consumption

| Consumer | Uses strategy for |
|----------|-------------------|
| **Planner** | Task template selection — official-repo path vs greenfield decomposition |
| **Implementation** | Generation vs reuse mode at workspace level |
| **Repository Understanding** | Whether repo-based understanding is in scope |
| **Review** | Strategy disclosure in reproduction report |

---

### 3.4 `resource_bindings`

#### Purpose

Record **which discovered resources will be used** and in what **role** — by reference to Discovery `candidate_id` values only.

#### Responsibility

| Field | Type | Description |
|-------|------|-------------|
| `bindings` | list of **ResourceBinding** | Active bindings for this campaign |
| `anchor_binding_id` | string \| null | ID of binding that anchors the workspace (typically code repository) |
| `combination_rationale` | string | Why this resource set forms a coherent reproduction path |

**ResourceBinding** (nested):

| Field | Type | Description |
|-------|------|-------------|
| `binding_id` | string | Unique within `ExecutionStrategy` |
| `candidate_id` | string | **Reference** to `ResearchResourceDiscovery.candidate_resources.candidates` |
| `selection_id` | string \| null | **Reference** to discovery `selection.selection_id` if binding follows a committed selection |
| `resource_need_id` | string \| null | **Reference** to discovery resource need satisfied |
| `role` | enum | `primary_repository`, `fallback_repository`, `checkpoint`, `dataset`, `configuration`, `documentation`, `project_home`, `supporting_asset` |
| `usage_intent` | enum | `execute_directly`, `extract_assets_from`, `reference_only`, `fallback_if_primary_fails` |
| `binding_rationale` | string | Why this candidate was bound for this role |
| `overrides_discovery_selection` | boolean | True if strategy binds a non-primary discovery selection — requires `override_rationale` |
| `override_rationale` | string \| null | Required when override is true |

#### Why it exists

Discovery answers *what exists and what was selected*. ExecutionStrategy answers *what we will actually use* — which may align with selection or explicitly override with recorded rationale. Bindings use **IDs only** — URLs, titles, and verification status remain in Discovery.

#### Downstream consumption

| Consumer | Uses resource_bindings for |
|----------|----------------------------|
| **Planner** | Clone/fetch tasks target bound `candidate_id` |
| **Execution** | Resolve URLs from Discovery artifact via ID lookup |
| **Repository Understanding** | Identify anchor repository binding |
| **Review** | Resource commitment audit trail |

**Invariant:** No candidate rankings, verification records, or evidence payloads appear in this module.

---

### 3.5 `reuse_plan`

#### Purpose

Commit to **how much existing engineering artifact will be reused unchanged** — the reuse dimension of strategy.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|------|-------------|
| `reuse_mode` | enum | `as_is`, `fork_based`, `hybrid_components`, `not_applicable` |
| `primary_reuse_binding_id` | string \| null | Reference to `resource_bindings.binding_id` for main reuse target |
| `components_to_reuse` | list of **ReuseComponent** | Resources or logical components committed to reuse |
| `components_excluded` | list of **ExcludedComponent** | Resources discovered but explicitly not reused |
| `reuse_assumptions` | list of strings | Assumptions reuse depends on (e.g. "official repo train script matches paper method") |
| `reuse_limitations` | list of strings | Known limitations accepted with reuse |

**ReuseComponent** (nested):

| Field | Description |
|-------|-------------|
| `binding_id` | Reference to `resource_bindings.binding_id` |
| `component_label` | Logical label: `training_code`, `eval_harness`, `weights`, `config` |
| `reuse_extent` | `full`, `partial`, `entrypoint_only` |

**ExcludedComponent** (nested):

| Field | Description |
|-------|-------------|
| `candidate_id` | Discovery candidate reference |
| `exclusion_reason` | Why not reused despite discovery |

#### Why it exists

Implementation must not infer reuse from task text. Coder needs explicit **reuse extent** per component before modifying or generating code.

#### Downstream consumption

| Consumer | Uses reuse_plan for |
|----------|---------------------|
| **Planner** | Skip clone tasks when `not_applicable`; order fetch-before-generate |
| **Implementation** | Workspace layout — preserve upstream structure vs greenfield |
| **Repository Adaptation** (future) | Baseline for what must remain untouched |

---

### 3.6 `adaptation_plan`

#### Purpose

Authorize **whether and how** discovered resources may be modified downstream — without performing modification in Execution Planning.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|------|-------------|
| `adaptation_required` | boolean | Whether Repository Adaptation (future) is expected |
| `adaptation_scope` | enum | `none`, `minimal`, `moderate`, `extensive` |
| `authorized_modifications` | list of **AuthorizedModification** | Modification classes permitted |
| `adaptation_constraints` | list of strings | What must **not** change (e.g. model architecture, eval protocol) |
| `adaptation_triggers` | list of **AdaptationTrigger** | Why adaptation is needed |
| `adaptation_deferred` | boolean | True when adaptation scope is unknown — Repository Understanding required first |

**AuthorizedModification** (nested):

| Field | Description |
|-------|-------------|
| `modification_class` | Conceptual class: `dependency_pin`, `config_patch`, `script_patch`, `fork`, `framework_port` |
| `target_binding_id` | Optional binding reference |
| `authorization_level` | `planner_task`, `coder_discretion`, `human_approval_required` |

**AdaptationTrigger** (nested):

| Field | Description |
|-------|-------------|
| `trigger_type` | `discovery_gap`, `verification_partial`, `scope_mismatch`, `framework_version` |
| `description` | Human-readable trigger |
| `related_discovery_gap_id` | Optional discovery gap reference |

#### Why it exists

Adaptation is a **strategy decision**, not a Discovery fact. Separating authorization from execution prevents Coder from expanding modification scope silently.

#### Downstream consumption

| Consumer | Uses adaptation_plan for |
|----------|--------------------------|
| **Planner** | Emit adaptation tasks only when `adaptation_required` |
| **Repository Adaptation** (future) | Scope ceiling for patches and forks |
| **Implementation** | Hard stops when modification class is not authorized |
| **Review** | Disclosure of intended modifications |

---

### 3.7 `generation_plan`

#### Purpose

Commit to **greenfield or partial code generation** when reuse and adaptation are insufficient.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|------|-------------|
| `generation_required` | boolean | Whether Implementation must generate new artifacts |
| `generation_scope` | enum | `none`, `full_codebase`, `missing_modules`, `config_and_scripts`, `eval_harness_only`, `documentation_only` |
| `modules_to_generate` | list of **GenerationTarget** | Analysis-aligned generation targets |
| `generation_constraints` | list of strings | Constraints on generated code (framework, interfaces, metrics) |
| `generation_rationale` | string | Why generation was chosen over reuse |
| `reuse_fallback_after_generation` | boolean | Whether discovered resources remain fallbacks after partial generation |

**GenerationTarget** (nested):

| Field | Description |
|-------|-------------|
| `analysis_module` | Conceptual reference: `method`, `evaluation`, `resources`, `goal` — not a copy of module content |
| `generation_intent` | `implement_from_paper`, `stub_for_integration`, `replace_missing_upstream` |
| `priority` | `blocking`, `degraded`, `optional` |

#### Why it exists

Greenfield reproduction must be an **explicit strategy commitment**, not an emergent Planner default when Discovery fails. Partial generation scopes prevent full rewrite when only one module is missing.

#### Downstream consumption

| Consumer | Uses generation_plan for |
|----------|--------------------------|
| **Planner** | Generate tasks vs clone tasks ratio |
| **Implementation** | Coder mode selection — scaffold vs patch vs full generation |
| **Review** | Disclosure of synthetic vs reused artifacts |

**Invariant:** `generation_plan` references analysis **module names** only — never duplicates `method`, `evaluation`, or `resources` content.

---

### 3.8 `risk_assessment`

#### Purpose

Record **confidence, risks, fallbacks, and accepted gaps** so downstream capabilities operate under explicit risk posture.

#### Responsibility

| Field | Type (conceptual) | Description |
|-------|------|-------------|
| `overall_confidence` | float (0.0–1.0) | Campaign-level confidence after risk adjustment |
| `blocking_risks` | list of **RiskRecord** | Risks that block full reproduction scope |
| `degraded_risks` | list of **RiskRecord** | Risks accepted with narrowed or partial scope |
| `informational_risks` | list of **RiskRecord** | Risks recorded for audit only |
| `fallback_strategies` | list of **FallbackStrategy** | Ordered fallback if primary strategy fails |
| `accepted_discovery_gap_ids` | list of strings | Discovery gap IDs explicitly accepted — references only |
| `manual_actions_required` | list of **ManualAction** | Human steps required before Implementation |
| `abort_conditions` | list of strings | Conditions under which campaign should stop |

**RiskRecord** (nested):

| Field | Description |
|-------|-------------|
| `risk_id` | Unique within artifact |
| `severity` | `blocking`, `degraded`, `informational` |
| `category` | `unresolved_resource`, `verification_low_confidence`, `license`, `scope_mismatch`, `ambiguous_official`, `other` |
| `description` | Human-readable risk statement |
| `mitigation` | How strategy mitigates or accepts the risk |
| `related_binding_id` | Optional resource binding reference |
| `related_discovery_gap_id` | Optional discovery gap reference |

**FallbackStrategy** (nested):

| Field | Description |
|-------|-------------|
| `fallback_order` | Integer priority |
| `posture` | Alternative `strategy.primary_posture` to attempt |
| `trigger_condition` | When to activate |
| `fallback_binding_ids` | Optional alternate bindings |

**ManualAction** (nested):

| Field | Description |
|-------|-------------|
| `action_id` | Unique within artifact |
| `description` | What the human must do |
| `blocks_planner` | Whether Planner must wait |

#### Why it exists

Partial Discovery and low verification confidence are normal. Risk assessment makes **explicit acceptance** of degradation — preventing silent failure in Implementation or Execution.

#### Downstream consumption

| Consumer | Uses risk_assessment for |
|----------|--------------------------|
| **Planner** | Task gating, fallback task chains |
| **Orchestrator** | User confirmation when `manual_actions_required` |
| **Review** | Risk section in reproduction report |
| **Execution** | Abort when `abort_conditions` met |

---

### 3.9 `provenance`

#### Purpose

Traceability for how `ExecutionStrategy` was produced — analogous to `ResearchResourceDiscovery.provenance`.

#### Responsibility

| Field | Type | Description |
|-------|------|-------------|
| `planning_run_id` | string | Correlates with workflow / MLflow nested run |
| `pipeline_version` | string | Man1Lab version that produced this artifact |
| `stage_timestamps` | map | Stage name → completion timestamp (workflow-defined in future doc) |
| `degradation_notes` | list of strings | Partial inputs, policy limits, planning failures recovered |
| `configuration_fingerprint` | string | Hash of planning-relevant settings — not full config dump |
| `decision_trace` | list of **DecisionRecord** | Optional structured audit of major decisions |
| `rerun_of` | string \| null | Prior `strategy_id` if this is a replan |

**DecisionRecord** (nested):

| Field | Description |
|-------|-------------|
| `decision_id` | Unique within trace |
| `decision_category` | `resource`, `reuse`, `adaptation`, `generation`, `risk` |
| `summary` | What was decided |
| `inputs_consulted` | List of upstream reference keys (e.g. `discovery.selections[0]`) — **references only** |
| `timestamp` | When recorded |

#### Why it exists

Three-artifact audits require knowing **how** strategy was derived. Decision trace supports benchmark analysis and regression comparison across Man1Lab versions.

#### Downstream consumption

| Consumer | Uses provenance for |
|----------|---------------------|
| **MLflow** | Nested run correlation |
| **Review** | Planning process audit |
| **Debugging** | Compare strategy across replans |

**Invariant:** `provenance` does not store Discovery provider records or evidence — those remain in `ResearchResourceDiscovery.provenance`.

---

### 3.10 `schema_version`

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | ExecutionStrategy schema version (e.g. `"1.0"`) — independent of analysis and discovery schema versions |

Future schema additions use optional fields or extension slots; breaking changes increment major version per platform convention.

---

## 4. Relationship to Discovery

### 4.1 Complementary questions

| Artifact | Question |
|----------|----------|
| **ResearchResourceDiscovery** | What exists? |
| **ExecutionStrategy** | What we will use? |

Discovery records the **factual landscape** — candidates, evidence, verification, rankings, selections, and gaps. ExecutionStrategy records **engineering commitment** — bindings, posture, and plans that use a subset of discovery facts by reference.

### 4.2 Reference model

```text
ResearchResourceDiscovery                    ExecutionStrategy
─────────────────────────                    ───────────────────
candidate_resources.candidates[].candidate_id ──► resource_bindings.candidate_id
selection.selections[].selection_id          ──► resource_bindings.selection_id
discovery_gaps.gaps[].gap_id                 ──► risk_assessment.accepted_discovery_gap_ids
ranking.rank_lists                           ──► (not copied)
verification.records                         ──► (not copied)
evidence.records                             ──► (not copied)
```

Execution Planning **reads** discovery verification and ranking outcomes to **inform** strategy — it does **not** persist them. If audit requires verification status at strategy time, record a **snapshot label** in `deciding_factors` or `decision_trace`, not a copy of verification modules.

### 4.3 What ExecutionStrategy never stores

| Discovery content | Why excluded |
|-------------------|--------------|
| Candidate rankings | Factual ordering — belongs in Discovery |
| Verification records | Factual viability — belongs in Discovery |
| Provider evidence | External observation — belongs in Discovery |
| Full candidate objects | Duplication — use `candidate_id` reference |
| Evidence chains | Audit trail — belongs in Discovery |

### 4.4 Override semantics

When `resource_bindings.overrides_discovery_selection` is true, ExecutionStrategy must record `override_rationale`. Discovery artifact remains unchanged — the override is a **planning decision**, not a discovery correction.

---

## 5. Relationship to Planner

### 5.1 Consumption contract

Planner **consumes** `ExecutionStrategy` as primary planning input on the target path.

```text
ExecutionStrategy
        ↓
Planner
        ↓
TaskModel
```

### 5.2 Responsibility split

| ExecutionStrategy | TaskModel |
|-------------------|-----------|
| Engineering posture | Ordered task list |
| Resource bindings by ID | Concrete task targets and file paths |
| Reuse / adapt / generate intent | Per-task instructions |
| Risk and fallback posture | Task dependencies and retries |
| Confidence and rationale | Task estimates and assignments |

Planner **expands** engineering decisions into executable tasks — it does not re-decide strategy posture except when `metadata.status` is `aborted` or `manual_review` blocks automation.

### 5.3 What ExecutionStrategy never contains

| Excluded | Owner |
|----------|-------|
| Task IDs | TaskModel |
| Task descriptions | TaskModel |
| `depends_on` graphs | TaskModel |
| Agent assignments | TaskModel |
| File paths in workspace | TaskModel / Implementation |

**Invariant:** `ExecutionStrategy` and `TaskModel` remain **independent canonical artifacts**. Planner may reference `strategy_id` in TaskModel provenance (future) — but tasks are not embedded in strategy.

---

## 6. Relationship to Implementation

### 6.1 Consumption contract

Implementation (Coder) **consumes** `ExecutionStrategy` alongside `TaskModel`.

| Module | Implementation uses for |
|--------|-------------------------|
| `strategy.primary_posture` | Workspace initialization pattern |
| `reuse_plan` | Preserve vs replace upstream structure |
| `adaptation_plan` | Modification ceiling |
| `generation_plan` | Coder generation mode |
| `resource_bindings` | Resolve resources via Discovery lookup |
| `risk_assessment` | Hard stops and degraded behavior |

### 6.2 No inference rule

Implementation **never infers**:

| Decision | Source |
|----------|--------|
| Reuse vs regenerate | `reuse_plan` + `strategy.primary_posture` |
| Whether to patch | `adaptation_plan.adaptation_required` |
| What to generate | `generation_plan.modules_to_generate` |
| Which repo is primary | `resource_bindings.anchor_binding_id` |

If task text conflicts with `ExecutionStrategy`, **strategy wins** — task generation is considered defective.

### 6.3 Discovery lookup pattern

Implementation resolves `candidate_id` → URL and metadata by loading the linked `ResearchResourceDiscovery` artifact identified in `input_references.discovery_reference` — not by embedding URLs in `ExecutionStrategy`.

---

## 7. Artifact Principles

| Principle | Application to ExecutionStrategy |
|-----------|----------------------------------|
| **Canonical** | Single authoritative engineering decision record per planning run |
| **Immutable** | Produced once; revisions create new `strategy_id` with `provenance.rerun_of` |
| **Versioned** | `schema_version` enables 3–5 year evolution |
| **Auditable** | `rationale`, `deciding_factors`, `decision_trace`, and `input_references` hashes |
| **Strategy-only** | No tasks, no code, no repository file metadata |
| **Reference-not-copy** | Upstream and discovery content linked by ID and hash |
| **No Provider Awareness** | No discovery provider names in strategy modules — only artifact references |
| **No Infrastructure Awareness** | No Hydra keys, Pixi specs, or MLflow run IDs in domain modules (provenance run correlation excepted) |
| **Partial-tolerant** | `metadata.status=partial` is valid when Discovery is partial but strategy is committed |
| **Independent from TaskModel** | Strategy and tasks version and evolve separately |

---

## 8. Future Evolution

### 8.1 Downstream capabilities

| Capability | Relationship to ExecutionStrategy |
|------------|-----------------------------------|
| **Repository Understanding** | Consumes `resource_bindings.anchor_binding_id` + posture — maps repo structure to analysis modules **after** strategy commits |
| **Repository Adaptation** | Consumes `adaptation_plan` authorization — executes modifications, does not expand scope |
| **Environment Preparation** | Consumes posture + bindings — resolves runtime after strategy and tasks exist |

```text
ExecutionStrategy
    ↓
Repository Understanding    (repo-based postures only)
    ↓
Repository Adaptation       (when adaptation_plan.adaptation_required)
    ↓
Environment Preparation
    ↓
Implementation → Execution
```

### 8.2 Execution modes

Strategy posture enums may gain additional values (e.g. container-first, notebook-demo-only) via **minor schema bump** — without changing Discovery schema or TaskModel structure.

### 8.3 Planner migration

| Phase | Behavior |
|-------|----------|
| **v1.1 compatibility** | Planner may still run from Analysis only — no `ExecutionStrategy` produced |
| **v1.2 target** | Planner requires `ExecutionStrategy` when Discovery ran |
| **v1.3** | Planner provenance records `strategy_id`; implicit strategy in Planner removed |

### 8.4 Schema evolution policy

| Change type | Version bump |
|-------------|--------------|
| New optional field | Patch (1.0 → 1.1) |
| New enum value for posture or role | Minor |
| Breaking field rename or semantic change | Major |

### 8.5 Extension points

| Location | Purpose |
|----------|---------|
| `strategy.deciding_factors` | New decision dimensions before first-class modules |
| `risk_assessment` custom categories | Emerging risk types |
| `provenance.decision_trace` | Richer audit without schema redesign |

### 8.6 Next documents

| Document | Scope |
|----------|-------|
| **Execution Planning workflow** | Stage ordering, partial semantics, coordinator integration |
| **Pydantic models + validation** | Implementation of this schema |
| **Planner migration note** | TaskModel provenance and input contract change |

---

## 9. Validation Rules

Conceptual rules for implementers. No runtime code in this phase.

### 9.1 Identity and referential integrity

| Rule | Description |
|------|-------------|
| **ES-01** | Every `binding_id` is unique within the artifact |
| **ES-02** | Every `resource_bindings.candidate_id` is non-empty when binding is active |
| **ES-03** | Every `anchor_binding_id` references an existing `binding_id` |
| **ES-04** | Every `selection_id` in bindings references a selection in linked Discovery artifact (workflow validation) |
| **ES-05** | Every `accepted_discovery_gap_id` references a gap in linked Discovery artifact |
| **ES-06** | `input_references.discovery_content_hash` and `analysis_content_hash` are non-empty on `complete` status |

### 9.2 Semantic rules

| Rule | Description |
|------|-------------|
| **ES-10** | `strategy.primary_posture=greenfield` implies `generation_plan.generation_required=true` |
| **ES-11** | `strategy.primary_posture=manual` implies `risk_assessment.manual_actions_required` is non-empty |
| **ES-12** | `resource_bindings.overrides_discovery_selection=true` requires non-empty `override_rationale` |
| **ES-13** | `adaptation_plan.adaptation_scope=none` implies `adaptation_plan.adaptation_required=false` |
| **ES-14** | `metadata.status=aborted` requires at least one `blocking_risks` entry or explicit abort in `strategy.rationale` |
| **ES-15** | `scope_commitment=narrowed_scope` requires non-empty `scope_narrowing_rationale` |
| **ES-16** | No task IDs, file paths, or agent names anywhere in ExecutionStrategy |
| **ES-17** | No duplicate of `PaperReproductionAnalysis` modules (`goal`, `method`, `evaluation`, `resources`) |
| **ES-18** | No duplicate of Discovery modules (`evidence`, `verification`, `ranking`, full `candidates`) |

### 9.3 Coherence rules

| Rule | Description |
|------|-------------|
| **ES-20** | `reuse_plan.reuse_mode=not_applicable` only valid when `strategy.primary_posture=greenfield` or `manual` |
| **ES-21** | `generation_plan.generation_scope=none` implies `generation_plan.generation_required=false` |
| **ES-22** | At least one `resource_bindings` entry when `metadata.status=complete` and posture is not `manual` |
| **ES-23** | `overall_confidence` ≤ `strategy.confidence` unless risk module documents adjustment rationale in `degradation_notes` |

Violations indicate planning pipeline bug or schema misuse — not end-user paper errors.

---

## 10. Implementation Handoff

The next phase translates this document into:

1. Pydantic (or equivalent) models mirroring §2 hierarchy
2. Validation enforcing §9 rules
3. Execution Planning workflow (separate design document)
4. Snapshot serialization to workflow history and MLflow artifacts
5. Planner input contract update

Implementers should **not** revisit capability boundaries in [ADR-0014](../adr/ADR-0014-Execution-Planning-Capability.md) and [execution-planning.md](execution-planning.md) unless schema validation reveals a gap — in which case update this document first.

---

## Document Maintenance

| Event | Action |
|-------|--------|
| Schema implementation starts | Pin `schema_version`; cross-link workflow design doc |
| New strategy posture added | Update §3.3; minor schema bump |
| Planner migration completes | Update §8.3; amend ADR-0005 scope note |
| Execution Planning workflow designed | Cross-link companion document |

**Status:** Design Only — Phase 1 schema complete. No code, runtime, or workflow changes.

---

# ExecutionStrategy Schema Audit

Audit performed after drafting this schema design. Documentation only — no code, workflow, or implementation.

### Artifact boundary

| Check | Result |
|-------|--------|
| ExecutionStrategy is third canonical pre-implementation artifact | ✅ Pass |
| Records engineering decisions only | ✅ Pass |
| No tasks, repository metadata, or provider evidence | ✅ Pass |
| Independent from TaskModel | ✅ Pass |

### Module completeness

| Module | Documented | Downstream consumption |
|--------|------------|------------------------|
| `metadata` | ✅ | ✅ |
| `input_references` | ✅ | ✅ |
| `strategy` | ✅ | ✅ |
| `resource_bindings` | ✅ | ✅ |
| `reuse_plan` | ✅ | ✅ |
| `adaptation_plan` | ✅ | ✅ |
| `generation_plan` | ✅ | ✅ |
| `risk_assessment` | ✅ | ✅ |
| `provenance` | ✅ | ✅ |
| `schema_version` | ✅ | ✅ |

### Duplication check

| Upstream content | Duplicated in ExecutionStrategy? |
|------------------|-------------------------------|
| `PaperReproductionAnalysis` modules | ❌ No — `input_references` + module name refs only |
| `ResearchResourceDiscovery` candidates (full) | ❌ No — `candidate_id` references only |
| Discovery rankings | ❌ No |
| Discovery verification records | ❌ No |
| Discovery evidence | ❌ No |
| TaskModel tasks | ❌ No |

### Relationship to Analysis

| Check | Result |
|-------|--------|
| Consumes Analysis via `input_references` read-only | ✅ Pass |
| Does not embed `goal`, `method`, `evaluation`, `resources` | ✅ Pass |
| `analysis_content_hash` binding documented | ✅ Pass |
| Aligns with [ADR-0009](../adr/ADR-0009-Analysis-Canonical-Artifact.md) | ✅ Pass |

### Relationship to Discovery

| Check | Result |
|-------|--------|
| "What exists" vs "what we will use" distinction clear | ✅ Pass |
| Bindings use `candidate_id` and `selection_id` references | ✅ Pass |
| Rankings, verification, evidence excluded | ✅ Pass |
| Override semantics preserve Discovery immutability | ✅ Pass |
| Aligns with [research-resource-discovery-schema.md](research-resource-discovery-schema.md) | ✅ Pass |

### Relationship to Planner

| Check | Result |
|-------|--------|
| Planner consumes ExecutionStrategy | ✅ Pass |
| Task decomposition remains Planner responsibility | ✅ Pass |
| No task content in schema | ✅ Pass |
| v1.1 compatibility path acknowledged | ✅ Pass |

### Future extensibility

| Check | Result |
|-------|--------|
| Repository Understanding attachment point defined | ✅ Pass |
| Repository Adaptation consumes `adaptation_plan` | ✅ Pass |
| Execution mode extension via minor version bump | ✅ Pass |
| `decision_trace` and extension points for evolution | ✅ Pass |
| Validation rules (§9) ready for implementers | ✅ Pass |

### Potential schema risks

| Risk | Assessment |
|------|------------|
| `candidate_id` validation requires Discovery artifact co-load | ⚠️ Workflow must pass linked artifacts — validation rule ES-04 is cross-artifact |
| Posture enum may grow faster than planned | ✅ Mitigated — minor version bump policy in §8.4 |
| `hybrid` posture spans reuse + generation — module coherence | ⚠️ ES-20/ES-21 coherence rules; implementers must validate cross-module consistency |
| Partial Discovery with `complete` strategy status | ⚠️ Explicitly allowed — `risk_assessment.accepted_discovery_gap_ids` required; workflow design must define gates |
| Denormalized fields in `metadata` drift from `strategy` | ✅ Mitigated — snapshot fields documented as denormalized for indexing only |
| v1.1 Planner path without ExecutionStrategy | ⚠️ Transitional — documented in §8.3; orchestrator must handle missing artifact |

---

## Verdict

**Ready for Workflow Design**

`ExecutionStrategy` is defined as the third canonical artifact of Man1Lab with complete module design, upstream reference model, downstream consumption contracts, validation rules, and explicit non-duplication boundaries against Analysis, Discovery, and TaskModel. Workflow design, implementation, and code remain out of scope for this document.
