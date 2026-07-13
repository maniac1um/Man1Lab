# Planning-to-Execution Materialization Architecture

**Status:** Foundation implemented; supported-template coverage and controlled end-to-end reproduction remain incomplete
**Target:** Man1Lab v1.3 executable reproduction path
**Audience:** Architects and implementers

This document defines the boundary that converts Planning decisions into backend-ready execution instructions. It complements [EXECUTION_PLANNING.md](EXECUTION_PLANNING.md), [EXECUTION_ENGINE.md](EXECUTION_ENGINE.md), [EXECUTION_MODEL.md](EXECUTION_MODEL.md), and [EXECUTION_RUNTIME.md](EXECUTION_RUNTIME.md).

---

## 1. Problem and Architecture Position

Execution Planning currently produces an immutable `ExecutionStrategy` and an abstract `ExecutionGraph`. The graph correctly expresses stage type, order, dependencies, bindings, assets, and rationale, but it does not reliably contain the `command`, working directory, environment, timeout, or artifact locations required by `LocalExecutor`.

Planning must not guess machine-specific paths or claim that a command is runnable. Execution Engine must not reinterpret strategy or invent commands. The missing capability is an explicit Materialization layer:

```text
PaperReproductionAnalysis
        ↓
ResearchResourceDiscovery
        ↓
ExecutionStrategy + abstract ExecutionGraph       ← what should happen
        ↓
Planning-to-Execution Materialization             ← make instructions concrete
        ↓
ExecutionMaterialization
  ├── materialized ExecutionGraph
  └── MaterializationReport
        ↓ readiness gate
ExecutionEngine                                   ← run and track instructions
        ↓
ExecutionRun → ExecutionReport
```

Materialization is a peer capability between Planning and Execution. It belongs in a new top-level `execution_materialization/` package, not in `execution_planning/`, `execution/`, Runtime, Console, or LocalExecutor.

---

## 2. Responsibility Boundaries

| Concern | Owner | Boundary |
|---------|-------|----------|
| Decide reuse, adaptation, generation, scope, and stage order | Execution Planning | Produces decisions and abstract topology; never produces machine claims |
| Convert strategy/graph nodes into executable instructions | Materialization | Resolves deterministic templates and context into typed execution specifications |
| Resolve repository and artifact locations | Materialization resolvers | Compute normalized workspace/backend references from bindings and application-provided context; do not clone or download |
| Decide required environment | Planning | Describes framework/dependency intent |
| Produce environment setup invocation | Materialization | Selects a supported template and concrete command; does not execute it |
| Generate LocalExecutor metadata | `ExecutionTaskFactory` | Projects a typed executable specification into the existing task metadata contract |
| Validate execution readiness | `ExecutionReadinessValidator` | Blocks unsupported, ambiguous, unsafe, or incomplete instructions before run creation |
| Validate graph/DAG structure | Execution Engine | Retains existing structural and lifecycle validation |
| Execute commands and collect outcomes | LocalExecutor | Consumes instructions; never derives them from strategy |
| Run/task lifecycle, scheduling, trace, resume | Execution Engine | Unchanged |
| Workspace root and durable persistence | Runtime | Supplies root/store services; never materializes commands |
| Full pipeline orchestration | Application service | Sequences capabilities and persists handoffs; Console and Facade only delegate |

Materialization must not clone repositories, create environments, download data, generate source code, start processes, mutate Planning artifacts, manage Runtime/Session, or persist execution state.

---

## 3. Materialization Models

### 3.1 ExecutableTaskSpec

Add a canonical, backend-neutral model representing one concrete invocation:

| Field | Meaning |
|-------|---------|
| `backend_kind` | Requested backend capability; `local` for the v1.3 path |
| `command` | Non-empty argument vector; never a shell command string |
| `working_directory` | Normalized workspace-relative or explicitly typed external reference |
| `environment_variables` | Non-secret variable values or secret references; never credentials in plaintext |
| `timeout_seconds` | Optional positive execution timeout |
| `artifact_paths` | Mapping from declared output logical name to normalized output path |
| `template_id` / `template_version` | Deterministic materialization provenance |
| `source_binding_ids` / `source_asset_ids` | Inputs used to create the instruction |

