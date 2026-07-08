"""Wire runtime-owned lazy resources from the application layer."""

from __future__ import annotations

from configuration.bootstrap import initialize_app_configuration
from configuration.models import AppSettings
from prompt.loader import PromptLoader
from providers.llm.manager import LLMManager
from providers.llm.provider_registry import ProviderRegistry, create_default_registry
from runtime.resources.cache import CachePolicy
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
    RuntimeResourceManager,
)


def wire_runtime_resources(
    manager: RuntimeResourceManager,
    *,
    settings: AppSettings | None = None,
    initialize_configuration: bool = True,
) -> None:
    """Register runtime-owned infrastructure resources with cache policy metadata."""
    manager.register(
        RESOURCE_CONFIGURATION,
        lambda: _resolve_configuration(
            settings=settings,
            initialize_configuration=initialize_configuration,
        ),
        resource_type="configuration",
        cache_policy=CachePolicy.RUNTIME,
    )
    manager.register(
        RESOURCE_PROMPT_REGISTRY,
        PromptLoader,
        resource_type="prompt_registry",
        cache_policy=CachePolicy.RUNTIME,
    )
    manager.register(
        RESOURCE_PROVIDER_REGISTRY,
        create_default_registry,
        resource_type="provider_registry",
        cache_policy=CachePolicy.RUNTIME,
    )
    manager.register(
        RESOURCE_LLM_MANAGER,
        lambda: _create_llm_manager(manager),
        resource_type="llm_manager",
        cache_policy=CachePolicy.RUNTIME,
    )


def _resolve_configuration(
    *,
    settings: AppSettings | None,
    initialize_configuration: bool,
) -> AppSettings:
    if settings is not None:
        return settings
    if initialize_configuration:
        return initialize_app_configuration()
    from configuration.legacy_provider import LegacySettingsProvider

    return LegacySettingsProvider().get_settings()


def _create_llm_manager(manager: RuntimeResourceManager) -> LLMManager:
    configuration = manager.get(RESOURCE_CONFIGURATION)
    provider_registry: ProviderRegistry = manager.get(RESOURCE_PROVIDER_REGISTRY)
    return LLMManager(configuration.llm, provider_registry=provider_registry)
