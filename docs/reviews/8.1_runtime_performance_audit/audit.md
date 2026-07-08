# Runtime Performance Audit — Phase 8.1

**Date:** 2026-07-08  
**Scope:** Runtime profiling foundation (`runtime/profiling/`) and `man1lab profile`  
**Verdict:** **Ready for Runtime Lifecycle Skeleton**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `runtime/__init__.py` | Runtime layer package entry |
| `runtime/profiling/__init__.py` | Profiling subsystem exports |
| `runtime/profiling/measurements.py` | `StageMeasurement` frozen record |
| `runtime/profiling/timeline.py` | `RuntimeTimeline` ordered stage collection |
| `runtime/profiling/profiler.py` | `RuntimeProfiler` — `begin_stage()`, `end_stage()`, `measure()` |
| `runtime/profiling/report.py` | `RuntimeProfile` report formatting |
| `application/runtime/startup_profile.py` | Startup profiling orchestration |
| `application/runtime/__init__.py` | Application runtime exports |
| `interfaces/cli/commands/profile.py` | `man1lab profile` command |
| `tests/test_runtime_profiling.py` | Profiler, report, CLI, boundary tests (15 tests) |
| `docs/reviews/8.1_runtime_performance_audit/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `application/facade.py` | `Man1Lab.profile_startup()` static method |
| `interfaces/cli/app.py` | Register `profile` command |
| `pyproject.toml` | Include `runtime*` package |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow / agents / providers | No timing logic added |
| Facade `__init__` | No lazy loading or optimization |
| Business modules | No instrumentation hooks yet |

---

## Architecture

```text
CLI (man1lab profile)
        ↓
Platform Facade (Man1Lab.profile_startup())
        ↓
Application Runtime (startup_profile.py)
        ↓
Runtime Profiling (runtime/profiling/)
```

The **Runtime layer** owns profiling primitives. Application runtime orchestrates startup measurement. Business modules do not implement timing logic in this phase.

---

## Runtime Layer

| Component | Responsibility |
|-----------|----------------|
| `RuntimeProfiler` | Hierarchical stage recording; no global state |
| `StageMeasurement` | Immutable stage name, duration, order, children |
| `RuntimeTimeline` | Deterministic ordered stage collection |
| `RuntimeProfile` | Wall-clock total + formatted report |

### APIs

| API | Behavior |
|-----|----------|
| `begin_stage(name)` | Start nested or root stage |
| `end_stage()` | Close stage; return `StageMeasurement` |
| `measure(name)` | Context manager wrapping begin/end |
| `build_profile()` | `RuntimeProfile` with timeline + total ms |
| `build_timeline()` | `RuntimeTimeline` without total |

---

## Measurement Model

| Property | Detail |
|----------|--------|
| Timing source | `time.perf_counter()` |
| Duration unit | Milliseconds (`duration_ms`) |
| Ordering | Monotonic `order` assigned at `begin_stage()` |
| Nesting | Child stages stored on parent `StageMeasurement.children` |
| Determinism | Root stages sorted by `order`; DFS flatten for nested |
| Global state | None — new `RuntimeProfiler` per session |

---

## CLI Integration

| Command | Delegation |
|---------|------------|
| `man1lab profile` | `Man1Lab.profile_startup()` → `profile_platform_startup()` |

### Startup stages profiled

| Stage | Measured activity |
|-------|-------------------|
| Import | `configuration.bootstrap`, `application.facade` module load |
| Configuration | `initialize_app_configuration()` |
| Facade | `Man1Lab(...)` construction (tracking forced to `noop` to avoid MLflow side effects) |
| Workflow | Orchestrator readiness probe |

### Example output

```text
Runtime Profile

Import .................. 12.3 ms
Configuration ........... 45.6 ms
Facade .................. 89.0 ms
Workflow ................ 0.1 ms

Total ................... 146.9 ms
```

CLI uses the Runtime profiling subsystem for formatting only — no inline timing in CLI code.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| `runtime/profiling/` does not import workflow | ✅ AST audit |
| `runtime/profiling/` does not import execution_planning | ✅ |
| `runtime/profiling/` does not import providers | ✅ |
| `runtime/profiling/` does not import agents | ✅ |
| `runtime/profiling/` does not import CLI | ✅ |
| No global profiler singleton | ✅ |
| No lazy loading introduced | ✅ |
| No caching introduced | ✅ |
| No startup optimization | ✅ |

Startup orchestration lives in `application/runtime/` (application layer), which may import facade and configuration — not in `runtime/profiling/` itself.

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `runtime/profiling/*` | stdlib only (`time`, `dataclasses`, `contextlib`) |
| `application/runtime/startup_profile.py` | `runtime.profiling`, `importlib`, facade, configuration |
| `interfaces/cli/commands/profile.py` | `application.facade`, `typer` |
| `application/facade.py` | `runtime.profiling.report`, `application.runtime` |

Forbidden in Runtime profiling: workflow, agents, providers, CLI.

---

## Test Coverage

**`tests/test_runtime_profiling.py`**

| Test | Coverage |
|------|----------|
| `test_measure_records_stage` | `measure()` context manager |
| `test_begin_and_end_stage` | Manual begin/end |
| `test_nested_stages` | Parent/child hierarchy |
| `test_measurement_ordering_is_deterministic` | Order counter |
| `test_end_stage_without_begin_raises` | Error handling |
| `test_total_includes_wall_clock` | Total vs stage duration |
| `test_flattened_measurements` | DFS flatten |
| `test_format_report_contains_expected_sections` | Report output |
| `test_format_report_is_deterministic` | Stable structure |
| `test_facade_profile_startup_returns_profile` | Four startup stages |
| `test_stage_durations_are_non_negative` | Duration validation |
| `test_profile_command_output` | CLI integration |
| `test_profile_delegates_to_facade` | CLI delegation |
| `test_runtime_profiling_has_no_forbidden_imports` | AST boundary |
| `test_profiler_has_no_global_singleton` | No singleton |

**Full suite:** 629 tests passing (614 + 15 new).

---

## Remaining Work

| Item | Phase |
|------|-------|
| Runtime Lifecycle Skeleton | 8.2 |
| Instrument business stages through Runtime APIs | Future |
| Persistent runtime profiling storage | Future |
| Startup time optimization | Out of scope — explicitly deferred |
| Lazy loading / caching | Out of scope — explicitly deferred |
| Public `touch_runtime()` instead of orchestrator probe | Optional polish |

---

## Verdict

**Ready for Runtime Lifecycle Skeleton**

Phase 8.1 delivers a reusable, hierarchy-aware Runtime profiling subsystem independent of workflow, agents, and providers. `man1lab profile` exercises startup measurement through the Platform Facade. No optimization, lazy loading, caching, or persistent runtime was introduced.
