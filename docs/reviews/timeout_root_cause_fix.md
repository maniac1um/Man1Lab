# Timeout Root Cause Fix — Audit

## Summary

`plan-all` timeouts during the first LLM call (Reader analysis) were caused by the **OpenAI SDK default HTTP connect timeout of 5 seconds**, not by oversized prompts or Discovery logic. DeepSeek API connections in this environment frequently require more than 5s to complete TLS handshake; with `max_retries=2`, users observe ~15–17s of "Retrying request" messages followed by `Request timed out`.

## Call Chain

```
plan-all (console builtins)
  → platform.analyze(paper)
    → WorkspaceArtifactStore.load_parsed_document (resume)
    → Reader.read_text (Docling) OR cached markdown
    → WorkspaceArtifactStore.save_parsed_document (checkpoint)
    → Reader.run_analysis → LLM complete
      → LLMManagerCompleteAdapter.complete
        → LLMManager.generate
          → OpenAIProvider.generate
            → OpenAI SDK → httpx → POST /chat/completions
```

Discovery and Planning are **not reached** when analyze LLM fails.

## Timeout Configuration (before fix)

| Layer | Connect | Read | Write | Retries |
|-------|---------|------|-------|---------|
| OpenAI SDK default | **5.0s** | 600s | 600s | 2 |
| Man1Lab (before) | *(unset — SDK default)* | *(unset)* | *(unset)* | 2 |
| Anthropic SDK | SDK default | SDK default | — | SDK default |

No explicit timeout was configured in `OpenAIProvider`. Read timeout (600s) was never the limiting factor for the observed failure.

## Retry Analysis

With `max_retries=2`, a connect-timeout failure produces **3 attempts** (initial + 2 retries), each timing out at ~5s → total ~15–17s elapsed, matching observed console output:

```
Retrying request to /chat/completions
Retrying request
Request timed out
```

Retries masked the root cause by suggesting a transient server issue rather than an aggressive client connect timeout.

## Prompt Size Analysis

For paper `2012.12877v2.pdf`:

| Metric | Value |
|--------|-------|
| Docling markdown chars | 73,319 |
| Estimated input tokens | ~18,329 |
| Reader system prompt | ~9,256 chars |

Large but within model limits. A minimal `"say hi"` request **also timed out** with the default 5s connect timeout, confirming prompt size is not the primary cause.

## Fix

1. **`providers/llm/timeouts.py`** — explicit `httpx.Timeout` with **connect=60s** (configurable via `LLMConfig`)
2. **`providers/llm/openai_provider.py`** — pass timeout to `OpenAI()` constructor
3. **`configuration/models.py`** — `llm_connect_timeout_seconds`, `llm_read_timeout_seconds`, etc.
4. **Parse checkpoint resume** — `WorkspaceArtifactStore` persists `analysis/parsed_document.md` after Docling; `facade.analyze()` reuses it on retry so Docling is not repeated after LLM failure

## Regression Coverage

| Test | Validates |
|------|-----------|
| `tests/test_llm_timeouts.py` | Connect timeout > SDK default; config wiring |
| `tests/test_llm_provider.py` | OpenAI client receives explicit timeout |
| `tests/test_console_workspace.py` | Parsed document cache round-trip + invalidation |
| `tests/test_platform_facade.py` | Analyze skips re-parse when cache exists |

## Remaining Work

1. **Intermittent SSL errors** to `api.deepseek.com` may still cause `APIConnectionError` — network/environment issue, not Man1Lab logic
2. **Profile `max_tokens`** — now forwarded when set; Reader analysis may benefit from explicit output cap in profiles
3. **Anthropic timeout parity** — separate SDK; not changed in this fix
