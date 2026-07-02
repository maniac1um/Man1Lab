# Platform Integration Audit — Final Phase

**Date:** 2026-06-29  
**Scope:** Discovery → Execution Planning → Planner platform wiring  
**Verdict:** **Man1Lab v1.2 Platform Complete**

---

## Pipeline Before

```text
Reader
    ↓
Planner (PaperReproductionAnalysis)
    ↓
Coder
    ↓
Runner
    ↓
Reviewer
```

Discovery and Execution Planning existed as standalone modules but were not invoked by `WorkflowOrchestrator`.

---

## Pipeline After

```text
Reader
    ↓
DiscoveryWorkflow
    ↓
ExecutionPlanningWorkflow
    ↓
Planner (ExecutionStrategy)
    ↓
Coder
    ↓
Runner
    ↓
Reviewer
    ↓
Reporter
```

---

## Workflow Changes

| File | Change |
|------|--------|
| `workflow/orchestrator.py` | Inserts Discovery and Execution Planning stages; config flags for disable paths |
| `workflow/pipeline.py` | Added `DISCOVERY`, `EXECUTION_PLANNING` to `PipelineStage` |
| `models/report.py` | `WorkflowHistory` extended with `discovery`, `execution_strategy` |
| `discovery/workflow.py` | Added `DiscoveryWorkflow.default()` |
| `discovery/empty.py` | `build_empty_discovery()` for disabled discovery |
| `execution_planning/workflow.py` | New `ExecutionPlanningWorkflow` coordinator |
| `execution_planning/stages.py` | Six deterministic planning stages |
| `app.py` | Wires discovery + execution planning at composition root |

### Orchestrator stage order

1. `READER` → `PaperReproductionAnalysis`
2. `DISCOVERY` → `ResearchResourceDiscovery` (or empty artifact when disabled)
3. `EXECUTION_PLANNING` → `ExecutionStrategy` (skipped when disabled)
4. `PLANNER` → `TaskModel` (strategy-driven or legacy)
5. `CODER` → `RUNNER` → review loop → `REPORTER` (unchanged)

---

## Planner Changes

| Before | After |
|--------|-------|
| `Planner.run(analysis)` | `Planner.run(execution_strategy)` |
| Inferred strategy from analysis JSON | Consumes committed strategy modules only |

**Planner responsibilities (unchanged scope, new input):**

- Task decomposition
- Task dependency ordering
- Task sequencing

**Planner never:**

- Chooses repository / greenfield / adaptation / reuse
- Inspects `ResearchResourceDiscovery` directly
- Infers engineering strategy

**Transitional compatibility:** `Planner.run_legacy(analysis)` when `execution_planning.enabled=false`.

| File | Change |
|------|--------|
| `agents/planner.py` | Strategy-driven `run()`; legacy `run_legacy()` |
| `agents/analysis_context.py` | `build_planner_user_content(strategy)`; legacy analysis builder |

---

## Execution Planning Integration

`ExecutionPlanningWorkflow.run(analysis, discovery)` executes six fixed stages:

1. Strategy Decision
2. Resource Binding
3. Reuse Planning
4. Adaptation Planning
5. Generation Planning
6. Risk Assessment

Then `ExecutionStrategyBuilder.build()` assembles and validates `ExecutionStrategy`.

Deterministic posture rules:

| Condition | Posture |
|-----------|---------|
| Verified official repository (PASS) | `official_repository` |
| PASS/PARTIAL non-official candidate | `community_fork` / `hybrid` |
| No eligible candidates / verification fail | `greenfield` |

---

## Discovery Integration

| Mode | Behavior |
|------|----------|
| `discovery.enabled=true` | `DiscoveryWorkflow.default().run(analysis)` |
| `discovery.enabled=false` | `build_empty_discovery(analysis)` — Execution Planning still runs |

Discovery is optional via configuration; Execution Planning is never bypassed when enabled.

---

## Configuration Updates

