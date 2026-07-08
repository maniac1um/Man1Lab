"""Anthropic SDK provider adapter."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from anthropic import Anthropic
from anthropic import APIError, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

from configuration.models import LLMConfig
from providers.llm.base import LLMProvider
from providers.llm.errors import (
    LLMProviderAPIError,
    LLMProviderAuthenticationError,
    LLMProviderError,
    LLMProviderRateLimitError,
)
from providers.llm.models import LLMHealthStatus, LLMMessage

ANTHROPIC_MODELS = (
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
)

DEFAULT_MAX_TOKENS = 4096
HEALTH_CHECK_MAX_TOKENS = 1


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        key = api_key if api_key is not None else config.anthropic_api_key
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        client_kwargs: dict[str, Any] = {"api_key": key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = Anthropic(**client_kwargs)
        self._model = model or config.anthropic_model
        self._default_max_tokens = max_tokens or DEFAULT_MAX_TOKENS

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def supported_models(self) -> list[str]:
        return list(ANTHROPIC_MODELS)

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> str:
        try:
            system_prompt, chat_messages = _split_messages(messages)
            response = self._client.messages.create(
                model=model or self._model,
                max_tokens=self._default_max_tokens,
                temperature=temperature,
                system=system_prompt or None,
                messages=chat_messages,
            )
            text_blocks = [block.text for block in response.content if block.type == "text"]
            if not text_blocks:
                raise LLMProviderAPIError("Anthropic returned an empty response")
            return "\n".join(text_blocks)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise _translate_anthropic_error(exc) from exc

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Iterator[str]:
        try:
            system_prompt, chat_messages = _split_messages(messages)
            with self._client.messages.stream(
                model=model or self._model,
                max_tokens=self._default_max_tokens,
                temperature=temperature,
                system=system_prompt or None,
                messages=chat_messages,
            ) as response:
                try:
                    yield from response.text_stream
                except Exception as exc:
                    raise _translate_anthropic_error(exc) from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise _translate_anthropic_error(exc) from exc

    def health_check(self) -> LLMHealthStatus:
        try:
            self._client.messages.create(
                model=self._model,
                max_tokens=HEALTH_CHECK_MAX_TOKENS,
                messages=[{"role": "user", "content": "ping"}],
            )
            return LLMHealthStatus(
                provider=self.provider_name,
                status="ok",
                model=self._model,
                message="Anthropic API reachable.",
            )
        except Exception as exc:
            translated = _translate_anthropic_error(exc)
            return LLMHealthStatus(
                provider=self.provider_name,
                status="error",
                model=self._model,
                message=str(translated),
            )


def _split_messages(messages: list[LLMMessage]) -> tuple[str, list[dict[str, str]]]:
    system_prompt = ""
    chat_messages: list[dict[str, str]] = []
    for message in messages:
        if message.role == "system":
            system_prompt = message.content
        else:
            chat_messages.append({"role": message.role, "content": message.content})
    return system_prompt, chat_messages


def _translate_anthropic_error(exc: Exception) -> LLMProviderError:
    if isinstance(exc, AuthenticationError):
        return LLMProviderAuthenticationError(str(exc))
    if isinstance(exc, RateLimitError):
        return LLMProviderRateLimitError(str(exc))
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return LLMProviderAPIError(str(exc))
    if isinstance(exc, APIError):
        return LLMProviderAPIError(str(exc))
    return LLMProviderAPIError(str(exc))
