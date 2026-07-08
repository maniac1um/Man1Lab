# Runtime Lifecycle Audit — Phase 8.2

**Date:** 2026-07-08  
**Scope:** `PlatformRuntime` lifecycle owner, state machine, `RuntimeContext`, facade delegation  
**Verdict:** **Ready for Lazy Loading**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `runtime/state.py` | `RuntimeState` enum and transition validation |
| `runtime/context.py` | `RuntimeContext` ownership container (empty slots) |
| `runtime/runtime.py` | `PlatformRuntime` — startup, shutdown, readiness |
| `runtime/lifecycle/errors.py` | `RuntimeTransitionError`, `RuntimeNotReadyError` |
| `runtime/lifecycle/__init__.py` | Lifecycle error exports |
| `tests/test_runtime_lifecycle.py` | State machine, runtime, facade, boundary tests (18 tests) |
| `docs/reviews/8.2_runtime_lifecycle/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `runtime/__init__.py` | Export lifecycle types alongside profiling |
| `application/facade.py` | Delegate lifecycle to `PlatformRuntime`; `shutdown_runtime()` |
| `application/runtime/startup_profile.py` | Workflow stage checks `is_runtime_ready()` |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| `runtime/profiling/` | Independent — not merged into lifecycle |
| Workflow / agents / providers | No lifecycle awareness added |
| Business behavior | Unchanged |
| Lazy loading / caching / startup optimization | Not introduced |

---

## Architecture

```text
Interfaces (CLI · SDK · future MCP/REST)
        ↓
Platform Facade (Man1Lab)
        ↓
PlatformRuntime (lifecycle owner)
        ↓
RuntimeContext (resource ownership container)

runtime/profiling/  ← independent subsystem (Phase 8.1)
```

`PlatformRuntime` owns **process lifecycle** only. It does not execute paper reproduction or own business workflows.

---

## Lifecycle

| Operation | Behavior |
|-----------|----------|
| `startup()` | `NEW` → `BOOTSTRAPPING` → `READY`; creates `RuntimeContext` |
| `shutdown()` | `READY` → `SHUTTING_DOWN` → `STOPPED`; clears context |
| `is_ready()` | `True` when state is `READY` |
| `context` | Returns context when available; raises `RuntimeNotReadyError` otherwise |

Facade calls `runtime.startup()` when constructed with a `NEW` runtime. Facade exposes `runtime`, `is_runtime_ready()`, and `shutdown_runtime()`.

---

## State Machine

| State | Description |
|-------|-------------|
| `NEW` | Initial state before startup |
| `BOOTSTRAPPING` | Startup in progress |
| `READY` | Runtime ready for use |
| `SHUTTING_DOWN` | Shutdown in progress |
| `STOPPED` | Terminal state |

### Valid transitions

| From | To |
|------|-----|
| `NEW` | `BOOTSTRAPPING` |
| `BOOTSTRAPPING` | `READY`, `STOPPED` |
| `READY` | `SHUTTING_DOWN` |
| `SHUTTING_DOWN` | `STOPPED` |
| `STOPPED` | *(none)* |

Invalid transitions raise `RuntimeTransitionError` with a deterministic message.

---

## Runtime Context

`RuntimeContext` reserves ownership slots for future phases:

| Slot | Phase 8.2 |
|------|-----------|
| `configuration` | `None` — not initialized |
| `llm_manager` | `None` — not initialized |
| `prompt_registry` | `None` — not initialized |
| `workspace` | `None` — not initialized |
| `session` | `None` — not initialized |

`RuntimeContext.create()` returns an empty container. Business objects are not wired in this phase.

---

## Facade Integration

| Facade API | Delegation |
|------------|------------|
| `Man1Lab.__init__(runtime=...)` | Creates or accepts `PlatformRuntime`; starts if `NEW` |
| `platform.runtime` | Returns `PlatformRuntime` |
| `platform.is_runtime_ready()` | `runtime.is_ready()` |
| `platform.shutdown_runtime()` | `runtime.shutdown()` |
| `Man1Lab.profile_startup()` | Unchanged — uses profiling subsystem |

Lifecycle logic lives in `runtime/runtime.py`, not in facade methods beyond delegation.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| `runtime/runtime.py` does not import workflow | ✅ |
| `runtime/state.py` does not import agents/providers | ✅ |
| `runtime/context.py` stdlib/dataclasses only | ✅ |
| Profiling independent from lifecycle | ✅ |
| No global singleton | ✅ |
| No lazy loading | ✅ |
| No caching | ✅ |
| No startup optimization | ✅ |

Startup profiling orchestration remains in `application/runtime/startup_profile.py` (application layer).

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `runtime/runtime.py` | `runtime.context`, `runtime.state`, `runtime.lifecycle.errors` |
| `runtime/state.py` | `runtime.lifecycle.errors` |
| `runtime/context.py` | stdlib |
| `runtime/profiling/*` | stdlib + `runtime.profiling.*` only |
| `application/facade.py` | `runtime.runtime`, `runtime.state` |
| Business modules | Must not import runtime internals (unchanged) |

---

## Test Coverage

**`tests/test_runtime_lifecycle.py`**

| Test | Coverage |
|------|----------|
| `test_allowed_transitions` | State machine table |
| `test_validate_transition_rejects_invalid` | Invalid transition error |
| `test_startup_transitions_to_ready` | Happy path startup |
| `test_shutdown_transitions_to_stopped` | Happy path shutdown |
| `test_startup_from_non_new_raises` | Double startup guard |
| `test_shutdown_before_ready_raises` | Premature shutdown guard |
| `test_shutdown_twice_raises` | Double shutdown guard |
| `test_context_unavailable_before_startup` | `RuntimeNotReadyError` |
| `test_context_unavailable_after_shutdown` | Context cleared |
| `test_no_singleton_instances` | No singleton |
| `test_create_returns_empty_container` | Context slots |
| `test_facade_starts_provided_runtime` | Facade delegation |
| `test_facade_creates_runtime_when_not_provided` | Default runtime |
| `test_facade_shutdown_delegates_to_runtime` | Shutdown delegation |
| `test_runtime_core_has_no_forbidden_imports` | AST boundary |
| `test_profiling_remains_independent` | Profiling separation |

**Full suite:** 647 tests passing (629 + 18 new).

---

## Remaining Work

| Item | Phase |
|------|-------|
| Lazy loading of facade components | 8.3+ |
| Wire `RuntimeContext` slots to real resources | Future |
| Persistent runtime / session management | Future |
| Interactive console | Out of scope |
| Startup optimization | Out of scope |

---

## Verdict

**Ready for Lazy Loading**

Phase 8.2 establishes `PlatformRuntime` as the reusable process lifecycle owner with a validated state machine and empty `RuntimeContext` container. The Platform Facade delegates lifecycle operations without embedding lifecycle logic. Profiling remains independent under `runtime/profiling/`. No lazy loading, caching, or startup optimization was introduced.
