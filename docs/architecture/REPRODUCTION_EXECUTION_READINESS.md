# Reproduction Execution Readiness Architecture

**Target:** Man1Lab v1.3.0
**Status:** Implemented for the bounded v1.3.0 release contract; arbitrary-paper reproduction remains unsupported
**Audience:** Discovery, Planning, Materialization, Execution, and Application implementers

This document defines the next phase required to turn the existing one-command orchestration into a controlled one-command paper reproduction capability. It extends [EXECUTION_MATERIALIZATION.md](EXECUTION_MATERIALIZATION.md) without redesigning Planning, Execution Engine, Runtime, `ExecutionStore`, or `LocalExecutor`.

---

## 1. Goal and Current Gap

The current pipeline is structurally connected:

```text
paper.pdf
  → Analysis
  → Discovery
  → Planning
  → Materialization
  → READY gate
  → Execution
  → Report
```

However, ordinary Planning graphs may contain preparation stages for which Materialization has no safe executable contract:

- repository preparation;
- dataset preparation;
- checkpoint preparation;
- configuration preparation.

This is not primarily a failure of Planning strategy quality. Planning can correctly decide that a repository, dataset, checkpoint, or configuration is required. The missing information is **execution evidence**: an exact source, revision, destination, integrity rule, preparation method, and downstream path contract.

The next phase must make the following flow reliable for a bounded set of repositories and assets:

```text
Planning decision
  + verified execution evidence
  + approved workspace policy
        ↓
complete materialized ExecutionGraph
        ↓
one ExecutionRun
        ↓
inspectable preparation receipts and workload artifacts
```

The system must continue to stop at `BLOCKED` or `UNSUPPORTED` when evidence is ambiguous. One-command orchestration does not imply speculative execution.

---

## 2. Architecture Decisions

### 2.1 Planning remains declarative

Planning owns:

- strategy posture;
- selected resource bindings;
- required stages and dependency order;
- reuse, adaptation, and generation decisions;
- rationale and risks.

Planning does not own URLs, local paths, shell commands, credentials, download clients, archive extraction, or checksums unless those values already exist as referenced evidence. Existing `ExecutionStrategy` and abstract `ExecutionGraph` remain valid.

### 2.2 Discovery owns factual execution evidence

Discovery providers collect and verify facts about selected resources. A new typed projection, `ExecutionEvidenceBundle`, is produced from existing discovery candidates, evidence records, selections, and research assets.

The bundle is a canonical downstream view; it does not replace `ResearchResourceDiscovery` and does not contain executable commands.

### 2.3 Materialization owns executable preparation instructions

Materialization combines:

- Planning intent and bindings;
- typed execution evidence;
- workspace policy and backend capabilities;
- versioned preparation templates.

It produces immutable `ExecutableTaskSpec` values for preparation and workload nodes. It does not perform clone, download, extraction, configuration writing, or process execution.

### 2.4 Future paths are explicit, not treated as missing

Repository files, datasets, checkpoints, and generated configurations may not exist before execution. A local existence check alone therefore cannot define readiness.

Materialization introduces a typed resolved-reference availability model:

| Availability | Meaning |
|---|---|
| `PRESENT` | The reference already exists in the approved workspace and has been verified locally |
| `WILL_BE_PRODUCED` | An upstream materialized task deterministically produces the reference |
| `EXTERNAL` | The reference remains external and is read through an explicitly supported protocol |
| `UNRESOLVED` | No unique safe reference is available; readiness must be blocked |

A `WILL_BE_PRODUCED` reference must name its producer node and required output. The readiness validator accepts it only when the producer is an ancestor in the graph and declares the same path or preparation receipt.

This allows a training entrypoint verified from a repository manifest to be materialized before the repository is cloned, while preserving a single immutable graph and a single `ExecutionRun`.

### 2.5 Preparation stages produce receipts

Every preparation stage produces an inspectable JSON receipt in addition to its workspace resource:

