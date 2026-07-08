# CLI Foundation Audit — Phase 1

**Date:** 2026-06-29  
**Scope:** `interfaces/cli/`, Typer CLI over Platform Facade  
**Verdict:** **Ready for Python SDK Interface**

---

## Command Tree

```text
man1lab [--version|-V] [--help]
├── reproduce <paper.pdf>
├── analyze <paper.pdf> [--output|-o PATH]
├── discover <paper.pdf> [--output|-o PATH]
├── plan <paper.pdf> [--output|-o PATH]
├── execute --strategy|-s PATH --analysis|-a PATH
├── doctor
├── config
└── version
```

| Command | Facade method |
|---------|---------------|
| `reproduce` | `Man1Lab.reproduce()` |
| `analyze` | `Man1Lab.analyze()` |
| `discover` | `Man1Lab.discover()` |
| `plan` | `Man1Lab.plan_from_paper()` |
| `execute` | `Man1Lab.execute_from_paths()` |
| `doctor` | `Man1Lab.doctor()` |
| `config` | `Man1Lab.configuration()` |
| `version` / `--version` | `Man1Lab.version()` / `PLATFORM_VERSION` |

---

## Implemented Files

| File | Purpose |
|------|---------|
| `interfaces/cli/app.py` | Typer root app and command registration |
| `interfaces/cli/common.py` | Facade access, exit codes, error handling |
| `interfaces/cli/commands/*.py` | One module per command |
| `interfaces/sdk/__init__.py` | Reserved (future) |
| `interfaces/mcp/__init__.py` | Reserved (future) |
| `interfaces/api/__init__.py` | Reserved (future) |
| `tests/test_cli.py` | CLI tests (12 tests) |

## Files Modified

| File | Change |
|------|--------|
| `application/facade.py` | Added `plan_from_paper()`, `execute_from_paths()` for CLI |
| `pixi.toml` | Added `typer` dependency and `man1lab` task |
| `README.md` | CLI usage and quick start |
| `docs/architecture/ARCHITECTURE.md` | CLI under Platform Interface Layer |
| `docs/CURRENT_STATUS.md` | CLI documented |

---

## Facade Relationship

```text
CLI (Typer)
    ↓
interfaces/cli/common.get_platform()
    ↓
Man1Lab
    ↓
TrackedWorkflowOrchestrator / capability methods
```

CLI imports **only** `application` (via `common.get_platform()`) and `typer`. No direct workflow or capability imports.

---

## Workflow Isolation

| Module | Imports workflow? |
|--------|-------------------|
| `interfaces/cli/*` | No |
| `workflow/orchestrator.py` | No facade import |

AST audit in `tests/test_cli.py` enforces forbidden roots: `workflow`, `agents`, `discovery`, `execution_planning`, `tracking`, `hydra`, `configuration`.

---

## Typer Integration

- Root app: `interfaces/cli/app.py`
- Commands registered via `app.command(...)(module.command)`
- Global `--version` / `-V` on root callback
- Per-command `--help`
- `pixi run man1lab <command>` entry via pixi task

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Platform failure (`EXIT_PLATFORM_FAILURE`) |
| `2` | Invalid arguments (`EXIT_INVALID_ARGUMENTS`) |

Errors print to stderr without stack traces by default.

---

## Help Output

```bash
pixi run man1lab --help
pixi run man1lab reproduce --help
pixi run man1lab --version
```

---

## Test Coverage

```text
pixi run test
388 passed
```

New tests (`tests/test_cli.py`): **12**

| Area | Covered |
|------|---------|
| Command registration / root help | Yes |
| Command help | Yes |
| `--version` flag | Yes |
| `version` command facade delegation | Yes |
| `reproduce` delegation | Yes |
| Missing paper invalid arguments | Yes |
| `analyze` delegation | Yes |
| `doctor` success / failure exit codes | Yes |
| `config` delegation | Yes |
| Workflow isolation (AST audit) | Yes |
| Facade-only imports | Yes |

---

## Remaining Work

| Item | Phase |
|------|-------|
| Python SDK package (`interfaces/sdk/`) | Next |
| MCP server | Future |
| REST API | Future |
| Global `man1lab` console script (pip install) | Optional |
| Shell completion | Optional |

---

## Verdict

**Ready for Python SDK Interface**

Users can run `pixi run man1lab reproduce paper.pdf`, `analyze`, `doctor`, and `version` through a thin Typer CLI that delegates exclusively to the Platform Facade.
