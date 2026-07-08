"""Runtime context container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.lazy.lazy_resource import LazyResource
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RuntimeResourceManager,
)


@dataclass
class RuntimeContext:
    """Container for runtime-owned platform resources.

    Infrastructure resources are managed through ``RuntimeResourceManager`` with
    lazy initialization as an internal implementation detail.
    """

    resource_manager: RuntimeResourceManager
    workspace: Any | None = None
    session: Any | None = None

    @classmethod
    def create(
        cls,
        *,
        resource_manager: RuntimeResourceManager | None = None,
    ) -> RuntimeContext:
        """Create a runtime context with an empty resource manager."""
        return cls(resource_manager=resource_manager or RuntimeResourceManager())

    @property
    def resources(self) -> RuntimeResourceManager:
        """Backward-compatible alias for the runtime resource manager."""
        return self.resource_manager

    @property
    def configuration(self) -> LazyResource[Any]:
        return self.resource_manager.require(RESOURCE_CONFIGURATION)

    @property
    def prompt_registry(self) -> LazyResource[Any]:
        return self.resource_manager.require(RESOURCE_PROMPT_REGISTRY)

    @property
    def llm_manager(self) -> LazyResource[Any]:
        return self.resource_manager.require(RESOURCE_LLM_MANAGER)

    def resource_status_entries(self) -> tuple[tuple[str, str], ...]:
        """Return profiling labels with health and cache metadata."""
        return self.resource_manager.profile_entries()
