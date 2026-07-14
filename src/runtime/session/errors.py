"""Runtime session lifecycle errors."""

from __future__ import annotations

from runtime.lifecycle.errors import RuntimeLifecycleError


class SessionLifecycleError(RuntimeLifecycleError):
    """Base error for runtime session operations."""


class SessionTransitionError(SessionLifecycleError):
    """Raised when a session state transition is not permitted."""


class SessionNotActiveError(SessionLifecycleError):
    """Raised when an operation requires an active session."""
