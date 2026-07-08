"""Thread-safe lazy value initialization."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class LazyValue(Generic[T]):
    """Initialize a value once on first access and reuse it thereafter."""

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._value: T | None = None
        self._initialized = False
        self._error: BaseException | None = None
        self._lock = threading.Lock()

    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def status(self) -> str:
        return "initialized" if self._initialized else "deferred"

    def get(self) -> T:
        if self._initialized:
            return self._value  # type: ignore[return-value]

        with self._lock:
            if self._initialized:
                return self._value  # type: ignore[return-value]
            if self._error is not None:
                raise self._error
            try:
                self._value = self._factory()
                self._initialized = True
            except BaseException as exc:
                self._error = exc
                raise
        return self._value  # type: ignore[return-value]
