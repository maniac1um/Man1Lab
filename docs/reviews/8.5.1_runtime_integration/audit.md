# Runtime Integration Audit — Phase 8.5.1

**Date:** 2026-07-08  
**Scope:** Consolidate infrastructure resource ownership through Runtime; eliminate direct construction in business modules  
**Verdict:** **Ready for Interactive Console**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `application/runtime/accessors.py` | `RuntimeInfrastructure` — canonical resource resolution through `RuntimeResourceManager` |
| `tests/support/prompt.py` | `default_prompt_builder()` — test-only helper for isolated agent construction |
| `tests/test_runtime_integration.py` | Ownership, facade delegation, workflow behavior, boundary tests (32 tests) |
| `docs/reviews/8.5.1_runtime_integration/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `application/facade.py` | Resolve configuration, prompt registry, and LLM manager via `RuntimeInfrastructure` |
| `agents/reader.py` | Require injected `PromptBuilder`; remove `PromptLoader()` default |
| `agents/planner.py` | Require injected `PromptBuilder` |
| `agents/coder.py` | Require injected `PromptBuilder` |
| `agents/reviewer.py` | Require injected `PromptBuilder`; expose `prompt_builder` for composition |
| `planning/patch_planner.py` | Require injected `PromptBuilder` |
| `workflow/orchestrator.py` | Default `PatchPlanner` shares reviewer's injected `prompt_builder` |
| `llm/factory.py` | Require runtime-owned `LLMManager` parameter; no direct construction |
| `runtime/context.py` | Expose `provider_registry` lazy resource property |
| `tests/test_*.py` | Inject `default_prompt_builder()` where agents are constructed in isolation |
| `docs/reviews/README.md` | Add 8.5.1 entry |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow execution logic | Behavior preserved; composition requires explicit prompt injection |
| Interactive console | Not implemented |
| Paper reproduction logic | Unchanged |
| `runtime/lazy/`, `runtime/resources/`, `runtime/session/` | Core subsystems unchanged |

---

## Architecture

```text
Interfaces (CLI · SDK · future Console · MCP · REST)
        ↓
Platform Facade (Man1Lab)
        ↓
PlatformRuntime
        ↓
RuntimeContext
        ↓
RuntimeResourceManager
        ↓
Infrastructure Resources
  ├── Configuration (AppSettings)
  ├── Prompt Registry (PromptLoader)
  ├── Provider Registry (ProviderRegistry)
  └── LLM Manager (LLMManager)
        ↓
