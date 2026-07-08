"""DeepSeek provider adapter using the OpenAI-compatible API."""

from __future__ import annotations

from configuration.models import LLMConfig
from providers.llm.openai_provider import OpenAIProvider

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = (
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-v4-pro",
)


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek chat-completions provider via OpenAI-compatible API."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        resolved_base_url = base_url or config.openai_base_url or DEEPSEEK_BASE_URL
        super().__init__(
            config,
            api_key=api_key,
            model=model,
            base_url=resolved_base_url,
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def supported_models(self) -> list[str]:
        return list(DEEPSEEK_MODELS)

    def health_check(self):
        return super().health_check().model_copy(
            update={
                "provider": self.provider_name,
                "message": "DeepSeek OpenAI-compatible client configured.",
            }
        )