| Stage | Workspace resource | Required receipt |
|---|---|---|
| Repository | checked-out directory | `repository_receipt.json` |
| Dataset | prepared dataset path | `dataset_receipt.json` |
| Checkpoint | checkpoint file/directory | `checkpoint_receipt.json` |
| Configuration | concrete configuration file | `configuration_receipt.json` |

Receipts contain source identity, resolved revision, target path, integrity result, tool/template version, timestamps, and redacted provenance. They do not contain credentials.

Receipts solve the current directory-artifact limitation: `LocalExecutor` can continue collecting files while prepared directories remain workspace resources referenced by their receipts.

---

## 3. Canonical Evidence Model

Add an additive canonical model family under `models/execution_evidence.py`.

### 3.1 ExecutionEvidenceBundle

Required fields:

- schema version;
- bundle ID and creation time;
- source analysis/discovery IDs and fingerprints;
- one evidence descriptor per selected execution resource;
- repository manifest evidence;
- unresolved and conflicting evidence issues;
- provenance back to candidate, evidence, selection, binding, and asset IDs.

The bundle must be deterministic for the same canonical Discovery artifact. Secret values are forbidden; only approved secret-reference names may appear.

### 3.2 RepositoryExecutionEvidence

Required fields:

- canonical repository URI;
- VCS type;
- immutable revision when available, otherwise an explicitly recorded movable reference;
- destination workspace-relative path;
- repository manifest or verified file index;
- training, evaluation, and comparison entrypoint candidates;
- requirements/environment descriptor locations;
- configuration locations;
- provenance and confidence;
- authentication reference, never authentication value.

`READY` requires exactly one supported repository source and a unique selected entrypoint for each required workload stage. A branch name without a resolved commit is allowed only as a warning under an explicit reproducibility policy; strict mode blocks it.

### 3.3 DatasetExecutionEvidence

Required fields:

- source kind: prepared workspace, HTTPS artifact, supported dataset registry, or repository-contained;
- canonical locator and optional revision;
- destination workspace-relative path;
- archive format and extraction root when applicable;
- checksum and algorithm when available;
- expected files or manifest;
- license/access requirements;
- authentication reference;
- provenance and confidence.

Unknown license acceptance, interactive authentication, ambiguous archive layout, or unsupported protocol blocks automatic execution.

### 3.4 CheckpointExecutionEvidence

Required fields:

- canonical locator and source kind;
- model/revision identity;
- destination path;
- file name or manifest;
- checksum/size when available;
- format and compatibility facts;
- authentication reference;
- provenance and confidence.

Materialization must not select between multiple checkpoint candidates. Selection remains a Planning decision.

### 3.5 ConfigurationExecutionEvidence

Supported modes:

- `EXISTING_FILE`: reuse a verified repository or workspace configuration;
- `COPY_TEMPLATE`: copy a verified template without semantic changes;
- `DETERMINISTIC_RENDER`: render a typed value map into a supported configuration format;
- `PATCH_DECLARATION`: apply a Planning-approved, typed patch to a known base configuration.

Required fields include base/template reference, destination path, format, typed values or patch declaration, and provenance. Free-form AI configuration generation is outside this phase.

---

## 4. Components and Ownership

### ExecutionEvidenceProjector

- **Owner:** Discovery capability.
- **Input:** `ResearchResourceDiscovery` and its canonical evidence/selection artifacts.
- **Output:** `ExecutionEvidenceBundle`.
- **Responsibility:** Normalize verified facts into typed execution evidence and report conflicts.
- **Forbidden:** Select a different resource, generate commands, access Runtime, or perform preparation.

### RepositoryManifestProvider

- **Owner:** Discovery provider layer.
- **Input:** Selected repository candidate and provider policy.
- **Output:** Verified repository file/entrypoint manifest with revision provenance.
- **Responsibility:** Inspect provider metadata or repository contents without mutating the execution workspace.
- **Forbidden:** Clone into the Runtime workspace or claim that unobserved files exist.

Provider network access follows existing Discovery policy, caching, timeout, and evidence rules. Materialization must never initiate this access.

### PreparationTemplateRegistry