| File | Content |
|------|---------|
| `conf/discovery/default.yaml` | `enabled: true` |
| `conf/execution_planning/default.yaml` | `enabled: true` |
| `conf/config.yaml` | Registers both config groups |
| `configuration/models.py` | `DiscoveryConfig`, `ExecutionPlanningConfig` |
| `configuration/hydra_provider.py` | Maps Hydra → settings |
| `configuration/legacy_provider.py` | Env fallbacks `DISCOVERY_ENABLED`, `EXECUTION_PLANNING_ENABLED` |

No business capability imports Hydra.

---

## MLflow Integration

`TrackedWorkflowOrchestrator` logs:

| Stage | Tracked data |
|-------|--------------|
| Discovery | Nested run, `discovery_status` tag, `discovery_candidate_count` metric, `discovery.json` artifact |
| Execution Planning | Nested run, `strategy_posture` tag, `binding_count` metric, `execution_strategy.json` artifact |

MLflow imports remain confined to `tracking/mlflow_tracker.py`.

---

## Dependency Audit

| Module | New imports |
|--------|-------------|
| `workflow/orchestrator.py` | `DiscoveryWorkflow`, `ExecutionPlanningWorkflow`, `build_empty_discovery` |
| `agents/planner.py` | `ExecutionStrategy` only (no discovery) |
| `execution_planning/*` | Analysis + discovery models, builder |
| `discovery/empty.py` | Discovery builder + empty port results |

No Hydra or MLflow imports inside capabilities.

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| No agent redesign | Yes — Reader, Coder, Runner, Reviewer unchanged |
| No Planner intelligence increase | Yes — strategy context only, no new decisions |
| No Discovery logic inside Planner | Yes |
| No Execution Planning logic inside Planner | Yes |
| No Discovery logic inside Workflow beyond orchestration | Yes |
| Execution Planning owns strategy | Yes |
| Planner owns decomposition | Yes |
| Workflow orchestrates only | Yes |

---

## Test Coverage

```text
pixi run test
364 passed
```

New tests (`tests/test_platform_integration.py`): **8**

| Area | Covered |
|------|---------|
| ExecutionPlanningWorkflow (empty + embedded discovery) | Yes |
| Planner consumes ExecutionStrategy | Yes |
| End-to-end orchestrator pipeline | Yes |
| NoOp discovery + execution planning | Yes |
| Disabled discovery (empty artifact) | Yes |
| Disabled execution planning (legacy planner) | Yes |
| Hydra config defaults | Yes |
| MLflow tracking (Discovery + ExecutionStrategy artifacts) | Yes |

Updated: `tests/test_planner.py` (legacy path), `tests/test_configuration.py`

---

## Updated Architecture Diagram

```text
Paper (PDF)
    ↓
Parsing → ParsedDocument
    ↓
Reader → PaperReproductionAnalysis
    ↓
DiscoveryWorkflow → ResearchResourceDiscovery
    ↓
ExecutionPlanningWorkflow → ExecutionStrategy
    ↓
Planner → TaskModel
    ↓
Coder → Workspace
    ↓
Runner → ExecutionResult
    ↓
Verification → Review → Report
```

Capability boundaries:

```text
Reader        → PaperReproductionAnalysis
Discovery     → ResearchResourceDiscovery
Exec Planning → ExecutionStrategy
Planner       → TaskModel
```

---

## Remaining Technical Debt

| Item | Notes |
|------|-------|
| Selection stage skeleton | Discovery selection still placeholder; bindings use ranking directly |
| `Planner.run_legacy` | Transitional — remove when execution planning always enabled |
| Coder strategy consumption | Coder still uses analysis + task; future: bind to ExecutionStrategy |
| Review loop re-coding | Still deferred |
| GitHub Search API | Out of scope |

---

## Verdict

**Man1Lab v1.2 Platform Complete**

The production pipeline now connects Analysis → Discovery → Execution Planning → Planner with strict capability boundaries, Hydra configuration switches, MLflow stage tracking, and full regression coverage.
