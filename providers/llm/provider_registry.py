"""Runtime provider registration and lookup."""

from __future__ import annotations

from collections.abc import Callable

from configuration.models import LLMConfig
from providers.llm.base import LLMProvider
from providers.llm.anthropic_provider import AnthropicProvider
from providers.llm.deepseek_provider import DeepSeekProvider
from providers.llm.openai_provider import OpenAIProvider

ProviderFactory = Callable[[LLMConfig], LLMProvider]


class ProviderRegistry:
    """Register and resolve LLM provider implementations."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        if not name:
            raise ValueError("Provider name is required.")
        self._factories[name] = factory

    def resolve(self, name: str, config: LLMConfig) -> LLMProvider:
        factory = self._factories.get(name)
        if factory is None:
            available = ", ".join(sorted(self._factories)) or "none"
            raise KeyError(f"Unknown LLM provider '{name}'. Available: {available}")
        return factory(config)

    def list_providers(self) -> list[str]:
        return sorted(self._factories)


def create_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("openai", OpenAIProvider)
    registry.register("deepseek", DeepSeekProvider)
    registry.register("anthropic", AnthropicProvider)
    return registry
