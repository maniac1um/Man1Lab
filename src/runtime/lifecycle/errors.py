"""Runtime lifecycle errors."""

from __future__ import annotations


class RuntimeLifecycleError(RuntimeError):
    """Base error for runtime lifecycle operations."""


class RuntimeTransitionError(RuntimeLifecycleError):
    """Raised when a lifecycle state transition is not permitted."""


class RuntimeNotReadyError(RuntimeLifecycleError):
    """Raised when the runtime is not in the READY state."""