- **Owner:** Materialization.
- **Input:** stage type, evidence descriptor, backend capability set, and workspace policy.
- **Output:** one versioned preparation template or an `UNSUPPORTED` diagnostic.
- **Responsibility:** Select deterministic repository/dataset/checkpoint/configuration preparation behavior.
- **Forbidden:** fallback guessing, resource selection, network access, or execution.

It may be implemented as an extension of the existing `TaskTemplateRegistry`; a second competing registry is not required.

### PreparationTaskFactory

- **Owner:** Materialization.
- **Input:** graph node, selected template, evidence descriptor, resolved references.
- **Output:** `ExecutableTaskSpec` and declared receipt path.
- **Responsibility:** Produce the exact argument vector, working directory, timeout, non-secret environment, and artifact paths.
- **Forbidden:** Execute tools or modify the workspace.

It should extend the existing `ExecutionTaskFactory` rather than introduce a second graph-to-task path.

### PreparationCommandAdapter

- **Owner:** local execution support, invoked through the existing `LocalExecutor` command contract.
- **Input:** a typed, serialized preparation request.
- **Output:** prepared resource plus receipt file.
- **Responsibility:** Perform one bounded operation such as checkout, verified download/extraction, or deterministic configuration rendering.
- **Forbidden:** Planning, resource selection, Runtime lifecycle, task scheduling, silent retries, or secret persistence.

The adapter is not a new executor and does not bypass `LocalExecutor`. It exists because clone/download/extract/receipt generation must be one auditable subprocess operation without shell chaining. It uses the standard library and existing project dependencies; unsupported protocols require no new dependency and return `UNSUPPORTED` during Materialization.

### PreparationReadinessValidator

- **Owner:** Materialization validation.
- **Input:** complete materialized graph, evidence bundle, workspace policy, backend/tool capabilities.
- **Output:** node diagnostics merged into `MaterializationReport`.
- **Responsibility:** Validate evidence sufficiency, reference production chains, path ownership, integrity policy, capabilities, and receipt declarations.
- **Forbidden:** Download, inspect the network, repair evidence, or alter graph topology.

This extends the existing `ExecutionReadinessValidator`; it does not create a separate readiness gate.

---

## 5. Preparation Task Contracts

### Repository preparation

Supported initial modes:

1. verify an already prepared workspace repository;
2. clone/fetch a Git repository at a verified revision.

Required evidence:

- supported canonical URI;
- target path;
- revision policy;
- repository manifest;
- required entrypoint/environment/config file facts.

Receipt validation includes resolved commit, remote identity, clean target-boundary check, and required manifest entries.

### Dataset preparation

Supported initial modes:

1. verify an already prepared dataset;
2. fetch a single HTTPS artifact with checksum;
3. fetch and safely extract a supported archive;
4. use a repository-contained dataset path.

Extraction must reject absolute members, `..` traversal, link escape, and unexpected extraction roots. Datasets requiring interactive terms or unsupported SDKs remain `UNSUPPORTED`.

### Checkpoint preparation

Supported initial modes mirror dataset preparation but require checkpoint-specific size, checksum, revision, and format evidence. Partial downloads use a temporary path and become visible only after integrity verification and atomic rename.

### Configuration preparation

Supported initial modes are existing file verification, deterministic copy, deterministic render, and typed patch application. Output serialization must be stable. A configuration receipt records the base fingerprint, applied value/patch fingerprint, output fingerprint, and template version.

### Failure and resume

- Preparation commands write to attempt-scoped temporary locations.
- Final resource publication and receipt publication occur only after validation.
- A successful task is resumable only when its receipt and resource integrity still validate.
- Stale temporary paths are not canonical artifacts and may be cleaned under Runtime workspace policy.
- Failed preparation never leaves a success receipt.
- Credentials are resolved only inside the executing process and are redacted from command metadata, trace, logs, receipts, and reports.

Execution Engine state transitions, attempt persistence, reconciliation, and scheduling remain unchanged.

---

## 6. End-to-End Data Flow

