# Runtime Lazy Initialization Audit — Phase 8.3

**Date:** 2026-07-08  
**Scope:** `runtime/lazy/` subsystem, `RuntimeContext` lazy ownership, application resource wiring, profiling integration  
**Verdict:** **Ready for Runtime Cache**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `runtime/lazy/lazy_value.py` | `LazyValue` — initialize once, thread-safe, error propagation |
| `runtime/lazy/lazy_resource.py` | `LazyResource` — named lazy value for runtime ownership |
| `runtime/lazy/resource_registry.py` | `ResourceRegistry` — register, resolve, status reporting |
| `runtime/lazy/__init__.py` | Lazy subsystem exports |
| `application/runtime/resource_wiring.py` | Application-layer factories for runtime resources |
| `tests/test_runtime_lazy_initialization.py` | Lazy subsystem, wiring, profiling, facade, boundary tests (18 tests) |
| `docs/reviews/8.3_runtime_lazy_initialization/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `runtime/context.py` | Owns `ResourceRegistry`; exposes lazy resource accessors |
| `runtime/__init__.py` | Export lazy primitives |
| `runtime/profiling/report.py` | Resource initialized/deferred section in profile report |
| `runtime/profiling/profiler.py` | `build_profile(resource_statuses=...)` |
| `application/runtime/startup_profile.py` | Collect resource statuses after facade init |
| `application/facade.py` | Wire lazy resources; resolve configuration and LLM manager via registry |
| `tests/test_runtime_lifecycle.py` | Updated context expectations; lazy paths in boundary audit |
| `tests/test_runtime_profiling.py` | Assert resource status section in CLI output |
| `docs/reviews/README.md` | Add 8.3 entry |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow / agents / discovery / execution planning | Not migrated to lazy ownership |
| `runtime/profiling/` core timing | Extended report only — no merge with lifecycle |
| Business behavior | Unchanged |
| Persistent runtime / caching | Not introduced |

---

## Architecture

```text
Interfaces (CLI · SDK)
        ↓
Platform Facade (Man1Lab)
        ↓
PlatformRuntime (lifecycle owner)
        ↓
RuntimeContext
        ↓
ResourceRegistry
        ↓
LazyResource → factory (wired in application layer)

runtime/lazy/          ← pure primitives (no business imports)
application/runtime/   ← resource factories (may import configuration, providers, prompt)
runtime/profiling/     ← independent timing + resource status reporting
```

Runtime owns initialization. Business modules do not perform lazy initialization manually.

---

## Lazy Initialization

| Primitive | Responsibility |
|-----------|----------------|
| `LazyValue[T]` | Factory-backed value; `get()` initializes once; `status` is `initialized` or `deferred` |
| `LazyResource[T]` | Named `LazyValue` for registry ownership |
| `ResourceRegistry` | Register named resources; `get()` resolves; `status_entries()` for profiling |

### Requirements

| Requirement | Status |
|-----------|--------|
| Deterministic initialization | Factory invoked on first `get()` only |
| Initialize once | Subsequent `get()` returns cached instance |
| Thread-safe (single-process) | `threading.Lock` around first initialization |
| Error propagation | Factory exceptions stored and re-raised on later access |
| No global singleton | Each `ResourceRegistry` is per-`RuntimeContext` instance |

---

## Runtime Resource Ownership

`RuntimeContext` holds a `ResourceRegistry`. Infrastructure accessors return `LazyResource` handles:

| Resource | Registry key | Wired in |
|----------|--------------|----------|
| Configuration | `configuration` | `wire_runtime_resources()` |
| Prompt Registry | `prompt_registry` | `wire_runtime_resources()` → `PromptLoader` |
| LLM Manager | `llm_manager` | `wire_runtime_resources()` → `LLMManager` |
| Provider Registry | `provider_registry` | `wire_runtime_resources()` → `create_default_registry()` |

`workspace` and `session` remain optional placeholders (not migrated).

Facade resolves configuration during construction (logging, tracker, workspace paths). LLM manager initializes when agents are built. Prompt registry remains deferred until explicitly accessed.

---

## Migration Scope

### Migrated (runtime-owned infrastructure)

- Configuration (`AppSettings`)
- Prompt Registry (`PromptLoader`)
- LLM Manager (`LLMManager`)
- Provider Registry (`ProviderRegistry`)

### Not migrated

- Workflow orchestration
- Execution planning
- Discovery
- Agents

---

## Profiling Integration

`RuntimeProfile.format_report()` appends a **Runtime Resources** section:

```text
Runtime Resources

Configuration ........ initialized
Prompt Registry ...... deferred
LLM Manager .......... initialized
Provider Registry .... initialized
```

`profile_platform_startup()` collects `resource_status_entries()` from the facade runtime context after initialization.

---

## Boundary Verification

### `runtime/lazy/` dependency audit

The lazy package must not import:

- `workflow`
- `providers`
- `execution_planning`
- `agents`

Verified via AST tests in `tests/test_runtime_lazy_initialization.py` and updated lifecycle boundary tests.

### Application wiring boundary

`application/runtime/resource_wiring.py` lives in the application layer and may import configuration, prompt, and provider modules. Business workflow modules are not aware of lazy implementation details.

---

## Dependency Audit

| Module | Imports workflow | Imports providers | Imports agents | Imports lazy |
|--------|------------------|-------------------|----------------|--------------|
| `runtime/lazy/*` | No | No | No | — |
| `runtime/context.py` | No | No | No | Yes |
| `application/runtime/resource_wiring.py` | No | Yes | No | Yes |
| `application/facade.py` | Yes | Yes | Yes | Yes (registry keys only) |

---

## Tests

| Test module | Count | Coverage |
|-------------|-------|----------|
| `tests/test_runtime_lazy_initialization.py` | 18 | LazyValue, LazyResource, registry, wiring, profiling, facade, boundaries |
| `tests/test_runtime_lifecycle.py` | 19 | Updated context + boundary paths |
| `tests/test_runtime_profiling.py` | 15+ | Resource status in CLI profile output |

### Verified behaviors

- Single initialization per lazy resource
- Multiple accesses reuse the same instance
- Initialization errors propagate on repeat access
- Resource registry registration and status reporting
- Profiling report shows initialized vs deferred
- Facade model operations unchanged
- AST dependency boundaries for `runtime/lazy/`

---

## Remaining Work

| Item | Phase |
|------|-------|
| Runtime cache layer | 8.4+ |
| Lazy ownership for workflow / agents | Future |
| Prompt registry consumption from runtime context in agents | Future |
| Persistent runtime | Out of scope |

---

## Verdict

**Ready for Runtime Cache**

Phase 8.3 introduces a reusable runtime lazy initialization subsystem under `runtime/lazy/`. `RuntimeContext` owns lazy infrastructure resources wired from the application layer. Profiling reports distinguish initialized and deferred resources. No persistent runtime, caching beyond instance reuse, workflow changes, or business behavior changes were introduced.
