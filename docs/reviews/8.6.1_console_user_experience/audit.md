# Console User Experience Audit — Phase 8.6.1

**Date:** 2026-07-09  
**Scope:** Man1Lab Console UX enhancement (v1.2.3 → v1.2.4 RC)  
**Verdict:** **Ready for v1.2.4 RC**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `runtime/session/workspace_store.py` | Runtime-owned `WorkspaceArtifactStore` — persist/load canonical artifacts |
| `runtime/session/workspace_resume.py` | Resume hydration, artifact status, deterministic diagnostics |
| `runtime/console/input.py` | Optional `prompt_toolkit` input with fallback |
| `runtime/console/renderer.py` | ASCII banner, guided success output, workflow help |
| `runtime/console/builtins.py` | Pipeline commands, persistence hooks, guided UX |
| `runtime/console/console.py` | Default enhanced input via `create_console_input_fn` |
| `tests/test_console_workspace.py` | Persistence and resume utility tests |
| `tests/test_man1lab_console.py` | Extended console UX, pipeline, banner, boundary tests |
| `docs/releases/v1.2.4.md` | Release notes |
| `docs/reviews/8.6.1_console_user_experience/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `application/version.py` | `PLATFORM_VERSION` → 1.2.4 |
| `pyproject.toml` | Package version → 1.2.4 |
| `runtime/session/__init__.py` | Export workspace store and resume utilities |
| `runtime/session/workspace.py` | Docstring — session references + disk hydration |
| `tests/test_platform_facade.py` | Version assertion |
| `CHANGELOG.md` | v1.2.4 entry |
| `docs/CURRENT_STATUS.md` | v1.2.4 capabilities and limitations |
| `docs/GETTING_STARTED.md` | Console workflow, persistence, pipeline commands |
| `docs/architecture/RUNTIME.md` | Session workspace persistence and resume |
| `docs/architecture/ARCHITECTURE.md` | Console UX and workspace layout |
| `docs/README.md` | v1.2.4 navigation |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow / Discovery / Execution Planning | No logic changes |
| Platform Facade business methods | Unchanged signatures |
| Runtime lifecycle state machine | Unchanged |
| Execution engine | Not implemented (reserved commands only) |

---

## Architecture

```text
Man1LabConsole (presentation)
        ├── CommandRegistry / Parser / Renderer / Input
        └── Built-in commands
                ↓
        Platform Facade (Man1Lab)
                ↓
        RuntimeSession → SessionWorkspace (in-memory references)
                ↓
        WorkspaceArtifactStore (runtime-owned persistence)
                ↓
        workspace/{analysis,discovery,planning}/
```

Console remains **presentation only**. Persistence is **runtime-owned** via `WorkspaceArtifactStore`. Business modules do not know file paths.

---

## Dependency Audit

| Dependency | Console usage | Boundary |
|------------|---------------|----------|
| `runtime.session.workspace_store` | builtins persistence | Runtime-owned; uses validation builders for load |
| `runtime.session.workspace_resume` | builtins hydration/diagnostics | Runtime-owned |
| `validation.*` | Load persisted JSON into canonical models | Validation layer only; no workflow imports |
| `prompt_toolkit` | Optional input enhancement | Try/import fallback; not required |

AST boundary test confirms `runtime/console/` has no imports from `workflow`, `discovery`, `execution_planning`, `agents`, or `providers`.

---

## Workspace Layout

```text
{workspace_root}/
  analysis/
    analysis.json      # PaperReproductionAnalysis (canonical JSON)
    analysis.md        # Human-readable summary
  discovery/
    resources.json     # ResearchResourceDiscovery
    summary.md
  planning/
    execution_strategy.json
    summary.md
```

Writes occur after successful console commands. Session workspace is hydrated from disk on session open and before stage commands when references are absent.

---

## Console UX

| Feature | Implementation |
|---------|----------------|
| Guided output | `ConsoleRenderer.render_command_success()` |
| Workflow help | `render_help()` workflow and pipeline sections |
| Pipeline `plan-all` | Facade `analyze` → `discover` → `plan` |
| Reserved `execute-all` / `reproduce` | User-facing messages; no execution logic |
| Startup banner | ASCII MAN1LAB + `platform.version()` |
| Input enhancement | `create_console_input_fn()` with `prompt_toolkit` fallback |

---

## Persistence & Resume Strategy

| Stage | Persist | Resume behavior |
|-------|---------|-----------------|
| analyze | `analysis/` | Required for discover/plan |
| discover | `discovery/` | Skips re-analyze when `analysis.json` exists |
| plan | `planning/` | Skips prior stages when artifacts exist |
| execute | — | Design only; no restore implementation |

Diagnostics (`diagnose_for_discover`, `diagnose_for_plan`) return recommended commands when artifacts are missing.

---

## Test Coverage

| Area | Tests |
|------|-------|
| Guided output | `GuidedOutputTest` |
| Pipeline commands | `PipelineCommandTest` |
| Workspace persistence | `WorkspacePersistenceConsoleTest`, `test_console_workspace.py` |
| Resume loading | `ResumeConsoleTest`, `WorkspaceResumeTest` |
| Banner | `ConsoleRunLoopTest::test_banner_shows_runtime_details` |
| Command registry | `CommandRegistryTest` (14 commands) |
| Facade delegation | `SessionIntegrationTest`, `FacadeConsoleIntegrationTest` |
| Input fallback | `ConsoleInputTest` |
| AST boundaries | `ConsoleBoundaryTest` |

**784** unit tests at phase completion; **826** at v1.2.4 RC (full suite).

---

## Remaining Work (post v1.2.4 RC)

| Item | Target |
|------|--------|
| `execute-all` implementation | Execution engine milestone |
| Console `reproduce` wiring | After execute-all |
| Execution artifact restore | v1.3+ |
| `prompt_toolkit` as optional extra in packaging | Packaging polish |
| GUI / daemon session scopes | Future interfaces |

---

## Verdict

Architecture constraints preserved. Console is presentation-only. Persistence is runtime-owned. Facade delegation unchanged. **Ready for v1.2.4 RC.**
