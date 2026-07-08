# Platform Facade Audit — Phase 1

**Date:** 2026-06-29  
**Scope:** `application/facade.py`, `app.py` migration  
**Verdict:** **Ready for CLI Interface**

---

## New Architecture

```text
Future CLI
    ↓
Future Python SDK
    ↓
Future MCP / REST
    ↓
Man1Lab (Platform Facade)          ← this phase
    ↓
TrackedWorkflowOrchestrator
    ↓
WorkflowOrchestrator
    ↓
Analysis → Discovery → Execution Planning → Planner → Execution
```

All interfaces must enter through `Man1Lab`. Direct `WorkflowOrchestrator` access from interfaces is forbidden.

---

## Implemented Files

| File | Purpose |
|------|---------|
| `application/__init__.py` | Public exports |
| `application/facade.py` | `Man1Lab` platform facade |
| `application/version.py` | `PLATFORM_VERSION = "1.2.0"` |
| `tests/test_platform_facade.py` | Facade tests (12 tests) |
| `docs/reviews/platform_facade_phase_1/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `app.py` | Delegates to `Man1Lab.reproduce()` |
| `scripts/run_integration_m7_1.py` | Uses `Man1Lab` with capturing reporter |
| `docs/architecture/ARCHITECTURE.md` | Platform Interface Layer section |
| `docs/CURRENT_STATUS.md` | Facade documented |

---

## Facade Responsibilities

| Owned by Facade | Not owned by Facade |
|-----------------|---------------------|
| Workflow creation | Analysis logic |
| Dependency wiring | Discovery logic |
| Configuration loading (Hydra) | Planning logic |
| Service composition | Execution logic |
| Lifecycle (logging entry) | Business rules |
| MLflow tracker initialization | Agent prompts |

### Public API

| Method | Delegates to |
|--------|--------------|
| `reproduce()` | `TrackedWorkflowOrchestrator.run()` |
| `analyze()` | `Reader.run()` |
| `discover()` | `DiscoveryWorkflow.run()` or `build_empty_discovery()` |
| `plan()` | `ExecutionPlanningWorkflow.run()` |
| `execute()` | `Planner.run()` → `Coder.run()` → `Runner.run()` |
| `doctor()` | Environment checks (dirs, paper, credentials, parser, tracking) |
| `version()` | `PLATFORM_VERSION` |
| `configuration()` | Serialised `AppSettings` |

---

## Workflow Relationship

- `WorkflowOrchestrator` is **unchanged**
- Facade composes `TrackedWorkflowOrchestrator` with all agents and services
- `workflow/` does **not** import `application/`
- Optional `orchestrator=` injection for tests

---

## Hydra Integration

- Facade calls `initialize_app_configuration()` on construction (default)
- Business layers remain Hydra-free
- `configuration()` exposes effective settings to interfaces
- Tests can pass pre-built `AppSettings` with `initialize_configuration=False`

---

## MLflow Integration

- Facade calls `initialize_experiment_tracking(settings)` at construction
- `reproduce()` uses `TrackedWorkflowOrchestrator` (existing nested stage tracking)
- Partial operations (`analyze`, `discover`, `plan`, `execute`) open facade-scoped runs
- No MLflow imports added to business capabilities

---

## Backward Compatibility

| Entry point | Status |
|-------------|--------|
| `app.py` | Refactored to `Man1Lab.reproduce()` — behavior preserved |
| `pixi run` → `python app.py` | Works unchanged |
| `scripts/run_integration_m7_1.py` | Migrated to facade |
| Direct orchestrator in tests | Still valid for unit tests |

---

## Dependency Audit

| Module | Imports workflow? | Imports application? |
|--------|-------------------|----------------------|
| `application/facade.py` | Yes (composition only) | — |
| `app.py` | No | Yes |
| `workflow/orchestrator.py` | — | No |
| `agents/*` | No | No |
| `discovery/*` | No | No |
| `execution_planning/*` | No | No |

Dependency rule enforced:

```text
Interface → Facade → Workflow   ✅
Interface → Workflow            ❌
```

---

## Boundary Verification

| Constraint | Status |
|------------|--------|
| No CLI / argparse / typer / click | Yes |
| No SDK package | Yes |
| No REST / MCP | Yes |
| No business logic in facade | Yes |
| Workflow unchanged | Yes |
| Workflow never imports facade | Yes |
| Hydra only at facade/composition root | Yes |
| MLflow only in tracking layer | Yes |

---

## Test Coverage

```text
pixi run test
376 passed
```

New tests (`tests/test_platform_facade.py`): **12**

| Area | Covered |
|------|---------|
| Facade construction | Yes |
| `reproduce()` workflow delegation | Yes |
| `analyze()` delegation | Yes |
| `discover()` delegation | Yes |
| Disabled discovery | Yes |
| `plan()` delegation | Yes |
| `execute()` planner/coder/runner | Yes |
| Configuration loading | Yes |
| `version()` | Yes |
| `doctor()` | Yes |
| `app.py` backward compatibility | Yes |
| Workflow does not import facade | Yes |

---

## Remaining Work

| Item | Phase |
|------|-------|
| CLI interface (Typer/argparse) | Next |
| Python SDK package layout | Future |
| MCP server | Future |
| REST API | Future |
| Facade result types for partial pipelines | Optional enhancement |

---

## Verdict

**Ready for CLI Interface**

Man1Lab now has a unified platform entry (`Man1Lab`) that composes configuration, tracking, and workflow without embedding business logic. All future interfaces can build on this facade.