For backward compatibility, `ExecutionGraphNode` gains an optional `execution_spec`. Existing Planning-produced graphs without it remain valid abstract graphs. Materialization copies the graph and fills this optional field; it never mutates the original.

The graph may additionally carry an optional `materialization_id` and materialization schema version. These fields are additive and default to absent, so existing serialized Planning graphs remain valid.

### 3.2 ExecutionMaterialization

Canonical output of the capability:

- `materialization_id`;
- source analysis/discovery/strategy/graph identifiers and fingerprints;
- target backend capability (`local` initially);
- materialized `ExecutionGraph`;
- `MaterializationReport`;
- creation timestamp and schema version.

### 3.3 MaterializationReport

Readiness is explicit rather than inferred from the presence of metadata:

| Field | Meaning |
|-------|---------|
| `status` | `READY`, `BLOCKED`, or `UNSUPPORTED` |
| `node_results` | Per-node readiness, selected template, and diagnostics |
| `errors` | Blocking structured issues |
| `warnings` | Non-blocking assumptions and deferred checks |
| `required_capabilities` | Backend/tool capabilities required by the graph |
| `resolved_references` | Redacted paths/resource references used during materialization |

Only `READY` materializations may be passed to `ExecutionEngine.start_run()`. The Application layer enforces this gate; Engine remains unchanged.

---

## 4. Component Design

### ExecutionMaterializer

- **Responsibility:** Orchestrate node-by-node materialization without executing effects.
- **Input:** `ExecutionStrategy`, `ResearchResourceDiscovery`, abstract `ExecutionGraph`, `MaterializationContext`.
- **Output:** `ExecutionMaterialization`.
- **Dependencies:** Task factory, template registry, resolver ports, readiness validator, canonical models.
- **Forbidden:** Runtime lifecycle, filesystem mutation, process execution, planning decisions.

### ExecutionGraphBuilder

- **Responsibility:** Produce a new graph whose topology and planning provenance are identical to the source graph and whose nodes contain typed execution specifications.
- **Input:** Abstract graph plus per-node materialization results.
- **Output:** Materialized `ExecutionGraph`.
- **Dependencies:** Canonical graph/materialization models only.
- **Forbidden:** Selecting commands, resolving paths, changing dependencies, adding/removing stages.

This builder is distinct from `execution_planning.execution_graph.build_execution_graph`: Planning builds abstract topology; Materialization enriches it without changing topology.

### ExecutionTaskFactory

- **Responsibility:** Combine one graph node, chosen template, and resolved references into `ExecutableTaskSpec`; provide the deterministic projection used by graph decomposition.
- **Input:** Node, `TaskTemplate`, resolved resource/path values.
- **Output:** Typed execution specification and LocalExecutor-compatible metadata projection.
- **Dependencies:** Canonical models and serialization helpers.
- **Forbidden:** Execute commands, inspect Runtime, choose Planning strategy.

The existing decomposition step remains the graph-to-task boundary. It copies the optional execution specification into the existing `ExecutionTask.metadata` keys consumed by LocalExecutor. No ExecutionEngine or LocalExecutor API change is required.

### TaskTemplateRegistry

- **Responsibility:** Resolve a versioned deterministic template by stage type, backend capability, and verified input shape.
- **Input:** `ExecutionGraphStageType`, backend kind, available facts/capabilities.
- **Output:** `TaskTemplate` or an unsupported diagnostic.
- **Dependencies:** Registered templates only; no global configuration access.
- **Forbidden:** Execute tools, perform discovery, silently fall back to guessed commands.

Initial templates cover only instructions that can be derived deterministically. Unknown training/evaluation entrypoints produce `BLOCKED`, not an assumed `python train.py` command.

### Materialization Resolvers

- **Responsibility:** Convert binding/asset identities and a supplied workspace descriptor into normalized references.
- **Ports:** `RepositoryLocationResolver`, `AssetLocationResolver`, `EnvironmentLocationResolver`, `EntrypointResolver`.
- **Input:** Strategy bindings, discovery assets, read-only workspace descriptor.
- **Output:** Typed resolved references with provenance and confidence.
- **Dependencies:** Canonical artifacts and injected read-only adapters.
- **Forbidden:** Clone/download/install, create directories, import Runtime Session, search the network implicitly.

