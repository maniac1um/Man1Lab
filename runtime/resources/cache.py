"""Runtime resource cache policy metadata."""

from __future__ import annotations

from enum import Enum


class CachePolicy(str, Enum):
    """Deterministic cache policy metadata for runtime-owned resources."""

    NEVER = "never"
    SESSION = "session"
    RUNTIME = "runtime"


def cache_policy_label(policy: CachePolicy) -> str:
    """Return a human-readable cache policy label for profiling output."""
    labels = {
        CachePolicy.NEVER: "No Cache",
        CachePolicy.SESSION: "Session Cache",
        CachePolicy.RUNTIME: "Runtime Cache",
    }
    return labels[policy]
