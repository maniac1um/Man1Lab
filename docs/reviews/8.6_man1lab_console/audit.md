# Man1Lab Console Audit — Phase 8.6

**Date:** 2026-07-08  
**Scope:** Interactive `Man1Lab Console` on completed Runtime architecture  
**Verdict:** **Ready for Runtime Cleanup & v1.2.3 Release**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `runtime/console/platform.py` | `ConsolePlatform` protocol (facade surface) |
| `runtime/console/command.py` | `ConsoleCommand`, `ConsoleContext` |
| `runtime/console/registry.py` | `CommandRegistry` — register and resolve commands |
| `runtime/console/parser.py` | `parse_command_line()` — shlex-based parsing |
| `runtime/console/renderer.py` | `ConsoleRenderer` — banner, help, output |
| `runtime/console/builtins.py` | Built-in command handlers and registration |
| `runtime/console/console.py` | `Man1LabConsole`, `run_console()` — main loop |
| `runtime/console/__init__.py` | Console exports |
| `tests/test_man1lab_console.py` | Console framework, session, facade, CLI, boundary tests (22 tests) |
| `docs/reviews/8.6_man1lab_console/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `interfaces/cli/app.py` | `man1lab` with no args enters interactive console |
| `application/facade.py` | `run_startup_profile()` instance wrapper for console |
| `docs/reviews/README.md` | Add 8.6 entry |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow / Discovery / Execution Planning | No changes |
| Runtime ownership / lifecycle | Unchanged |
| Business reproduction logic | Unchanged |

---

## Architecture

```text
man1lab (no args)
        ↓
Man1LabConsole
        ├── CommandRegistry
        ├── Parser
        ├── Renderer
        └── Built-in commands
                ↓
        Platform Facade (Man1Lab)
                ↓
        PlatformRuntime / RuntimeSession / RuntimeContext
                ↓
        Business operations (analyze, discover, plan, …)
```

The Console is a **new interface layer** under `runtime/console/`. It does not modify workflow or runtime ownership.

---

## Console Framework

| Component | Responsibility |
|-----------|----------------|
| `CommandRegistry` | Register commands; resolve by name (no central if/else dispatch) |
| `ConsoleCommand` | Immutable name, help text, handler |
| `parse_command_line` | Split user input into command + args |
| `ConsoleRenderer` | Banner, help, stdout/stderr output |
| `Man1LabConsole` | Read-eval loop, Ctrl+C / EOF handling, session open on start |

### Initial commands

| Command | Facade delegation |
|---------|-------------------|
| `help` | Registry command list |
| `doctor` | `platform.doctor()` |
| `profile` | `platform.run_startup_profile()` |
| `model [list\|current\|use]` | `list_models()`, `current_model()`, `use_model()` |
| `clear` | Renderer screen clear |
| `exit` | Close session, exit loop |
| `analyze <paper.pdf>` | `platform.analyze()` + session placeholders |
| `discover` | `platform.discover()` using session analysis |
| `plan` | `platform.plan()` using session analysis + discovery |

---

## Session Integration

On console start, `RuntimeSession.open()` is called when state is `NEW`.

| Command | Session update |
|---------|----------------|
| `analyze paper.pdf` | `workspace.current_paper`, `workspace.current_analysis` |
| `discover` | Uses `current_paper` / `current_analysis`; sets `current_discovery` |
| `plan` | Uses `current_analysis` + `current_discovery`; sets `current_strategy` |

No persistence — memory only.

---

## Command Registry

Commands are registered via `register_builtin_commands()`:

```python
registry.register(ConsoleCommand("analyze", "...", _cmd_analyze))
```

`Man1LabConsole.dispatch()` and `run()` resolve handlers through the registry.

---

## Console UX

Running `man1lab` with no subcommand enters the console and displays:

- Version
- Workspace
- Active model
- Runtime state
- Session state

Prompt: `man1lab> `

- **Ctrl+C** — prints "Interrupted.", continues loop
- **EOF** — closes session, prints "Goodbye.", exits

---

## Boundary Verification

### Console must NOT

| Rule | Status |
|------|--------|
| Import workflows directly | Verified — AST tests pass |
| Import providers directly | Verified |
| Manage runtime resources | Verified — uses facade only |
| Manage lifecycle | Verified — session open/close via facade APIs |

### Business execution

All commands delegate to `Man1Lab` facade methods. No duplicated CLI command logic.

---

## Dependency Audit

| Module | Imports workflow | Imports providers | Imports facade |
|--------|------------------|-------------------|----------------|
| `runtime/console/*` | No | No | No (protocol + injection) |
| `interfaces/cli/app.py` | No | No | Yes (via `get_platform()`) |

Console receives platform instance from CLI entry point. Built-in handlers call protocol methods on the injected platform.

---

## Tests

| Test class | Coverage |
|------------|----------|
| `ParserTest` | Command-line parsing |
| `CommandRegistryTest` | Registration, duplicates, built-ins |
| `ConsoleDispatchTest` | help, exit, doctor, profile, unknown |
| `SessionIntegrationTest` | Session open, analyze/discover/plan placeholders |
| `ConsoleRunLoopTest` | EOF, Ctrl+C, banner |
| `FacadeConsoleIntegrationTest` | Real `Man1Lab` instance |
| `CLIConsoleEntryTest` | `man1lab` with no args |
| `ConsoleBoundaryTest` | AST forbidden imports |

**765 tests passing** (full suite).

---

## Remaining Work

| Item | Phase |
|------|-------|
| Runtime cleanup | 8.7 / v1.2.3 |
| `reproduce` / `execute` console commands | Future |
| Conversation history | Future |
| Workspace persistence | Future |
| MCP / REST interactive interfaces | Future |

---

## Verdict

**Ready for Runtime Cleanup & v1.2.3 Release**

Phase 8.6 introduces the Man1Lab Console as the primary interactive interface on top of the completed Runtime architecture. The command registry pattern avoids large dispatch branches. Session placeholders integrate analyze → discover → plan workflows in memory. Runtime ownership, business workflows, and reproduction logic remain unchanged.