Runtime/Application owns the workspace root. Materialization receives a `MaterializationContext` value containing the approved root and capability descriptors; it does not discover or change the root.

### ExecutionReadinessValidator

- **Responsibility:** Validate the complete materialized graph before execution.
- **Input:** Source artifacts, materialized graph, context policy.
- **Output:** `MaterializationReport`.
- **Dependencies:** Canonical models and pure validation rules.
- **Forbidden:** Repair instructions automatically or dispatch tasks.

---

## 5. Executable Task Contract

LocalExecutor's existing metadata contract remains unchanged. Decomposition projects the typed specification as follows:

| `ExecutableTaskSpec` | `ExecutionTask.metadata` | Rule |
|----------------------|--------------------------|------|
| `command` | `command` | JSON array of non-empty strings; no shell interpolation |
| `working_directory` | `working_directory` | Normalized path constrained by workspace policy |
| `environment_variables` | `environment_variables` | JSON object; reject secret-looking keys/values unless represented by approved reference |
| `timeout_seconds` | `timeout_seconds` | Positive numeric string |
| `artifact_paths` | `artifact_paths` | JSON mapping whose keys exactly match declared output logical names |

Example transformation:

```text
Planning node
  stage_type: training
  intent: "Train model"
  repository binding: primary_repository
  configuration asset: config/reproduce.yaml

Materialized instruction
  command: ["python", "train.py", "--config", "config/reproduce.yaml"]
  working_directory: "repositories/primary"
  environment_variables: {"MAN1LAB_RUN_MODE": "reproduction"}
  timeout_seconds: 86400
  artifact_paths: {"training_output": "outputs/checkpoints/final.pt"}
```

This example is valid only when the entrypoint, config, and output contract are supported by verified repository/asset evidence or an explicit template. Materialization must never infer them from the label “Train model” alone.

### Readiness invariants

- Every executable node has a supported backend and template version.
- Command is an argument vector and contains no shell operators.
- Working directory and local artifact paths remain within the approved workspace unless explicitly typed as external.
- Required bindings/assets resolve uniquely.
- Every required `OutputDeclaration` has exactly one compatible artifact path.
- Dependency-produced inputs reference declared upstream outputs.
- No plaintext secret enters graph, task metadata, trace, or report.
- Abstract nodes without an execution specification block execution.
- Topology, binding IDs, asset IDs, and Planning rationale are preserved unchanged.

---

## 6. Minimal v1.3 Reproduction Flow

```text
paper.pdf
  ↓ Parsing
ParsedDocument
  ↓ Analysis
PaperReproductionAnalysis
  ↓ Discovery
ResearchResourceDiscovery
  ↓ Execution Planning
ExecutionStrategy + DecisionTrace + abstract ExecutionGraph
  ↓ Materialization
ExecutionMaterialization
  ├── materialized ExecutionGraph
  └── MaterializationReport(READY)
  ↓ Execution Engine
ExecutionRun + ExecutionTrace + ArtifactManifest
  ↓
ExecutionReport
```

Workspace persistence separates the artifacts:

```text
workspace/
├── analysis/                 PaperReproductionAnalysis
├── discovery/                ResearchResourceDiscovery
├── planning/                 ExecutionStrategy
├── decision/                 DecisionTrace + abstract ExecutionGraph
├── materialization/          execution_materialization.json
│                              materialized_execution_graph.json
│                              materialization_report.json
└── execution/runs/<run_id>/  run/tasks/trace/artifacts/report
```

`WorkspaceArtifactStore` may persist the immutable Materialization artifacts through a dedicated materialization projection or sibling store API. `ExecutionStore` must not store Planning or Materialization decisions; it begins at `ExecutionRun`.

---

## 7. One-Command Reproduction Orchestration

The Console command `reproduce <paper.pdf>` becomes a single Facade call. It must not call Console command handlers recursively or read/write stage stores directly.

```text
Console
  ↓ reproduce(paper)
Platform Facade
  ↓ delegate
ReproductionPipelineService        ← application orchestration owner
  ├── Analysis
  ├── Discovery
  ├── Execution Planning
  ├── Materialization
  ├── readiness gate
  ├── PlatformExecutionService
  └── final report projection
```

