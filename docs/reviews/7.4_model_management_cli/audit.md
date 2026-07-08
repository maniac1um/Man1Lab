# Model Management CLI Audit — Phase 7.4

**Date:** 2026-07-08  
**Scope:** `man1lab model` CLI exposing Model Registry through Platform Facade  
**Verdict:** **Ready for v1.3 Platform Hardening**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `providers/llm/persistence.py` | Persist/load profile overlays to `conf/llm/user_profiles.yaml` |
| `providers/llm/model_management.py` | Model management reports and registry operations |
| `interfaces/cli/commands/model.py` | `man1lab model` subcommands |
| `tests/test_model_cli.py` | CLI, facade delegation, persistence, boundary tests (13 tests) |
| `docs/reviews/7.4_model_management_cli/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `providers/llm/manager.py` | Model management methods + persistence + provider refresh |
| `providers/llm/registry.py` | `export_profiles()` for persistence |
| `providers/llm/profiles.py` | `profile_to_spec()` helper |
| `configuration/paths.py` | `resolve_llm_user_profiles_path()` |
| `configuration/hydra_provider.py` | Merge persisted user profile overlay on bootstrap |
| `application/facade.py` | `list_models()`, `current_model()`, `use_model()`, `add_model()`, `remove_model()`, `rename_model()`, `test_model()`, `validate_models()` |
| `interfaces/cli/app.py` | Register `model` Typer group |
| `docs/architecture/ARCHITECTURE.md` | Model CLI mapping |
| `docs/CURRENT_STATUS.md` | Model CLI status |
| `docs/GETTING_STARTED.md` | Model management examples |
| `README.md` | Model CLI examples |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Provider implementations | OpenAI, DeepSeek, Anthropic adapters unchanged |
| Workflow / agents / prompts | No behavior changes |
| ModelRegistry validation rules | Unchanged |
| Analysis / Discovery / Execution Planning | Unchanged |

---

## Architecture

```text
CLI (man1lab model)
        ↓
Platform Facade (Man1Lab)
        ↓
LLMManager
        ↓
ModelRegistry
        ↓
ProviderRegistry (on test / inference only)
        ↓
LLMProvider
```

CLI never imports providers, registry internals, or edits YAML directly. Persistence is invoked by `LLMManager` after registry mutations.

---

## CLI Commands

| Command | Facade method | Behavior |
|---------|---------------|----------|
| `model list` | `list_models()` | Tabular profile listing with active marker |
| `model current` | `current_model()` | Active profile details |
| `model use <profile>` | `use_model()` | Switch active profile, persist, refresh provider |
| `model add` | `add_model()` | Interactive prompts + validation + persist |
| `model remove <profile>` | `remove_model()` | Block active removal unless `--force` |
| `model rename <old> <new>` | `rename_model()` | Rename profile, update active reference |
| `model test [profile]` | `test_model()` | Provider `health_check()` with friendly output |
| `model validate` | `validate_models()` | Structured diagnostics; exit `0`/`1` |

---

## Facade Integration

Facade methods are thin delegations to `LLMManager` with no registry logic:

- `list_models()` → `ModelListReport`
- `current_model()` → `CurrentModelReport`
- `use_model()` → `ModelChangeReport`
- `add_model()` / `remove_model()` / `rename_model()` → `ModelChangeReport`
- `test_model()` → `ModelTestReport`
- `validate_models()` → `RegistryValidationResult`

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `interfaces/cli/commands/model.py` | `application` (via `get_platform`), `typer` |
| `application/facade.py` | `providers.llm.manager`, `providers.llm.model_management` |
| `providers/llm/persistence.py` | `omegaconf`, `configuration` |

Forbidden in CLI: `providers.*`, workflow, agents, OpenAI/Anthropic SDKs.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| CLI does not import providers | ✅ AST audit |
| CLI does not edit YAML directly | ✅ |
| Facade contains no registry logic | ✅ delegation only |
| Registry does not call providers (except via manager test) | ✅ |
| No workflow or agent changes | ✅ |

---

## Persistence

| Item | Detail |
|------|--------|
| Path | `conf/llm/user_profiles.yaml` |
| Owner | `LLMManager` via `providers/llm/persistence.py` |
| Load | Merged during Hydra bootstrap (`_merge_persisted_llm_config`) |
| Save | After `use`, `add`, `remove`, `rename` |
| Contents | `active` + `profiles` only (no secret values) |

---

## Backward Compatibility

| Path | Behavior |
|------|----------|
| Existing `man1lab` commands | Unchanged |
| Hydra `conf/llm/default.yaml` | Unchanged bundled defaults |
| Legacy `.env` configuration | Still supported |
| Provider behavior | Unchanged |
| No `user_profiles.yaml` | Bootstrap uses Hydra defaults only |

---

## Test Coverage

**`tests/test_model_cli.py`**

| Test | Coverage |
|------|----------|
| `test_model_list` | CLI list + facade delegation |
| `test_model_current` | Active profile display |
| `test_model_use` | Profile switching |
| `test_model_add_interactive` | Interactive add flow |
| `test_model_remove_*` | Active profile guard + `--force` |
| `test_model_rename` | Rename command |
| `test_model_test` | Health test output |
| `test_model_validate_*` | Exit codes 0/1 |
| `test_facade_delegates_model_operations` | Facade → manager |
| `test_registry_persistence_round_trip` | Save/load overlay |
| AST boundary audit | CLI import restrictions |

**Full suite:** 596 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Non-interactive `model add` flags-only mode refinement | Optional polish |
| SDK model management method exports | Optional |
| Profile import/export | Future |
| Per-agent profile overrides | Future |

---

## Verdict

**Ready for v1.3 Platform Hardening**

Users can fully manage model profiles through `man1lab model` without editing configuration files. The CLI remains a thin interface over the Platform Facade. Registry owns profile lifecycle; providers stay isolated.
