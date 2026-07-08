# Man1Lab MLflow Migration — Phase 1 Report

**Date:** 2026-06-30  
**Scope:** Thin MLflow experiment tracking (infrastructure layer only)  
**Verdict:** **Phase 1 complete**

---

## Experiment Tracking Architecture

```text
conf/tracking/default.yaml
    ↓
TrackingConfig (configuration/models.py)
    ↓
build_experiment_tracker() (tracking/bootstrap.py)
    ↓
ExperimentTracker protocol
    ├── NoOpExperimentTracker   (disabled / tests)
    └── MLflowExperimentTracker (tracking/mlflow_tracker.py — only mlflow import)
    ↓
TrackedWorkflowOrchestrator (tracking/workflow.py)
    ↓
WorkflowOrchestrator (unchanged topology)
```

**Experiment model:** one complete paper reproduction = **one parent MLflow run**.  
Analysis (Reader), planning (Planner), generation (Coder), execution (Runner), review (Reviewer / PatchPlanner), and reporting (Reporter) are recorded as **nested runs** within that parent run.

---

## Modified Files

| File | Change |
|------|--------|
| `tracking/` | **New** — protocol, noop, mlflow adapter, provider, bootstrap, workflow wrapper |
| `conf/tracking/default.yaml` | **New** — tracking settings |
| `conf/config.yaml` | Added `tracking` config group |
| `configuration/models.py` | Added `TrackingConfig` |
| `configuration/hydra_provider.py` | Maps tracking settings |
| `configuration/legacy_provider.py` | Env-based tracking defaults (`noop`, disabled) |
| `app.py` | Composition root wires `TrackedWorkflowOrchestrator` |
| `scripts/run_integration_m7_1.py` | Same tracking bootstrap |
| `requirements.txt` / `pixi.toml` | Added `mlflow>=2.0.0` |
| `.gitignore` | `mlruns/`, `mlflow.db` |
| `tests/test_experiment_tracking.py` | **New** — tracker + import audit tests |
| `tests/test_configuration.py` | `tracking` field on `AppSettings` |

**Unchanged:** `workflow/orchestrator.py` topology, all agent logic (`agents/*`), analysis/planner/coder/runner/reviewer implementations.

---

## Capability Mapping

| Approved capability | Implementation |
|---------------------|----------------|
| **Experiment** | `mlflow.set_experiment(experiment_name)` — default `man1lab` |
| **Runs** | Parent run per `orchestrator.run(paper_path)` |
| **Parameters** | `paper_path`, `parser_backend` on parent run |
| **Metrics** | `stage_count` (parent); `duration_seconds` per nested stage |
| **Artifacts** | Final `report.md` logged on parent run |
| **Tags** | `paper_path`, `component`, `final_status` (parent); `stage`, `status` (nested) |
| **Nested runs** | One nested run per pipeline stage (`Reader`, `Planner`, …) |

**Not implemented (out of scope):** Registry, Projects, Recipes, Evaluation, Prompt Registry, Deployments, Tracing.

---

## Remaining Technical Debt

| Item | Phase |
|------|-------|
| Log analysis snapshot / workspace artifacts to MLflow | Phase 2 |
| Remote tracking server / artifact store configuration docs | As needed |
| Disable tracking in integration CI when added | When CI exists |
| Per-stage params (task count, exit codes) as structured metrics | Optional enhancement |
| `TRACKING_ENABLED` env documented in `.env.example` | Minor |

---

## Test Results

```text
pixi run test
172 passed in 10.46s
```

Includes 7 new experiment-tracking tests and import audit confirming no `mlflow` imports under `agents/`, `workflow/`, `services/`, `models/`, `validation/`.

---

## Architecture Audit

| Question | Answer |
|----------|--------|
| Thin integration preserved? | **Yes** — single adapter module; wrapper at composition root |
| Business code imports `mlflow`? | **No** — only `tracking/mlflow_tracker.py` |
| Only approved capabilities? | **Yes** — experiments, runs, params, metrics, artifacts, tags, nested runs |
| Workflow topology changed? | **No** — `WorkflowOrchestrator` untouched; `TrackedWorkflowOrchestrator` subclasses it |
| Agent capability boundaries changed? | **No** |
| Tests use tracking? | **No** by default — `LegacySettingsProvider` uses `noop` / disabled |

---

## Configuration

Default (Hydra / `app.py`):

```yaml
tracking:
  enabled: true
  backend: mlflow
  experiment_name: man1lab
  tracking_uri: sqlite:///mlruns/mlflow.db
```

Disable tracking:

```bash
TRACKING_ENABLED=false
# or
TRACKING_BACKEND=noop
```

View runs locally:

```bash
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db
```

---

## Success Criteria

```text
MLflow SDK → MLflowExperimentTracker → ExperimentTracker → TrackedWorkflowOrchestrator → Man1Lab
```

Business agents do not know MLflow exists.