The application service owns stage order, idempotent handoffs, stage-level resume selection, and correlation IDs. It does not implement analysis, planning, command generation, task scheduling, or persistence mechanics.

Console, Runtime, ExecutionEngine, LocalExecutor, Planning workflow, and Materializer must not own the end-to-end pipeline.

If Materialization is `BLOCKED`, the pipeline stops before creating an `ExecutionRun` and returns the `MaterializationReport` with actionable diagnostics.

---

## 8. Backward Compatibility

- `ExecutionStrategy` remains unchanged and valid.
- Existing abstract `ExecutionGraph` JSON remains valid because new execution fields are optional.
- Existing `ExecutionTask` and LocalExecutor metadata keys remain unchanged.
- ExecutionEngine, scheduler, state machine, ExecutionStore, and Runtime ownership remain unchanged.
- Legacy `ExecutionPlanner`/`ExecutionPlan` continues to coexist but is not the canonical Materialization path.
- Existing callers may still submit a manually materialized graph if it passes readiness validation.
- Schema versions must distinguish abstract legacy graphs from materialized graphs without coercing missing instructions into defaults.

---

## 9. Required New Modules and Files

```text
models/
└── execution_materialization.py       canonical specs, report, issues, provenance

execution_materialization/
├── __init__.py                        narrow public API
├── materializer.py                    ExecutionMaterializer
├── graph_builder.py                   materialized graph copy/enrichment
├── task_factory.py                    typed spec and metadata projection
├── templates.py                       TaskTemplate + registry
├── validation.py                      readiness gate
├── ports.py                           read-only resolver contracts
└── resolvers/
    └── workspace.py                   workspace-scoped reference adapters

application/
├── reproduction_pipeline.py           one-command application orchestration
└── runtime/materialization_wiring.py  inject context, resolvers, templates

runtime/session/
└── materialization_artifacts.py       immutable workspace persistence projection

docs/architecture/
└── EXECUTION_MATERIALIZATION.md
```

Required additive changes:

- `models/execution_graph.py`: optional typed execution/materialization fields.
- `execution/decomposition.py`: deterministic typed-spec-to-metadata projection.
- `application/platform_execution.py`: require a READY materialized graph for new runs.
- `application/facade.py` and Console protocol: delegate one-command reproduction to the application pipeline service.

No change is required to ExecutionEngine, LocalExecutor, ExecutionStore layout, or Runtime lifecycle.

---

## 10. Migration Order

1. Add canonical materialization models and optional graph fields with legacy round-trip tests.
2. Add resolver ports, template registry, task factory, graph builder, and pure readiness validation.
3. Implement `ExecutionMaterializer` and immutable workspace persistence; test deterministic output and blocked diagnostics.
4. Extend decomposition projection and gate `PlatformExecutionService` on `MaterializationReport.READY`.
5. Add `ReproductionPipelineService`, Facade/Console delegation, and one controlled end-to-end paper reproduction fixture.

---

## 11. Risks and Controls

| Risk | Control |
|------|---------|
| Guessing repository entrypoints | Require verified evidence or explicit template; otherwise `BLOCKED` |
| Machine-specific paths leak into Planning | Resolve only in Materialization using injected workspace context |
| Secrets persisted in metadata | Secret references/redaction validation; reject plaintext sensitive fields |
| Template becomes hidden strategy | Templates implement committed decisions only and preserve source provenance |
| Abstract graph executed accidentally | Application readiness gate; missing execution spec is blocking |
| Graph topology changes during enrichment | Builder invariant compares node IDs, dependencies, bindings, and assets |
| Clone-before-inspection dependency | v1.3 supports only evidence-backed entrypoints or already prepared repositories; staged rematerialization is deferred |
| Backend contract drift | Version templates/specs and test projection against LocalExecutor parser |
| Duplicate orchestration in Console | Single application pipeline service; Console delegates one method |

The principal unresolved product constraint is evidence quality: when Discovery/Planning cannot identify a runnable entrypoint and output contract, Materialization must stop safely rather than fabricate an executable workflow.
