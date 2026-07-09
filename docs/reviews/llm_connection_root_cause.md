# LLM Connection Root Cause — Investigation Report

## Executive Summary

Intermittent `plan-all` failures during the first LLM request (Reader analysis) have **two distinct root causes**, both originating below the OpenAI SDK wrapper:

| Symptom | Root exception | Mechanism |
|---------|----------------|-----------|
| **Case A:** `Request timed out` (~15–17s, SDK retries) | `httpx.ConnectTimeout` / `openai.APITimeoutError` | OpenAI SDK default **connect timeout = 5s**; TLS to `api.deepseek.com` often exceeds 5s; `max_retries=2` → 3 attempts |
| **Case B:** `Connection error` (~45–50s, SDK retries) | `httpx.ConnectError` → `ssl.SSLEOFError: UNEXPECTED_EOF_WHILE_READING` | Intermittent TLS handshake / connection drop to DeepSeek during large POST bodies |

Failures are **not** caused by Discovery, Planning, Docling logic, or Runtime architecture. Docling always completes; failure occurs at `POST /chat/completions`.

## Execution Path

```
plan-all (runtime/console/builtins.py)
  → hydrate_workspace_from_disk
  → platform.analyze(paper)          [if analysis.json absent]
    → WorkspaceArtifactStore.load_parsed_document  [resume checkpoint]
    → Reader.read_text → DoclingParser.parse      [if no checkpoint]
    → WorkspaceArtifactStore.save_parsed_document
    → Reader.run_analysis → LLM complete
      → LLMManagerCompleteAdapter.complete
        → LLMManager.generate
          → OpenAIProvider.generate
            → OpenAI SDK (max_retries=2)
              → httpx.Client → api.deepseek.com/chat/completions
```

## Runtime Probe Evidence

### Small requests (reliable)

8/8 `"ping"` requests succeeded in 0.7–1.3s with connect=60s.

### Large analyze-sized requests (intermittent)

With `max_retries=2` and ~82k-char payload:

- **3/3 failed** at ~47s each with chain:
  ```
  openai.APIConnectionError: Connection error.
  caused by: httpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] ...
  caused by: ssl.SSLEOFError: [SSL: UNEXPECTED_EOF_WHILE_READING] ...
  ```

Same payload later succeeded 12/12 — confirming **intermittent network/TLS**, not deterministic prompt-size rejection.

### Payload size alone (not sufficient)

Synthetic 80k-char `"x"` payloads succeeded without SSL errors — failures correlate with **transient TLS to DeepSeek**, sometimes under load/timing, not raw character count alone.

## Exception Swallowing (fixed)

Before this investigation, the console displayed only `str(exc)`:

- `APIConnectionError` → `"Connection error."`
- `APITimeoutError` → `"Request timed out."`

The underlying `httpx.ConnectError` / `ssl.SSLEOFError` was hidden. **Fix:** `translate_openai_error()` + `format_exception_chain()` surface the full chain in console errors.

## Retry Analysis

| Layer | Retries | Backoff | Notes |
|-------|---------|---------|-------|
| OpenAI SDK | `max_retries=2` | SDK exponential | Only retry layer in Man1Lab |
| httpx | `retries=0` (default transport) | — | No duplicate httpx retries |
| Man1Lab custom | None | — | No additional retry logic |

Total attempts per call: **3** (initial + 2 SDK retries). Elapsed time ≈ `per_attempt_timeout × 3` for connect failures.

## HTTP Client Lifecycle

- `OpenAIProvider` creates **one** `OpenAI` client per provider instance
- `LLMManager` holds one provider for the runtime session (`client_id` stable across requests)
- Connection pooling: httpx default pool inside SDK client; keep-alive enabled
- **Not** creating a new client per request

## Provider Configuration (deterministic)

| Setting | Value | Source |
|---------|-------|--------|
| connect timeout | 60s | `LLMConfig.llm_connect_timeout_seconds` |
| read timeout | 600s | `LLMConfig.llm_read_timeout_seconds` |
| write timeout | 600s | `LLMConfig.llm_write_timeout_seconds` |
| pool timeout | 60s | `LLMConfig.llm_pool_timeout_seconds` |
| max_retries | 2 | `OpenAIProvider` |
| streaming | false | `generate()` |
| HTTP/2 | false | `h2` not installed; httpx uses HTTP/1.1 |
| base_url | profile `base_url` or provider default | e.g. `https://api.deepseek.com` |

## DeepSeek Compatibility

- Uses OpenAI-compatible `/chat/completions` endpoint ✓
- `DeepSeekProvider` extends `OpenAIProvider` with `DEEPSEEK_BASE_URL` ✓
- Active profile may use `provider: openai` with `base_url: https://api.deepseek.com` ✓
- Model names (`deepseek-chat`, `deepseek-v4-pro`) accepted by API when network succeeds ✓

## Resume / Docling Re-parse

| Artifact present | Behavior |
|------------------|----------|
| `analysis/analysis.json` | `hydrate_workspace_from_disk` + `facade.analyze` skip Docling and LLM |
| `analysis/parsed_document.md` (valid meta) | Docling skipped; LLM still runs |
| Neither | Docling runs; checkpoint saved before LLM |

**Why Docling may still appear after failures:** LLM failed before `analysis.json` was written; `parsed_document.md` checkpoint should prevent re-parse on retry. If workspace path differs or PDF mtime changed, cache invalidates.

## Fixes Applied (minimal)

1. **Connect timeout 60s** (prior fix) — addresses Case A
2. **`format_exception_chain` + `translate_openai_error`** — surfaces root `httpx`/`ssl` exceptions (Case B visibility)
3. **`facade.analyze`** — skip entirely when `analysis.json` exists
4. **Console** — print full exception chain on errors

## What was NOT changed

- No additional retry layers
- No timeout increases beyond prior 60s connect fix
- No Runtime / Console / Provider redesign

## Regression Tests

- `tests/test_llm_exception_chain.py` — chain formatting, error translation, trace output
- `tests/test_llm_timeouts.py` — timeout configuration
- `tests/test_console_workspace.py` — parsed document checkpoint
- `tests/test_platform_facade.py` — analyze resume without re-parse

## Remaining Work

1. **Network reliability** to `api.deepseek.com` — environmental; consider proxy/VPN/firewall diagnostics
2. **Optional:** chunked/summarized Reader prompts to reduce upload size and TLS exposure window
3. **Optional:** provider health probe before large analyze requests
