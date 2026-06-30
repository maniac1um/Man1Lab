# ADR-0010 — Hydra Configuration

## Status

Accepted

## Date

2026-06-30

## Context

Man1Lab v1.x relied on a flat `config.py` module with environment variables and hard-coded defaults. As the platform grew (parser backends, LLM providers, workflow limits, per-layer placeholders), configuration became scattered and difficult to override consistently.

Architecture review identified [Hydra](https://hydra.cc/) as a mature configuration composition framework. Man1Lab is not a Hydra application — it is a research reproduction platform. Hydra must remain **infrastructure**, not a dependency of business agents.

Constraints:

- Reader, Planner(S), workflow, and parsing adapters must not import Hydra
- Existing `import config` call sites must keep working during migration
- Tests must run without invoking Hydra bootstrap when using legacy provider
- Secrets continue to resolve from environment variables and `.env`

## Decision

Adopt **Hydra with thin integration** at the **Configuration Layer only**.

### Architecture

```text
conf/*.yaml
    ↓
Hydra compose (configuration/bootstrap.py)
    ↓
HydraSettingsProvider
    ↓
SettingsProvider (port)
    ↓
config.py facade (module constants)     ← existing consumers
ConfigParserSettingsProvider            ← parser adapter
app.py composition root                 ← initialize_app_configuration()
```

### Configuration structure

Hydra YAML lives under `conf/`:

| Config group | Purpose |
|--------------|---------|
| `parser/` | Parser backend, max text chars |
| `workflow/` | Review iteration limits |
| `llm/` | API keys and model names (env interpolation) |
| `logging/` | Log level and format |
| `analysis/`, `planner/`, `coder/`, `runner/`, `reviewer/`, `reporter/` | Layer placeholders for future settings |

Secrets and overrides resolve via `${oc.env:...}` with `.env` loaded before compose.

### Integration rules

| Rule | Detail |
|------|--------|
| **Single entry** | `app.py` calls `initialize_app_configuration()` before workflow execution |
| **Provider port** | `SettingsProvider` abstracts Hydra; adapters read settings through provider where migrated |
| **Legacy facade** | `config.py` projects `AppSettings` onto module-level constants for unchanged consumers |
| **Test path** | `LegacySettingsProvider` populates defaults when Hydra bootstrap is not called |
| **No agent imports** | Hydra and OmegaConf imports confined to `configuration/` bootstrap and provider modules |

Business agents **do not know Hydra exists**.

## Alternatives

**Keep flat `config.py` only:** Rejected. Does not scale with layered architecture; no structured override tree.

**Hydra imported directly in agents:** Rejected. Couples business logic to infrastructure; violates ports-and-adapters boundary.

**Replace `config.py` facade immediately:** Rejected. Wide import graph and test fixtures require phased migration (Phase 2).

**Pydantic Settings without Hydra:** Rejected for now. Hydra provides composition, defaults groups, and override syntax aligned with multi-layer config tree; adoption is infrastructure-only behind provider.

**Custom YAML loader:** Rejected. Reinvents composition, env interpolation, and override semantics Hydra already provides.

## Consequences

**Positive:**

- Structured, composable configuration aligned with platform layers
- Environment overrides preserved via Hydra `oc.env`
- Parser settings decoupled from flat module via `SettingsProvider`
- Business modules unchanged in Phase 1
- Foundation for CLI overrides (e.g. `parser.backend=pymupdf`) in a future phase

**Negative:**

- Dual access path: `import config` facade and `SettingsProvider` coexist until Phase 2
- `config.py` remains intentional technical debt as compatibility shim
- Some modules still read facade directly rather than provider
- Agent-specific YAML groups are placeholders until populated

## Relationship to Other ADRs

- [ADR-0008](ADR-0008-Document-Parsing-Docling.md): Parser backend selection (`PARSER_BACKEND`) is configured through Hydra `conf/parser/` and consumed via `ConfigParserSettingsProvider`
- [ADR-0003](ADR-0003-Prompt-Infrastructure.md): Prompt paths remain configurable; not yet migrated to Hydra groups
- Infrastructure governance: see [infrastructure.md](../architecture/infrastructure.md)

## Phase 1 Scope

Phase 1 is **configuration layer only**. No business logic changes.

| Item | Phase 1 status |
|------|----------------|
| Hydra bootstrap + provider | Complete |
| `conf/` YAML tree | Complete |
| Parser adapter via provider | Complete |
| Migrate all consumers off `config` facade | Deferred — Phase 2 |
| Remove `LegacySettingsProvider` | Deferred — Phase 2+ |
| Native Hydra CLI overrides on `app.py` | Future |

Migration report (local): `private/design/migrations/hydra-phase-1.md`
