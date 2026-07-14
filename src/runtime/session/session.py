"""Runtime session — user interaction lifetime owner."""

from __future__ import annotations

import time
from typing import Any

from runtime.session.errors import SessionTransitionError
from runtime.session.state import SessionState, validate_transition
from runtime.session.workspace import SessionWorkspace


class RuntimeSession:
    """Own user interaction lifetime without workflow execution or persistence."""

    def __init__(self) -> None:
        self._state = SessionState.NEW
        self._workspace = SessionWorkspace()
        self._opened_at: float | None = None
        self._closed_at: float | None = None

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def workspace(self) -> SessionWorkspace:
        return self._workspace

    @property
    def current_paper(self) -> Any | None:
        return self._workspace.current_paper

    @property
    def current_analysis(self) -> Any | None:
        return self._workspace.current_analysis

    @property
    def current_discovery(self) -> Any | None:
        return self._workspace.current_discovery

    @property
    def current_execution_strategy(self) -> Any | None:
        return self._workspace.current_strategy

    def is_active(self) -> bool:
        return self._state is SessionState.ACTIVE

    def open(self) -> None:
        """Activate the session for user interaction."""
        if self._state is not SessionState.NEW:
            raise SessionTransitionError(
                f"Cannot open session from state {self._state.value}."
            )
        self._transition(SessionState.ACTIVE)
        self._opened_at = time.monotonic()

    def close(self) -> None:
        """Close the session and end user interaction lifetime."""
        if self._state is not SessionState.ACTIVE:
            raise SessionTransitionError(
                f"Cannot close session from state {self._state.value}."
            )
        self._transition(SessionState.CLOSED)
        self._closed_at = time.monotonic()

    def duration_s(self) -> float | None:
        """Return session duration in seconds when opened; ``None`` if never opened."""
        if self._opened_at is None:
            return None
        end = self._closed_at if self._closed_at is not None else time.monotonic()
        return end - self._opened_at

    def profile_state(self) -> str:
        """Return the session state label for profiling output."""
        return self._state.value.upper()

    def _transition(self, target: SessionState) -> None:
        validate_transition(self._state, target)
        self._state = target
