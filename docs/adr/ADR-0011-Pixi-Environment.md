# ADR-0011 — Pixi Environment

## Status

Accepted

## Date

2026-06-30

## Context

Man1Lab v1.x documented installation via `pip install -r requirements.txt` and implicit system Python. This approach lacks reproducible lockfiles, separates dev dependencies ad hoc (pytest was not in requirements), and does not standardize the developer workflow across platforms.

[Pixi](https://pixi.sh/) provides a conda-forge–backed, lockfile-driven Python environment manager suitable for scientific ML stacks (Docling transitive dependencies). Man1Lab is not a Pixi project — it is a research reproduction platform. Pixi must remain **repository infrastructure**, not a runtime dependency of agents or generated workspaces.

Constraints:

- Business agents, workflow, and services must not import or reference Pixi
- `EnvironmentService` workspace venv lifecycle (reproduction projects) remains unchanged
- Legacy `pip install -r requirements.txt` must continue to work during migration
- No CI workflows exist yet; adoption is developer-local first

## Decision

Adopt **Pixi with thin integration** at the **repository environment layer only**.

### Architecture

```text
pixi.toml (+ pixi.lock)
    ↓
Pixi environment (.pixi/envs/default)
    ↓
Python 3.12 + PyPI dependencies
    ↓
pixi run {run | test | integration}
    ↓
app.py / pytest / integration scripts
```

### Canonical developer workflow

| Task | Command | Purpose |
|------|---------|---------|
| `run` | `pixi run run` | Execute `app.py` with `PYTHONPATH=.` |
| `test` | `pixi run test` | Run pytest suite |
| `integration` | `pixi run integration` | Run integration script |

`pixi.toml` is the **canonical environment entry** for Man1Lab development. Python is pinned to **3.12.\***. Runtime dependencies mirror `requirements.txt`; pytest lives in the `dev` feature only.

### Integration rules

| Rule | Detail |
|------|--------|
| **Repo root only** | Pixi files live at repository root; not embedded in generated workspaces |
| **No agent imports** | Zero Pixi references in agents, workflow, services, or adapters |
| **Legacy path retained** | `requirements.txt` remains as pip compatibility layer with header comment |
| **Workspace isolation** | `EnvironmentService` still creates `.venv` + pip inside reproduction workspaces — separate concern |
| **Lockfile committed** | `pixi.lock` checked in for reproducible installs |

Business agents **do not know Pixi exists**.

## Alternatives

**pip + venv only:** Rejected as canonical path. No lockfile; dev deps informal; harder reproducibility for Docling ML stack.

**Poetry / uv as primary:** Considered. Pixi chosen for conda-forge channel support and unified task runner aligned with scientific Python workflows.

**Embed Pixi in generated workspaces:** Rejected. Reproduction workspace environment is Execution layer concern (`EnvironmentService`); developer repo environment is infrastructure.

**Remove `requirements.txt` immediately:** Rejected. Contributors and legacy docs still reference pip; removal deferred to Phase 2 after CI migration.

**Pin Python 3.10 in Pixi:** Rejected. Docs stated 3.10+; Pixi standardizes on 3.12 for current stack; legacy pip path still allows other versions.

## Consequences

**Positive:**

- Reproducible developer environment via lockfile
- Dev dependencies (pytest) formally declared
- Single commands for run, test, and integration
- Docling and ML transitive deps solved in one environment
- No business logic changes

**Negative:**

- Contributors must install Pixi for recommended workflow
- Dual maintenance: `pixi.toml` and `requirements.txt` until Phase 2
- Python version effectively 3.12 for Pixi users vs documented 3.10+ for pip legacy
- No CI integration yet — Pixi not enforced in automation
- `.pixi/` local cache gitignored; not portable without `pixi install`

## Relationship to Other ADRs

- [ADR-0006](ADR-0006-Runtime-Artifact-Ownership.md) / [ADR-0007](ADR-0007-Execution-Capability.md): Runner workspace `.venv` is runtime artifact ownership — **not** Pixi. Pixi manages the **Man1Lab developer** environment only.
- [ADR-0010](ADR-0010-Hydra-Configuration.md): `hydra-core` is declared in both Pixi and legacy requirements
- [ADR-0008](ADR-0008-Document-Parsing-Docling.md): Docling dependency supplied through Pixi PyPI dependencies
- Infrastructure governance: see [infrastructure.md](../architecture/infrastructure.md)

## Phase 1 Scope

Phase 1 is **environment layer only**. No business logic changes.

| Item | Phase 1 status |
|------|----------------|
| `pixi.toml` + `pixi.lock` | Complete |
| Pixi tasks (run, test, integration) | Complete |
| `requirements.txt` compatibility layer | Retained |
| Remove `requirements.txt` | Deferred — Phase 2 |
| CI with `setup-pixi` | Deferred — when CI added |
| lint/format Pixi tasks | Deferred — when tooling adopted |

Migration report (local): `private/design/migrations/pixi-phase-1.md`
