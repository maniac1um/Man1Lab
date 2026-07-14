"""LLM provider contract for infrastructure adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from providers.llm.models import LLMHealthStatus, LLMMessage


class LLMProvider(ABC):
    """Infrastructure-level provider contract."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return models commonly supported by this provider."""

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for the given messages."""

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Iterator[str]:
        """Stream completion chunks for the given messages."""

    @abstractmethod
    def health_check(self) -> LLMHealthStatus:
        """Return provider health metadata without performing business logic."""
