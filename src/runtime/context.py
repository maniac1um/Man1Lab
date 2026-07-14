"""Runtime context container."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.execution_store.factory import ExecutionStoreFactory
from runtime.execution_store.file_store import FileExecutionStore
from runtime.lazy.lazy_resource import LazyResource
from runtime.resources.manager import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
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
    execution_store_factory: ExecutionStoreFactory | None = None
    _owned_stores: list[FileExecutionStore] = field(default_factory=list, repr=False)

    def bind_execution_store(self, factory: ExecutionStoreFactory) -> None:
        """Attach a workspace-scoped execution store factory."""
        self.execution_store_factory = factory

    def execution_store(self) -> FileExecutionStore:
        """Return the workspace-scoped execution store for this context."""
        if self.execution_store_factory is None:
            raise RuntimeError("execution store factory is not configured")
        store = self.execution_store_factory.store()
        if store not in self._owned_stores:
            self._owned_stores.append(store)
        return store

    def release_execution_locks(self) -> None:
        """Release all execution writer locks held by this context."""
        if self.execution_store_factory is not None:
            self.execution_store_factory.release_all_writers()
        for store in self._owned_stores:
            store.release_all_writers()

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

    @property
    def provider_registry(self) -> LazyResource[Any]:
        return self.resource_manager.require(RESOURCE_PROVIDER_REGISTRY)

    def resource_status_entries(self) -> tuple[tuple[str, str], ...]:
        """Return profiling labels with health and cache metadata."""
        return self.resource_manager.profile_entries()
