"""Runtime session lifecycle state machine."""

from __future__ import annotations

from enum import Enum

from runtime.session.errors import SessionTransitionError


class SessionState(str, Enum):
    """Deterministic runtime session lifecycle states."""

    NEW = "new"
    ACTIVE = "active"
    CLOSED = "closed"


_ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.NEW: frozenset({SessionState.ACTIVE}),
    SessionState.ACTIVE: frozenset({SessionState.CLOSED}),
    SessionState.CLOSED: frozenset(),
}


def validate_transition(current: SessionState, target: SessionState) -> None:
    """Raise SessionTransitionError when the transition is not allowed."""
    allowed = _ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise SessionTransitionError(
            f"Invalid session transition: {current.value} -> {target.value}"
        )


def allowed_transitions(state: SessionState) -> frozenset[SessionState]:
    """Return permitted target states from the given state."""
    return _ALLOWED_TRANSITIONS[state]
