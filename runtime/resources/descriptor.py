"""Immutable runtime resource metadata descriptors."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.resources.cache import CachePolicy, cache_policy_label
from runtime.resources.health import RuntimeResourceHealth


@dataclass(frozen=True)
class RuntimeResourceDescriptor:
    """Immutable metadata describing a runtime-owned resource."""

    name: str
    resource_type: str
    lazy: bool
    initialized: bool
    cache_policy: CachePolicy
    health: RuntimeResourceHealth
    created_at: float
    last_accessed: float | None
    access_count: int

    def profile_status(self) -> str:
        """Format health and cache policy for profiling output."""
        health_label = self.health.value.upper()
        if self.health == RuntimeResourceHealth.READY and self.cache_policy is not CachePolicy.NEVER:
            return f"{health_label} ({cache_policy_label(self.cache_policy)})"
        return health_label
