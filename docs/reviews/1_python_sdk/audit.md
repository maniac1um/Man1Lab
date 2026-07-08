# Python SDK Audit — Phase 1

**Date:** 2026-06-29  
**Scope:** `interfaces/sdk/`, `man1lab/` public package  
**Verdict:** **Ready for Package Distribution**

---

## SDK Architecture

```text
External Program (Cursor, Codex, Claude Code, integrations)
        ↓
man1lab.Man1Lab          ← public import path
        ↓
interfaces.sdk.client.Man1Lab
        ↓
application.facade.Man1Lab
        ↓
WorkflowOrchestrator
```

The SDK is a **pure delegation layer** — no business logic, no workflow logic, no duplicated implementations.

---

## Implemented Files

| File | Purpose |
|------|---------|
| `interfaces/sdk/client.py` | `Man1Lab` SDK client (facade delegation) |
| `interfaces/sdk/__init__.py` | SDK exports |
| `man1lab/__init__.py` | Public package (`from man1lab import Man1Lab`) |
| `tests/test_sdk.py` | SDK tests (16 tests) |
| `docs/reviews/python_sdk_phase_1/audit.md` | This audit |

## Files Modified

| File | Change |
|------|--------|
| `README.md` | Python SDK usage section |
| `docs/GETTING_STARTED.md` | SDK quick start |
| `docs/architecture/ARCHITECTURE.md` | SDK under Platform Interface Layer |
| `docs/CURRENT_STATUS.md` | SDK documented |

---

## Public API

```python
from man1lab import Man1Lab

client = Man1Lab()

client.reproduce(paper_path=None)
client.analyze(paper_path)
client.discover(analysis=None, paper_path=None)
client.plan(analysis=None, discovery=None, paper_path=None)
client.execute(execution_strategy=None, analysis=None, strategy_path=None, analysis_path=None)
client.doctor()
client.version()
client.configuration()
```

Also exported: `PLATFORM_VERSION`, `DoctorReport`, `ExecuteResult`.

| SDK method | Facade delegation |
|------------|-------------------|
| `reproduce()` | `facade.reproduce()` |
| `analyze()` | `facade.analyze()` |
| `discover()` | `facade.discover()` |
| `plan(paper_path=...)` | `facade.plan_from_paper()` |
| `plan(analysis, discovery)` | `facade.plan()` |
| `execute(strategy, analysis)` | `facade.execute()` |
| `execute(strategy_path=..., analysis_path=...)` | `facade.execute_from_paths()` |
| `doctor()` | `facade.doctor()` |
| `version()` | `facade.version()` |
| `configuration()` | `facade.configuration()` |

---

## Dependency Audit

| Module | Imports |
|--------|---------|
| `interfaces/sdk/client.py` | `application.facade` only (lazy at init) |
| `interfaces/sdk/__init__.py` | `application.facade`, `application.version`, `interfaces.sdk.client` |
| `man1lab/__init__.py` | `interfaces.sdk` only |

| Forbidden | SDK imports? |
|-----------|--------------|
| `workflow` | No |
| `interfaces.cli` | No |
| `agents` | No |
| `discovery` | No |
| `execution_planning` | No |
| `tracking` | No (via SDK) |
| `hydra` | No |

AST isolation tests enforce SDK module boundaries.

---

## Facade Relationship

- SDK `Man1Lab` composes `application.facade.Man1Lab` via `_facade`
- Constructor kwargs pass through unchanged (settings, logging, orchestrator injection for tests)
- Return types are facade artifacts unchanged

---

## Import Examples

```python
# Recommended public import
from man1lab import Man1Lab

# Internal / monorepo import
from interfaces.sdk import Man1Lab

# Package version
import man1lab
print(man1lab.__version__)  # 1.2.0
```

Source checkout usage requires `PYTHONPATH=.` (or `pixi run`).

---

## Test Coverage

```text
pixi run test
404 passed
```

New tests (`tests/test_sdk.py`): **16**

| Area | Covered |
|------|---------|
| `from man1lab import Man1Lab` | Yes |
| `from interfaces.sdk import Man1Lab` | Yes |
| Package `__version__` | Yes |
| Construction delegates to facade | Yes |
| All public method delegation | Yes |
| Workflow isolation (AST) | Yes |
| `man1lab` package re-exports SDK | Yes |

---

## Remaining Work

| Item | Phase |
|------|-------|
| `pyproject.toml` / pip installable package | Next (Package Distribution) |
| Console entry points | Optional |
| Published PyPI distribution | Future |
| MCP server using SDK | Future |

---

## Verdict

**Ready for Package Distribution**

The Python SDK provides a stable `from man1lab import Man1Lab` programmatic API that delegates exclusively to the Platform Facade with no workflow or business logic duplication.
