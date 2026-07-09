"""HTTP timeout configuration for OpenAI-compatible LLM clients."""

from __future__ import annotations

import httpx

from configuration.models import LLMConfig

DEFAULT_CONNECT_TIMEOUT_SECONDS = 60.0
DEFAULT_READ_TIMEOUT_SECONDS = 600.0
DEFAULT_WRITE_TIMEOUT_SECONDS = 600.0
DEFAULT_POOL_TIMEOUT_SECONDS = 60.0


def build_openai_client_timeout(config: LLMConfig) -> httpx.Timeout:
    """Build httpx timeouts for the OpenAI SDK client.

    The OpenAI SDK default connect timeout is 5 seconds, which is too aggressive
    for some remote APIs (e.g. DeepSeek) where TLS handshake can exceed 5s.
    """
    return httpx.Timeout(
        connect=config.llm_connect_timeout_seconds,
        read=config.llm_read_timeout_seconds,
        write=config.llm_write_timeout_seconds,
        pool=config.llm_pool_timeout_seconds,
    )
