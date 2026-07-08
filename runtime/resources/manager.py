"""Runtime resource manager — registration, resolution, metadata, and statistics."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from runtime.lazy.lazy_resource import LazyResource
from runtime.lazy.resource_registry import (
    RESOURCE_CONFIGURATION,
    RESOURCE_LLM_MANAGER,
    RESOURCE_PROMPT_REGISTRY,
    RESOURCE_PROVIDER_REGISTRY,
    RUNTIME_RESOURCE_LABELS,
    RUNTIME_RESOURCE_ORDER,
    ResourceRegistry,
)
from runtime.resources.cache import CachePolicy
from runtime.resources.descriptor import RuntimeResourceDescriptor
from runtime.resources.health import RuntimeResourceHealth

T = TypeVar("T")


@dataclass
class _ManagedResource:
    name: str
    resource_type: str
    lazy: bool
    cache_policy: CachePolicy
    health: RuntimeResourceHealth
    created_at: float
    last_accessed: float | None
    access_count: int
    lazy_resource: LazyResource[Any]


@dataclass(frozen=True)
class RuntimeResourceStatistics:
    """Aggregate runtime resource metadata counters."""

    total_resources: int
    initialized_count: int
    deferred_count: int
    ready_count: int
    failed_count: int
    total_access_count: int


class RuntimeResourceManager:
    """Own runtime resource lifecycle metadata without business logic."""

    def __init__(self) -> None:
        self._registry = ResourceRegistry()
        self._records: dict[str, _ManagedResource] = {}

    def register(
        self,
        name: str,
        factory: Callable[[], T],
        *,
        resource_type: str,
        lazy: bool = True,
        cache_policy: CachePolicy = CachePolicy.RUNTIME,
    ) -> None:
        if name in self._records:
            raise ValueError(f"Runtime resource '{name}' is already registered.")
        lazy_resource = self._registry.register(name, factory)
        self._records[name] = _ManagedResource(
            name=name,
            resource_type=resource_type,
            lazy=lazy,
            cache_policy=cache_policy,
            health=RuntimeResourceHealth.DEFERRED,
            created_at=time.monotonic(),
            last_accessed=None,
            access_count=0,
            lazy_resource=lazy_resource,
        )

    def require(self, name: str) -> LazyResource[Any]:
        return self._require_record(name).lazy_resource

    def get(self, name: str) -> Any:
        record = self._require_record(name)
        record.access_count += 1
        record.last_accessed = time.monotonic()

        if record.health == RuntimeResourceHealth.FAILED:
            return record.lazy_resource.get()

        if record.lazy_resource.is_initialized():
            record.health = RuntimeResourceHealth.READY
            return record.lazy_resource.get()

        record.health = RuntimeResourceHealth.INITIALIZING
        try:
            value = record.lazy_resource.get()
            record.health = RuntimeResourceHealth.READY
            return value
        except BaseException:
            record.health = RuntimeResourceHealth.FAILED
            raise

    def descriptor(self, name: str) -> RuntimeResourceDescriptor:
        record = self._require_record(name)
        health = self._resolved_health(record)
        return RuntimeResourceDescriptor(
            name=record.name,
            resource_type=record.resource_type,
            lazy=record.lazy,
            initialized=record.lazy_resource.is_initialized(),
            cache_policy=record.cache_policy,
            health=health,
            created_at=record.created_at,
            last_accessed=record.last_accessed,
            access_count=record.access_count,
        )

    def descriptors(self) -> tuple[RuntimeResourceDescriptor, ...]:
        ordered: list[RuntimeResourceDescriptor] = []
        seen: set[str] = set()
        for name in RUNTIME_RESOURCE_ORDER:
            if name in self._records:
                ordered.append(self.descriptor(name))
                seen.add(name)
        for name in sorted(self._records):
            if name not in seen:
                ordered.append(self.descriptor(name))
        return tuple(ordered)

    def statistics(self) -> RuntimeResourceStatistics:
        descriptors = self.descriptors()
        return RuntimeResourceStatistics(
            total_resources=len(descriptors),
            initialized_count=sum(1 for item in descriptors if item.initialized),
            deferred_count=sum(
                1 for item in descriptors if item.health is RuntimeResourceHealth.DEFERRED
            ),
            ready_count=sum(1 for item in descriptors if item.health is RuntimeResourceHealth.READY),
            failed_count=sum(1 for item in descriptors if item.health is RuntimeResourceHealth.FAILED),
            total_access_count=sum(item.access_count for item in descriptors),
        )

    def profile_entries(self) -> tuple[tuple[str, str], ...]:
        entries: list[tuple[str, str]] = []
        for descriptor in self.descriptors():
            label = RUNTIME_RESOURCE_LABELS.get(descriptor.name, descriptor.name)
            entries.append((label, descriptor.profile_status()))
        return tuple(entries)

    def _require_record(self, name: str) -> _ManagedResource:
        record = self._records.get(name)
        if record is None:
            raise KeyError(f"Runtime resource '{name}' is not registered.")
        return record

    @staticmethod
    def _resolved_health(record: _ManagedResource) -> RuntimeResourceHealth:
        if record.health is RuntimeResourceHealth.FAILED:
            return RuntimeResourceHealth.FAILED
        if record.lazy_resource.is_initialized():
            return RuntimeResourceHealth.READY
        return record.health


# Re-export resource name constants for application wiring convenience.
__all__ = [
    "RESOURCE_CONFIGURATION",
    "RESOURCE_LLM_MANAGER",
    "RESOURCE_PROMPT_REGISTRY",
    "RESOURCE_PROVIDER_REGISTRY",
    "RuntimeResourceManager",
    "RuntimeResourceStatistics",
]
