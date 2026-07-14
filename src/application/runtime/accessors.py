"""Runtime infrastructure accessors for the application composition layer."""

from __future__ import annotations

from typing import Any

from configuration.models import AppSettings
from prompt.loader import PromptLoader
from providers.llm.manager import LLMManager
from providers.llm.provider_registry import ProviderRegistry
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
    RuntimeResourceManager,
)


class RuntimeInfrastructure:
    """Resolve runtime-owned infrastructure resources through the resource manager."""

    def __init__(self, manager: RuntimeResourceManager) -> None:
        self._manager = manager

    @property
    def manager(self) -> RuntimeResourceManager:
        return self._manager

    def configuration(self) -> AppSettings:
        return self._manager.get(RESOURCE_CONFIGURATION)

    def prompt_registry(self) -> PromptLoader:
        return self._manager.get(RESOURCE_PROMPT_REGISTRY)

    def llm_manager(self) -> LLMManager:
        return self._manager.get(RESOURCE_LLM_MANAGER)

    def provider_registry(self) -> ProviderRegistry:
        return self._manager.get(RESOURCE_PROVIDER_REGISTRY)

    def lazy_resource(self, name: str) -> Any:
        return self._manager.require(name)
