"""Runtime resource management primitives."""

from runtime.resources.cache import CachePolicy, cache_policy_label
from runtime.resources.descriptor import RuntimeResourceDescriptor
from runtime.resources.health import RuntimeResourceHealth
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
    RuntimeResourceManager,
    RuntimeResourceStatistics,
)

__all__ = [
    "CachePolicy",
    "RESOURCE_CONFIGURATION",
    "RESOURCE_LLM_MANAGER",
    "RESOURCE_PROMPT_REGISTRY",
    "RESOURCE_PROVIDER_REGISTRY",
    "RuntimeResourceDescriptor",
    "RuntimeResourceHealth",
    "RuntimeResourceManager",
    "RuntimeResourceStatistics",
    "cache_policy_label",
]
