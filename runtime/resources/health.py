"""Runtime resource health metadata."""

from __future__ import annotations

from enum import Enum


class RuntimeResourceHealth(str, Enum):
    """Runtime-owned resource health states (metadata only)."""

    DEFERRED = "deferred"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"
