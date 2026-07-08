"""Platform runtime lifecycle owner."""

from __future__ import annotations

from runtime.context import RuntimeContext
from runtime.lifecycle.errors import RuntimeNotReadyError, RuntimeTransitionError
from runtime.session.errors import SessionTransitionError
from runtime.session.session import RuntimeSession
from runtime.session.state import SessionState
from runtime.state import RuntimeState as PlatformRuntimeState
from runtime.state import validate_transition


class PlatformRuntime:
    """Own platform process lifecycle without business workflow execution."""

    def __init__(self) -> None:
        self._state = PlatformRuntimeState.NEW
        self._context: RuntimeContext | None = None
        self._session: RuntimeSession | None = None

    @property
    def state(self) -> PlatformRuntimeState:
        return self._state

    @property
    def context(self) -> RuntimeContext:
        if self._context is None:
            raise RuntimeNotReadyError("Runtime context is not available.")
        return self._context

    @property
    def session(self) -> RuntimeSession:
        if self._session is None:
            raise RuntimeNotReadyError("Runtime session is not available.")
        return self._session

    def is_ready(self) -> bool:
        return self._state == PlatformRuntimeState.READY

    def is_session_active(self) -> bool:
        if self._session is None:
            return False
        return self._session.is_active()

    def close_session(self) -> None:
        """Close the runtime session when active."""
        if self._session is None:
            raise RuntimeNotReadyError("Runtime session is not available.")
        self._session.close()

    def startup(self) -> RuntimeContext:
        """Bootstrap the runtime and transition to READY."""
        if self._state is not PlatformRuntimeState.NEW:
            raise RuntimeTransitionError(
                f"Cannot start runtime from state {self._state.value}."
            )

        self._transition(PlatformRuntimeState.BOOTSTRAPPING)
        try:
            self._context = RuntimeContext.create()
            self._session = RuntimeSession()
            self._context.session = self._session
            self._transition(PlatformRuntimeState.READY)
        except Exception:
            self._transition(PlatformRuntimeState.STOPPED)
            self._context = None
            self._session = None
            raise
        return self._context

    def shutdown(self) -> None:
        """Shut down the runtime and transition to STOPPED."""
        if self._state is PlatformRuntimeState.STOPPED:
            raise RuntimeTransitionError("Runtime is already stopped.")

        if self._state is not PlatformRuntimeState.READY:
            raise RuntimeTransitionError(
                f"Cannot shut down runtime from state {self._state.value}."
            )

        self._transition(PlatformRuntimeState.SHUTTING_DOWN)
        if self._session is not None and self._session.state is SessionState.ACTIVE:
            try:
                self._session.close()
            except SessionTransitionError:
                pass
        self._context = None
        self._session = None
        self._transition(PlatformRuntimeState.STOPPED)

    def _transition(self, target: PlatformRuntimeState) -> None:
        validate_transition(self._state, target)
        self._state = target