```text
paper.pdf
  ↓
PaperReproductionAnalysis
  ↓
ResearchResourceDiscovery
  ├── candidates / selections / evidence
  └── ExecutionEvidenceBundle
  ↓
ExecutionStrategy + abstract ExecutionGraph
  ↓
ExecutionMaterializer
  ├── repository preparation spec
  ├── environment preparation spec
  ├── dataset preparation spec
  ├── checkpoint preparation spec
  ├── configuration preparation spec
  ├── training/evaluation/comparison specs
  └── MaterializationReport
  ↓ READY
ExecutionRun
  ↓
Preparation receipts + logs + workload artifacts
  ↓
ExecutionReport
  ↓
ReproductionPipelineResult / Console report
```

### Canonical artifacts

The one-command pipeline produces or persists:

| Stage | Artifact |
|---|---|
| Analysis | `PaperReproductionAnalysis` |
| Discovery | `ResearchResourceDiscovery` |
| Evidence projection | `ExecutionEvidenceBundle` |
| Planning | `ExecutionStrategy`, `DecisionTrace`, abstract `ExecutionGraph` |
| Materialization | `ExecutionMaterialization`, materialized graph, `MaterializationReport` |
| Preparation | repository/dataset/checkpoint/configuration receipts |
| Execution | `ExecutionRun`, task attempts/results, `ExecutionTrace`, artifacts |
| Reporting | `ExecutionReport`, application-level reproduction result |

`ExecutionEvidenceBundle` and `ExecutionMaterialization` are immutable workspace artifacts. Preparation receipts and runtime outcomes belong to `ExecutionStore` through the existing artifact tracker because they are execution results.

---

## 7. One-Command Orchestration

`reproduce <paper.pdf>` continues to call the Facade once. `ReproductionPipelineService` remains the orchestration owner:

```text
Console
  → Facade.reproduce()
  → ReproductionPipelineService
      1. Analyze
      2. Discover
      3. Project execution evidence
      4. Plan and build abstract graph
      5. Materialize the complete graph
      6. Enforce READY
      7. Execute or resume
      8. Return report
```

The Console must not call preparation commands, Materializer, Execution Engine, or stores directly. Facade must not construct templates or preparation requests. Runtime must not orchestrate business stages.

If evidence projection or Materialization blocks, the command returns structured diagnostics identifying:

- the affected graph node;
- the missing or conflicting evidence field;
- the upstream capability that must supply it;
- whether user authorization is required;
- whether the source protocol is unsupported.

No `ExecutionRun` is created for a blocked graph.

---

## 8. Dependency Boundaries

Allowed dependencies:

```text
Discovery providers
  → discovery models and provider clients

ExecutionEvidenceProjector
  → Discovery canonical models
  → execution evidence models

Materialization
  → Planning/Discovery/evidence canonical models
  → materialization ports and templates
  → application-provided workspace/capability context values

PreparationCommandAdapter
  → typed preparation request models
  → standard library / already approved dependencies

Application
  → capability public services and Runtime-provided stores
```

Forbidden dependencies:

- Planning importing Materialization, Runtime, LocalExecutor, or preparation adapters;
- Materialization importing Runtime Session, configuration loaders, LLM providers, or LocalExecutor internals;
- Discovery executing preparation side effects;
- Preparation adapters importing Planning or managing ExecutionRun state;
- Execution Engine loading Discovery or Planning artifacts;
- Console importing evidence, templates, executors, or stores.

---

## 9. Required Modules and Changes

Suggested new files:

```text
models/
└── execution_evidence.py

discovery/execution_evidence/
├── __init__.py
├── projector.py
├── validation.py
└── repository_manifest.py

execution_materialization/
├── preparation_templates.py
├── preparation_factory.py
└── preparation_validation.py

execution/preparation/
├── __init__.py
├── request.py
├── command.py
├── repository.py
├── dataset.py
├── checkpoint.py
├── configuration.py
├── integrity.py
└── receipts.py

runtime/session/
└── execution_evidence_artifacts.py
```

Required additive changes:

