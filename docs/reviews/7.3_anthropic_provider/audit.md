# Anthropic Provider Audit — Phase 7.3

**Date:** 2026-07-08  
**Scope:** Anthropic provider integration via LLM Provider architecture  
**Verdict:** **Ready for CLI Model Commands**

---

## Implemented Files

| File | Purpose |
|------|---------|
| `providers/llm/anthropic_provider.py` | Anthropic Messages API adapter (`generate`, `stream`, `health_check`) |
| `providers/llm/errors.py` | Provider-level error types for SDK exception translation |
| `tests/test_anthropic_provider.py` | Anthropic provider tests (14 tests) |
| `docs/reviews/7.3_anthropic_provider/audit.md` | This audit |

## Modified Files

| File | Change |
|------|--------|
| `providers/llm/provider_registry.py` | Register `anthropic` provider |
| `providers/llm/profiles.py` | Add `anthropic` to `KNOWN_PROVIDERS` |
| `providers/llm/registry.py` | `build_provider_config()` maps Anthropic profiles to `anthropic_*` fields |
| `providers/llm/__init__.py` | Export `AnthropicProvider` and error types |
| `llm/anthropic_provider.py` | Backward-compatible wrapper over infrastructure provider |
| `conf/llm/default.yaml` | Add disabled `claude` Anthropic profile |
| `tests/test_llm_provider.py` | Updated default registry provider list |
| `docs/architecture/ARCHITECTURE.md` | Anthropic provider documented |
| `docs/CURRENT_STATUS.md` | Anthropic provider status |
| `docs/GETTING_STARTED.md` | Anthropic profile example |

## Files Unchanged (per phase scope)

| Area | Notes |
|------|-------|
| Agents / workflow / prompts | No business-layer changes |
| Analysis / Discovery / Execution Planning | Unchanged |
| CLI model commands | Not implemented |
| OpenAI / DeepSeek providers | Behavior unchanged |

---

## Architecture

```text
Business Logic
        ↓
LLMManager
        ↓
ModelRegistry
        ↓
ProviderRegistry
        ↓
AnthropicProvider
        ↓
Anthropic SDK
```

Only `ProviderRegistry` and the Anthropic adapter know about the Anthropic SDK. Business modules interact exclusively with `LLMManager` through the legacy `complete()` adapter.

---

## Provider Contract

| Method | Anthropic implementation |
|--------|------------------------|
| `generate()` | `client.messages.create()` with system/chat split |
| `stream()` | `client.messages.stream()` → `text_stream` |
| `health_check()` | Lightweight `messages.create(max_tokens=1)`; errors returned as `LLMHealthStatus(status="error")` |
| `provider_name` | `"anthropic"` |
| `supported_models()` | Recommended defaults (`claude-sonnet-4`, `claude-opus-4`, …) |

SDK exceptions are translated to `LLMProviderError` subclasses before crossing the provider boundary.

---

## Configuration

**`conf/llm/default.yaml`**

```yaml
profiles:
  claude:
    provider: anthropic
    model: claude-sonnet-4
    api_key_reference: ANTHROPIC_API_KEY
    enabled: false
```

No schema redesign. Existing OpenAI and DeepSeek profiles unchanged. Activate with `active: claude` and `ANTHROPIC_API_KEY` in `.env`.

---

## Boundary Verification

| Rule | Status |
|------|--------|
| Business does not import Anthropic SDK | ✅ |
| Anthropic provider does not import workflow / agents | ✅ AST audit |
| Providers do not edit ModelRegistry | ✅ |
| No prompt or workflow changes | ✅ |
| No CLI model commands | ✅ |

---

## Dependency Audit

| Layer | May import |
|-------|------------|
| `providers/llm/anthropic_provider.py` | `anthropic` SDK, `configuration.models`, `providers.llm.*` |
| Business / facade | `LLMManager` only (via adapter) |

Forbidden in `anthropic_provider.py`: workflow, execution_planning, agents, github providers.

---

## Backward Compatibility

| Path | Behavior |
|------|----------|
| OpenAI / DeepSeek profiles | Unchanged |
| Legacy `.env` OpenAI variables | Unchanged |
| `llm.anthropic_provider.AnthropicProvider` | Preserved as compatibility wrapper |
| Mock fallback without API keys | Unchanged (default profile still OpenAI-based) |
| Anthropic integration | Additive — disabled `claude` profile in default config |

---

## Test Coverage

**`tests/test_anthropic_provider.py`**

| Test | Coverage |
|------|----------|
| Provider registration | Default registry includes `anthropic` |
| Provider lookup | Resolve Anthropic adapter |
| `generate()` delegation | System/user message split, SDK call |
| `stream()` delegation | `text_stream` chunks |
| `health_check()` | Success and error paths (no throw) |
| Error translation | Authentication and rate-limit errors |
| Provider metadata | `provider_name`, `supported_models()` |
| Manager integration | Active Claude profile → Anthropic provider |
| Provider config mapping | `anthropic_api_key` / `anthropic_model` |
| AST boundary audit | Forbidden imports |

**Full suite:** 583 tests passing.

---

## Remaining Work

| Item | Phase |
|------|-------|
| CLI model commands (`man1lab model list`, `use`, …) | Next |
| Per-agent profile overrides | Future |
| Gemini / OpenRouter / Ollama / Azure OpenAI | Future |
| Profile persistence editing | Future |

---

## Verdict

**Ready for CLI Model Commands**

Anthropic is integrated exclusively as a new provider adapter. The heterogeneous SDK architecture is validated: `LLMManager` resolves Anthropic through `ModelRegistry` and `ProviderRegistry` without business-layer changes. OpenAI and DeepSeek behavior remains unchanged.
