"""Runtime lifecycle state machine."""

from __future__ import annotations

from enum import Enum

from runtime.lifecycle.errors import RuntimeTransitionError


class RuntimeState(str, Enum):
    """Deterministic platform runtime lifecycle states."""

    NEW = "new"
    BOOTSTRAPPING = "bootstrapping"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


_ALLOWED_TRANSITIONS: dict[RuntimeState, frozenset[RuntimeState]] = {
    RuntimeState.NEW: frozenset({RuntimeState.BOOTSTRAPPING}),
    RuntimeState.BOOTSTRAPPING: frozenset({RuntimeState.READY, RuntimeState.STOPPED}),
    RuntimeState.READY: frozenset({RuntimeState.SHUTTING_DOWN}),
    RuntimeState.SHUTTING_DOWN: frozenset({RuntimeState.STOPPED}),
    RuntimeState.STOPPED: frozenset(),
}


def validate_transition(current: RuntimeState, target: RuntimeState) -> None:
    """Raise RuntimeTransitionError when the transition is not allowed."""
    allowed = _ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise RuntimeTransitionError(
            f"Invalid runtime transition: {current.value} -> {target.value}"
        )


def allowed_transitions(state: RuntimeState) -> frozenset[RuntimeState]:
    """Return permitted target states from the given state."""
    return _ALLOWED_TRANSITIONS[state]
