# ADR-0012 — Experiment Tracking with MLflow

## Status

Accepted

## Date

2026-06-30

## Context

Man1Lab v1.0.x persisted reproduction outcomes via text logs, workspace files, and integration JSON snapshots. There was no structured experiment history, run comparison, or durable artifact index across paper reproduction attempts.

MLflow was evaluated as the Experiment Tracking Layer backend (Technology Adoption Review, local). Man1Lab is not an MLOps platform — tracking must remain **infrastructure** behind a native port. Agents and workflow topology must not import MLflow directly.

Constraints:

- Business agents must not import `mlflow`
- `WorkflowOrchestrator` topology unchanged
- Tracking disabled by default in tests (`noop` backend)
- Adopt **Tracking subset only** — no Model Registry, Recipes, Gateway, Prompt Registry, GenAI Evaluation, or Deployments

## Decision

Adopt **MLflow with thin integration** at the **Experiment Tracking Layer** behind the **`ExperimentTracker` port**.

### Architecture

```text
conf/tracking/default.yaml
    ↓
TrackingConfig
    ↓
build_experiment_tracker() (tracking/bootstrap.py)
    ↓
ExperimentTracker protocol
    ├── NoOpExperimentTracker      (disabled / tests)
    └── MLflowExperimentTracker    (tracking/mlflow_tracker.py — sole mlflow import)
    ↓
TrackedWorkflowOrchestrator (tracking/workflow.py)
    ↓
WorkflowOrchestrator (unchanged topology)
```

### Experiment model

| Entity | Definition |
|--------|------------|
| **Experiment** | Reproduction campaign (default name: `man1lab`) |
| **Parent run** | One complete `orchestrator.run(paper_path)` |
| **Nested runs** | One per pipeline stage (Reader, Planner, Coder, …) |

### Approved MLflow capabilities

| Capability | Usage |
|------------|--------|
| Experiments | `mlflow.set_experiment(experiment_name)` |
| Runs | Parent + nested runs |
| Parameters | `paper_path`, `parser_backend` on parent run |
| Metrics | `stage_count` (parent); `duration_seconds` per nested stage |
| Artifacts | Final `report.md` on parent run |
| Tags | `paper_path`, `component`, `final_status`; per-stage `stage`, `status` |

### Out of scope (not adopted)

Model Registry, Projects, Recipes, Evaluation, Prompt Registry, Deployments, Tracing.

### Integration rules

| Rule | Detail |
|------|--------|
| **Composition root only** | `app.py` wires `TrackedWorkflowOrchestrator` |
| **Port first** | All tracking via `ExperimentTracker`; no direct MLflow in agents |
| **Config via Hydra** | `conf/tracking/default.yaml`; disable via `TRACKING_BACKEND=noop` |
| **Default store** | Local SQLite (`sqlite:///mlruns/mlflow.db`); `mlruns/` gitignored |

Business agents **do not know MLflow exists**.

## Alternatives

**Build native experiment store:** Rejected — duplicates solved problem; high maintenance.

**Weights & Biases:** Rejected for primary — SaaS cost and residency; less aligned with OSS governance.

**No experiment tracking (status quo):** Rejected — blocks run comparison and long-term audit trail.

**Full MLflow platform (Registry, Gateway, …):** Rejected — scope overlap with Man1Lab native layers.

## Consequences

**Positive:**

- Structured reproduction history with nested stage timing
- Local SQLite backend; no server required for development
- Thin adapter; workflow topology preserved
- Complements Hydra (config), Pixi (dev env), Docling (parsing) without boundary violation

**Negative:**

- Dual storage during migration (logs/snapshots + MLflow)
- Remote tracking server deferred to future phase
- Analysis snapshot / workspace artifacts not yet logged as MLflow artifacts (Phase 2)

## Relationship to Other ADRs

- [ADR-0001](ADR-0001-Workflow-Orchestrator.md): Orchestrator topology unchanged; tracking wraps at composition root
- [ADR-0010](ADR-0010-Hydra-Configuration.md): Tracking settings composed via Hydra
- [ADR-0011](ADR-0011-Pixi-Environment.md): `mlflow` declared in Pixi dependencies
- [infrastructure.md](../architecture/infrastructure.md): Adoption matrix updated to **Adopted**

Migration report (local): `private/design/migrations/mlflow-phase-1.md` or `docs/reviews/mlflow_migration_phase_1/report.md`
