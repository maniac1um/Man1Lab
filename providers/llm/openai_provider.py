"""OpenAI SDK provider adapter."""

from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from configuration.models import LLMConfig
from providers.llm.base import LLMProvider
from providers.llm.models import LLMHealthStatus, LLMMessage

OPENAI_MODELS = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o3-mini",
)


class OpenAIProvider(LLMProvider):
    """OpenAI chat-completions provider."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        key = api_key if api_key is not None else config.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is not set")

        client_kwargs: dict[str, str] = {"api_key": key}
        resolved_base_url = base_url if base_url is not None else config.openai_base_url
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url

        self._client = OpenAI(**client_kwargs)
        self._model = model or config.openai_model

    @property
    def provider_name(self) -> str:
        return "openai"

    def supported_models(self) -> list[str]:
        return list(OPENAI_MODELS)

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> str:
        response = self._client.chat.completions.create(
            model=model or self._model,
            temperature=temperature,
            messages=[{"role": message.role, "content": message.content} for message in messages],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty response")
        return content

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Iterator[str]:
        response = self._client.chat.completions.create(
            model=model or self._model,
            temperature=temperature,
            messages=[{"role": message.role, "content": message.content} for message in messages],
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def health_check(self) -> LLMHealthStatus:
        return LLMHealthStatus(
            provider=self.provider_name,
            status="ok",
            model=self._model,
            message="OpenAI client configured.",
        )
