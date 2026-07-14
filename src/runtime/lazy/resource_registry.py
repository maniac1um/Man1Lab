"""Registry of named lazy runtime resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from runtime.lazy.lazy_resource import LazyResource

T = TypeVar("T")

RESOURCE_CONFIGURATION = "configuration"
RESOURCE_PROMPT_REGISTRY = "prompt_registry"
RESOURCE_LLM_MANAGER = "llm_manager"
RESOURCE_PROVIDER_REGISTRY = "provider_registry"

_RUNTIME_RESOURCE_ORDER = (
    RESOURCE_CONFIGURATION,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROVIDER_REGISTRY,
)

RUNTIME_RESOURCE_ORDER = _RUNTIME_RESOURCE_ORDER

_RUNTIME_RESOURCE_LABELS = {
    RESOURCE_CONFIGURATION: "Configuration",
    RESOURCE_PROMPT_REGISTRY: "Prompt Registry",
    RESOURCE_LLM_MANAGER: "LLM Manager",
    RESOURCE_PROVIDER_REGISTRY: "Provider Registry",
}

RUNTIME_RESOURCE_LABELS = _RUNTIME_RESOURCE_LABELS


class ResourceRegistry:
    """Own named lazy resources without global singleton state."""

    def __init__(self) -> None:
        self._resources: dict[str, LazyResource[Any]] = {}

    def register(self, name: str, factory: Callable[[], T]) -> LazyResource[T]:
        if name in self._resources:
            raise ValueError(f"Runtime resource '{name}' is already registered.")
        resource: LazyResource[T] = LazyResource(name, factory)
        self._resources[name] = resource
        return resource

    def require(self, name: str) -> LazyResource[Any]:
        resource = self._resources.get(name)
        if resource is None:
            raise KeyError(f"Runtime resource '{name}' is not registered.")
        return resource

    def get(self, name: str) -> Any:
        return self.require(name).get()

    def status_entries(self) -> tuple[tuple[str, str], ...]:
        entries: list[tuple[str, str]] = []
        for name in _RUNTIME_RESOURCE_ORDER:
            resource = self._resources.get(name)
            if resource is None:
                continue
            label = _RUNTIME_RESOURCE_LABELS.get(name, name)
            entries.append((label, resource.status))
        return tuple(entries)
