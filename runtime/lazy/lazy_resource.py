"""Named lazy runtime resource."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from runtime.lazy.lazy_value import LazyValue

T = TypeVar("T")


class LazyResource(LazyValue[T]):
    """A named lazy value owned by the runtime resource registry."""

    def __init__(self, name: str, factory: Callable[[], T]) -> None:
        super().__init__(factory)
        self.name = name
