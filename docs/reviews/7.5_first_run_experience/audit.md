# First-run Experience Audit — Phase 7.5

**Date:** 2026-07-08  
**Scope:** Interactive `man1lab init` wizard, model import/export, doctor LLM validation  
**Verdict:** **Ready for v1.3 Platform Hardening**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `application/lifecycle/init_wizard.py` | Init wizard request resolution, provider defaults, `.env` API key persistence |
| `application/lifecycle/llm_doctor.py` | LLM section checks for `man1lab doctor` |
| `tests/test_init_wizard.py` | Wizard, import/export, doctor LLM, facade delegation, AST boundary tests (18 tests) |
| `docs/reviews/7.5_first_run_experience/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `application/facade.py` | `setup_first_model()`, `export_models()`, `import_models()`, LLM-aware `doctor()` |
| `providers/llm/persistence.py` | `export_portable_config()`, `import_portable_config()`, `ModelImportReport` |
| `providers/llm/manager.py` | `export_models()`, `import_models()` with persist + provider refresh |
| `interfaces/cli/commands/init.py` | Interactive first-model wizard, `--skip-model-config`, post-init UX |
| `interfaces/cli/commands/doctor.py` | Grouped LLM section output |
| `interfaces/cli/commands/model.py` | `model export`, `model import` with `--replace` / `--skip-existing` |
| `tests/test_cli.py` | Fixed `DoctorCheck` import path |
| `tests/test_package_distribution.py` | Init test uses `--skip-model-config` |
| `README.md`, `docs/GETTING_STARTED.md`, `docs/CURRENT_STATUS.md`, `docs/architecture/ARCHITECTURE.md` | First-run and import/export documentation |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Provider implementations | OpenAI, DeepSeek, Anthropic adapters unchanged |
| Workflow / agents / prompts | No behavior changes |
| ModelRegistry core validation | Unchanged |
| Analysis / Discovery / Execution Planning / Planner / Execution | Unchanged |

---

## Architecture

```text
CLI (man1lab init | model | doctor)
        ↓
Platform Facade (Man1Lab)
        ↓
Lifecycle Service (init_wizard, llm_doctor, doctor)
        ↓
LLMManager
        ↓
ModelRegistry
        ↓
ProviderRegistry (health check only in doctor/test)
        ↓
LLMProvider
```

CLI remains presentation-only. Configuration logic lives in lifecycle and LLM management layers. CLI never edits YAML or imports providers.

---

## Init Wizard

| Step | Behavior |
|------|----------|
| Prompt | `Configure your first AI model? [Y/n]` after workspace init |
| Profile name | Default `default` |
| Provider | Menu: OpenAI, DeepSeek, Anthropic |
| Model | Provider default with custom override |
| API key | Hidden input; written to `.env` via `write_api_key_to_env()` |
| Base URL | Optional; provider defaults auto-filled |
| Temperature / Max tokens / Description | Optional |
| Save | `setup_first_model()` → `add_model()` → `use_model()` via facade |
| Skip | `n` or `--skip-model-config` — identical to pre-7.5 behavior |

---

## Doctor

Extended `Man1Lab.doctor()` merges base lifecycle checks with `run_llm_doctor_checks()`:

| Check | Source |
|-------|--------|
| LLM Profiles | Profile count |
| LLM Active | Active profile name |
| LLM Provider | Provider label |
| LLM Model | Model id |
| LLM API Key | Resolved reference status |
| LLM Connection | `test_model()` health (mocked in tests) |
| LLM Validation | Registry validation summary |

CLI renders non-LLM checks first, then an **LLM** section header.

---

## Import / Export

| Command | Facade method | Behavior |
|---------|---------------|----------|
| `model export <file>` | `export_models()` | Portable YAML: `active` + `profiles` (no secrets) |
| `model import <file>` | `import_models()` | Validate, merge, detect duplicates |
| `--replace` | | Overwrite existing profile names |
| `--skip-existing` | | Skip conflicting names |

Import performs no provider communication. API keys remain environment references only.

**Portable format example:**

```yaml
active: claude
profiles:
  claude:
    provider: anthropic
    model: claude-sonnet-4
    api_key_reference: ANTHROPIC_API_KEY
    enabled: true
```

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `interfaces/cli/commands/init.py` | `application.lifecycle.init_wizard`, `typer`, `getpass` |
| `interfaces/cli/commands/model.py` | `application` (via `get_platform`), `typer` |
| `interfaces/cli/commands/doctor.py` | `application.lifecycle`, `typer` |
| `application/facade.py` | `application.lifecycle.*`, `providers.llm.manager` |
| `application/lifecycle/llm_doctor.py` | `providers.llm.manager` (doctor health only) |

Forbidden in CLI: `providers.*`, workflow, agents, execution_planning, planner, coder, runner, vendor SDKs.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| CLI does not import providers | ✅ AST audit (`test_init_wizard.py`) |
| CLI does not edit YAML directly | ✅ |
| Init wizard saves via ModelRegistry persistence | ✅ |
| Export never includes API secrets | ✅ |
| No workflow or provider implementation changes | ✅ |
| Existing init skip path unchanged | ✅ |

---

## Backward Compatibility

| Path | Behavior |
|------|----------|
| `man1lab init --skip-model-config` | Pre-7.5 init flow |
| Decline wizard (`n`) | Same as skip |
| Existing `man1lab model` commands | Unchanged |
| Configuration schema | Unchanged |
| Hydra defaults | Unchanged |

---

## Test Coverage

**`tests/test_init_wizard.py`**

| Test | Coverage |
|------|----------|
| `test_init_skip_model_config` | Skip flag preserves legacy flow |
| `test_init_openai_wizard_flow` | OpenAI interactive path |
| `test_init_deepseek_wizard_flow` | DeepSeek provider choice |
| `test_init_anthropic_wizard_flow` | Anthropic provider choice |
| `test_init_decline_model_config` | Decline wizard |
| `test_setup_first_model_delegates_through_facade` | Facade → manager |
| `test_export_excludes_secrets` | No keys in export file |
| `test_import_duplicate_detection` | Duplicate error |
| `test_import_replace` | `--replace` semantics |
| `test_import_skip_existing` | `--skip-existing` semantics |
| `test_model_export_cli` / `test_model_import_cli` | CLI delegation |
| `test_doctor_llm_output` | LLM check generation |
| `test_doctor_cli_llm_section` | CLI LLM section rendering |
| `test_init_cli_has_no_forbidden_imports` | AST boundary |
| `test_facade_exports_setup_and_import_export` | Facade methods |

**Full suite:** 614 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| SDK exports for `setup_first_model`, `export_models`, `import_models` | Optional |
| Non-interactive `model add` flags-only mode | Optional polish |
| Per-agent profile overrides | Future |

---

## Verdict

**Ready for v1.3 Platform Hardening**

A new user can install Man1Lab, run `man1lab init`, and configure their first LLM provider entirely through the CLI. Model profiles can be exported and imported safely without secrets. Doctor fully validates LLM configuration. No workflow or provider architecture changes were introduced.
