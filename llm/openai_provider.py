"""Backward-compatible OpenAI provider export."""

from __future__ import annotations

import config
from configuration.models import LLMConfig
from llm.compat import ProviderCompleteAdapter
from providers.llm.openai_provider import OpenAIProvider as InfrastructureOpenAIProvider


class OpenAIProvider(ProviderCompleteAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        llm_config = LLMConfig(
            openai_api_key=api_key if api_key is not None else (config.OPENAI_API_KEY or ""),
            openai_base_url=base_url if base_url is not None else (config.OPENAI_BASE_URL or ""),
            openai_model=model if model is not None else (config.OPENAI_MODEL or "gpt-4o-mini"),
        )
        super().__init__(
            InfrastructureOpenAIProvider(
                llm_config,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
        )