- `ResearchResourceDiscovery` persistence: store the evidence projection as a sibling artifact, not as mutable runtime state.
- Discovery providers: collect exact source/revision/manifest/integrity facts when available.
- `ExecutionMaterializer`: accept `ExecutionEvidenceBundle` and resolve `PRESENT`/`WILL_BE_PRODUCED` references.
- `TaskTemplateRegistry`: register preparation templates.
- `ExecutionReadinessValidator`: validate production chains and preparation receipts.
- `ReproductionPipelineService`: add evidence projection between Discovery and Planning/Materialization.
- Execution artifact verification: validate preparation receipt/resource pairs during resume.

No redesign is required for `ExecutionEngine`, scheduler, state machine, `ExecutionStore`, Runtime lifecycle, or LocalExecutor invocation contract.

---

## 10. Implementation Order

1. Add typed execution evidence models, schema versions, validation, and legacy-compatible persistence.
2. Add `ExecutionEvidenceProjector` using existing Discovery evidence; report missing/conflicting facts without network side effects.
3. Add repository manifest collection to supported Discovery providers.
4. Add typed resolved-reference availability and producer/output linkage.
5. Add repository preparation template and receipt contract for prepared and Git-backed repositories.
6. Add deterministic configuration preparation and receipt contract.
7. Add dataset and checkpoint preparation templates, safe download/extraction, integrity checks, and receipts.
8. Extend readiness validation to require exact node coverage, evidence provenance, path ownership, capability support, and valid future-reference chains.
9. Add application wiring and immutable evidence artifact persistence.
10. Add resume verification for preparation receipts and prepared resources.
11. Build one controlled official-repository reproduction fixture with pinned source/assets and bounded workload.
12. Add crash/resume, tampered artifact, missing credential, unsupported protocol, path traversal, and checksum failure tests.

Repository and configuration preparation should land before dataset/checkpoint support because they unlock the smallest controlled end-to-end fixture.

---

## 11. Acceptance Criteria

This phase is complete only when:

- one supported paper with an official repository can pass from PDF to `ExecutionReport` through one Facade call;
- every graph node has a versioned executable specification before run creation;
- repository, dataset, checkpoint, and configuration decisions use typed evidence rather than free-form extension keys;
- future repository paths are accepted only when linked to a verified upstream producer;
- preparation operations produce validated receipt artifacts;
- no command, path, revision, credential, or output is guessed from a stage label;
- unsupported protocols and missing authorization stop before `ExecutionRun` creation;
- workspace escape, unsafe archive extraction, checksum mismatch, and secret persistence are rejected;
- process restart resumes the same run and reuses preparation tasks only after receipt/resource verification;
- existing Planning models, Execution Engine APIs, Runtime ownership, ExecutionStore layout, and LocalExecutor metadata contract remain compatible;
- the full test suite and a controlled end-to-end reproduction test pass.

---

## 12. Risks and Unresolved Questions

| Risk | Control |
|---|---|
| Discovery evidence remains too coarse | Typed evidence completeness report and provider-specific manifest collection |
| Remote branch changes after Discovery | Prefer immutable commit/revision; compare resolved revision during preparation |
| Repository manifest differs from checkout | Receipt validation checks required files against the resolved revision |
| Dataset/checkpoint protocols proliferate | Explicit supported-source matrix; unsupported sources block rather than invoke arbitrary tools |
| Unsafe archives or workspace escape | Temporary extraction, canonical path checks, link rejection, and atomic publication |
| Credentials leak into persisted artifacts | Store only secret references; resolve at process boundary; redact all outcomes |
| Successful receipt outlives deleted/corrupt resource | Resume validates both receipt and resource integrity |
| Planning begins carrying commands | Keep evidence factual and templates in Materialization |
| Preparation adapter becomes a second executor | It remains a bounded subprocess command invoked exclusively by LocalExecutor |
| “One command” is interpreted as universal support | Publish an explicit support matrix and return structured `UNSUPPORTED` diagnostics |

The first controlled fixture must decide the initial supported source matrix: Git repository plus prepared/local assets is the lowest-risk baseline; verified HTTPS dataset/checkpoint retrieval is the next increment. Universal repository and dataset support is not a v1.3 completion requirement.
