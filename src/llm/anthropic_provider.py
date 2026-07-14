"""Backward-compatible Anthropic provider export."""

from __future__ import annotations

import config
from configuration.models import LLMConfig
from llm.compat import ProviderCompleteAdapter
from providers.llm.anthropic_provider import AnthropicProvider as InfrastructureAnthropicProvider


class AnthropicProvider(ProviderCompleteAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        llm_config = LLMConfig(
            anthropic_api_key=api_key if api_key is not None else (config.ANTHROPIC_API_KEY or ""),
            anthropic_model=model if model is not None else (config.ANTHROPIC_MODEL or "claude-3-5-haiku-latest"),
        )
        super().__init__(
            InfrastructureAnthropicProvider(
                llm_config,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
        )
