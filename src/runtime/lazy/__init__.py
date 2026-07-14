"""Runtime lazy initialization primitives."""

from runtime.lazy.lazy_resource import LazyResource
from runtime.lazy.lazy_value import LazyValue
from runtime.lazy.resource_registry import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
    ResourceRegistry,
)

__all__ = [
    "LazyResource",
    "LazyValue",
    "ResourceRegistry",
    "RESOURCE_CONFIGURATION",
    "RESOURCE_LLM_MANAGER",
    "RESOURCE_PROMPT_REGISTRY",
    "RESOURCE_PROVIDER_REGISTRY",
]