Business Workflows (receive injected ports/builders)
```

`RuntimeInfrastructure` in the application layer is the single composition-root accessor for resolving runtime-owned resources.

---

## Migration Scope

### Migrated to Runtime ownership

| Resource | Resolution path |
|----------|-----------------|
| Configuration | `RuntimeInfrastructure.configuration()` |
| Prompt Registry | `RuntimeInfrastructure.prompt_registry()` → facade `PromptBuilder` |
| LLM Manager | `RuntimeInfrastructure.llm_manager()` → facade LLM ports |
| Provider Registry | Wired via `wire_runtime_resources()`; shared with LLM manager |

### Removed from business modules

| Pattern | Location | Resolution |
|---------|----------|------------|
| `PromptBuilder(PromptLoader())` defaults | Agents, `PatchPlanner` | Required `prompt_builder` injection |
| `LLMManager(_legacy_llm_config())` | `llm/factory.py` | Factory requires `manager` parameter |
| `PatchPlanner()` without builder | `WorkflowOrchestrator` | Uses `reviewer.prompt_builder` |

### Intentionally retained (provider-layer tests)

| Pattern | Location | Reason |
|---------|----------|--------|
| `LLMManager(...)` direct construction | Provider unit tests | Tests provider infrastructure in isolation |
| `PromptLoader(...)` in tests | `tests/support/prompt.py` | Test fixtures only |

---

## Integration Strategy

1. **Composition root** — `Man1Lab.__init__` wires resources via `wire_runtime_resources()` and resolves them through `RuntimeInfrastructure`.
2. **Injection downstream** — Facade builds one `PromptBuilder` from runtime-owned `PromptLoader` and injects it into all agents and orchestrator components.
3. **No business ownership** — Agents and planners accept `PromptBuilder` as a required dependency; they never construct `PromptLoader`.
4. **Workflow composition** — `WorkflowOrchestrator` shares the reviewer's injected `prompt_builder` when creating a default `PatchPlanner`.
5. **Legacy factory** — `llm/factory.py` adapts a runtime-provided `LLMManager` to `LLMProvider`; it does not own manager lifecycle.

---

## Ownership Verification

| Check | Result |
|-------|--------|
| Facade resolves configuration through runtime | Yes — `RuntimeInfrastructure` |
| Facade resolves prompt registry through runtime | Yes — single `PromptLoader` instance |
| All facade-built agents share runtime `PromptLoader` | Yes — verified by identity tests |
| LLM manager shares runtime provider registry | Yes — verified by identity tests |
| Agents contain `PromptLoader()` construction | No — AST/static checks pass |
| `llm/factory.py` constructs `LLMManager` | No — requires injected manager |
| Duplicated lazy-loading in business modules | None found |
| Global singleton patterns for infrastructure | None introduced |

---

## Boundary Verification

### Runtime core

`runtime/*` does not import workflow, agents, or providers (except via application wiring).

### Business modules

Agents and `PatchPlanner` import `PromptBuilder` type only — not runtime internals.

### Application layer

`application/runtime/accessors.py` and `resource_wiring.py` may import configuration, prompt, and provider modules to register factories.

### Workflow

`WorkflowOrchestrator` does not import runtime; it receives injected agents with pre-wired `PromptBuilder`.

---

## Dependency Audit

| Module | Imports runtime | Constructs PromptLoader | Constructs LLMManager |
|--------|-----------------|-------------------------|------------------------|
| `application/facade.py` | Via accessors/wiring | No (resolves from runtime) | No (resolves from runtime) |
| `agents/*` | No | No | No |
| `planning/patch_planner.py` | No | No | No |
| `workflow/orchestrator.py` | No | No | No |
| `llm/factory.py` | No | No | No |
| `application/runtime/accessors.py` | Yes | No (resolves) | No (resolves) |

No circular dependencies: runtime core does not import `application`.

---

## Test Coverage

| Test module | Tests | Coverage |
|-------------|-------|----------|
| `tests/test_runtime_integration.py` | 32 | Provider registry property, agent prompt ownership, LLM manager sharing, workflow behavior, boundaries |
| Updated agent/workflow tests | — | `default_prompt_builder()` injection for isolated construction |

### Verified behaviors

- Business modules resolve infrastructure through Runtime when used via facade
- Runtime remains single owner of configuration, prompt, provider, and LLM resources
- All facade agents share one runtime-owned `PromptLoader`
- Existing workflows behave identically (741 tests passing)
- No behavior regressions in profile startup, model operations, or lifecycle
- AST dependency boundaries valid
- No circular runtime ↔ application dependencies

---

## Remaining Work

| Item | Phase |
|------|-------|
| Interactive console on `RuntimeSession` | 8.6+ |
| Conversation history | Future |
| Workspace persistence | Future |
| Migrate provider unit tests to runtime fixtures (optional) | Low priority |

---

## Verdict

**Ready for Interactive Console**

Phase 8.5.1 completes Runtime architecture integration. Infrastructure resources are owned exclusively by `RuntimeResourceManager` and resolved through `RuntimeInfrastructure` at the composition root. Business modules receive injected dependencies and no longer construct or manage infrastructure lifecycle. Resource ownership is consistent across the platform, and the Runtime substrate is ready to support a long-lived Interactive Console without further architectural refactoring.
