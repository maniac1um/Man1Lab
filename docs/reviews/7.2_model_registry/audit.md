# Model Registry Audit — Phase 7.2

**Date:** 2026-07-08  
**Scope:** Canonical Model Registry and profile management  
**Verdict:** **Ready for Anthropic Provider and CLI Model Commands**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `providers/llm/profiles.py` | Legacy migration, API key resolution, deterministic validation |
| `providers/llm/registry.py` | `ModelRegistry` — profile lifecycle and active profile resolution |
| `providers/llm/provider_registry.py` | `ProviderRegistry` (split from `registry.py`) |
| `tests/test_model_registry.py` | Model registry tests (15 tests) |
| `docs/reviews/7.1_llm_provider_foundation/audit.md` | Provider foundation audit (retroactive) |
| `docs/reviews/7.2_model_registry/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `providers/llm/models.py` | Added `ModelProfile`, `RegistryDiagnostic`, `RegistryValidationResult` |
| `providers/llm/manager.py` | Resolves active profile via `ModelRegistry` before provider lookup |
| `providers/llm/__init__.py` | Exports `ModelRegistry`, `ModelProfile`, `RegistryValidationResult` |
| `configuration/models.py` | Added `ModelProfileSpec`; extended `LLMConfig` with `active` + `profiles` |
| `configuration/hydra_provider.py` | Parses profile-based LLM configuration from Hydra |
| `conf/llm/default.yaml` | Canonical `active` + `profiles` layout with legacy field preservation |
| `tests/test_llm_provider.py` | Updated imports; credential tests use explicit empty resolver |
| `docs/architecture/ARCHITECTURE.md` | Model Registry architecture section |
| `docs/CURRENT_STATUS.md` | Model Registry status |
| `docs/GETTING_STARTED.md` | Model profiles documentation |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Workflow / Analysis / Discovery / Execution Planning | No behavior changes |
| Agents and prompts | Unchanged |
| CLI commands | No model CLI in this phase |
| Anthropic provider | Not implemented |
| `llm/anthropic_provider.py` | Still unwired |

---

## Architecture

```text
Business Logic
        ↓
LLMManager
        ↓
ModelRegistry          ProviderRegistry
   (profiles)              (adapters)
        ↓                      ↓
   ModelProfile            LLMProvider
                                ↓
                      OpenAIProvider / DeepSeekProvider
```

| Component | Owns |
|-----------|------|
| **ModelRegistry** | Profile lifecycle — load, validate, activate, register, rename, remove |
| **LLMManager** | Inference coordination — active profile → provider → `generate()` |
| **ProviderRegistry** | Provider adapter lookup only |
| **LLMProvider adapters** | API communication only |

Registry never calls providers. Providers never edit the registry.

---

## Model Profile

Canonical `ModelProfile` fields:

| Field | Purpose |
|-------|---------|
| `profile_name` | Stable profile identifier |
| `provider` | Provider adapter name (`openai`, `deepseek`) |
| `model` | Model identifier |
| `base_url` | Optional API base URL |
| `api_key_reference` | Environment variable reference (not secret value) |
| `organization` | Reserved for Azure / enterprise providers |
| `api_version` | Reserved for versioned endpoints |
| `temperature` / `max_tokens` | Optional generation defaults |
| `enabled` | Profile availability flag |
| `description` / `tags` | Metadata |
| `created_at` / `updated_at` | Profile timestamps |

Profiles describe configuration only — no runtime inference state.

---

## Registry Operations

| Method | Responsibility |
|--------|----------------|
| `list_profiles()` | Return configured profiles |
| `get_profile()` | Lookup by name |
| `set_active_profile()` | Switch active profile |
| `add_profile()` / `register_profile()` | Add profile |
| `remove_profile()` | Remove profile |
| `rename_profile()` | Rename profile |
| `validate()` | Deterministic diagnostics |

Validation never throws during loading. Returns `RegistryValidationResult` with structured `RegistryDiagnostic` entries.

---

## Configuration Changes

**`conf/llm/default.yaml`**

```yaml
active: default
profiles:
  default:
    provider: openai
    model: ...
    api_key_reference: OPENAI_API_KEY
  deepseek:
    provider: deepseek
    model: deepseek-chat
    enabled: false
```

Legacy flat fields (`openai_api_key`, `openai_base_url`, `openai_model`, `anthropic_*`) preserved for `config.py` bridge compatibility.

---

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Legacy `.env` only (no profiles in config) | `ensure_profiles()` auto-migrates to `default` profile |
| DeepSeek via `OPENAI_BASE_URL` | Migrated profile uses `provider: deepseek` |
| `OPENAI_API_KEY` in config without env var | Resolved via `build_api_key_resolver()` fallback |
| Hydra profiles present | Profiles used directly; legacy fields still populated |
| No API key | Manager returns no active provider; mock fallback in facade unchanged |

No user-visible CLI behavior changes.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| Registry does not import providers or SDKs | ✅ AST audit |
| Registry does not import workflow / agents | ✅ |
| Providers do not edit registry | ✅ |
| Business sees only `LLMManager` | ✅ via facade + adapter |
| No CLI model commands | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `providers/llm/registry.py` | `configuration.models`, `providers.llm.profiles`, `providers.llm.models` |
| `providers/llm/profiles.py` | `configuration.models`, stdlib |
| `providers/llm/manager.py` | `ModelRegistry`, `ProviderRegistry`, provider adapters |

Forbidden in registry/profiles: OpenAI SDK, HTTP, workflow, execution_planning, agents, github providers.

---

## Test Coverage

**`tests/test_model_registry.py`**

| Test | Coverage |
|------|----------|
| `test_ensure_profiles_migrates_legacy_*` | Legacy OpenAI and DeepSeek migration |
| `test_registry_loads_profiles_and_active_profile` | Profile loading |
| `test_registry_switch_active_profile` | Active profile switching |
| `test_registry_detects_duplicate_profile_names` | Duplicate detection |
| `test_registry_detects_unknown_provider` | Unknown provider validation |
| `test_registry_detects_disabled_active_profile` | Disabled active profile |
| `test_registry_detects_missing_api_reference` | Missing API reference |
| `test_registry_rename_and_remove_profile` | Profile lifecycle operations |
| `test_registry_validation_never_raises_on_load` | Non-throwing load |
| `test_manager_resolves_provider_from_active_profile` | Manager integration |
| `test_manager_delegates_through_active_profile` | End-to-end generate delegation |
| AST boundary audit | Registry/profiles import boundaries |

**`tests/test_llm_provider.py`** — updated for `ModelRegistry` integration (14 tests).

**Full suite:** 571 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| Anthropic provider adapter in `providers/llm/` | Next provider phase |
| CLI model commands (`man1lab model list`, `use`, etc.) | Future |
| Profile persistence / file editing | Future |
| Gemini / OpenRouter / Ollama / Azure OpenAI profiles | Future |
| Per-agent profile overrides (reader vs planner) | Future |

---

## Verdict

**Ready for Anthropic Provider and CLI Model Commands**

Model Registry is the canonical model abstraction. `LLMManager` resolves providers through `ModelRegistry` without business-layer changes. Configuration supports future providers via profile `provider` field without schema redesign. OpenAI and DeepSeek runtime behavior is preserved.
