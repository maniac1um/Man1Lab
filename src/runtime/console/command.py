"""Console command primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from runtime.console.platform import ConsolePlatform
from runtime.console.renderer import ConsoleRenderer
from runtime.session.session import RuntimeSession

if TYPE_CHECKING:
    from runtime.console.registry import CommandRegistry


CommandHandler = Callable[["ConsoleContext", list[str]], int]


@dataclass(frozen=True)
class ConsoleCommand:
    """Registered interactive console command."""

    name: str
    help: str
    handler: CommandHandler


@dataclass
class ConsoleContext:
    """Execution context for a single console command."""

    platform: ConsolePlatform
    renderer: ConsoleRenderer
    registry: "CommandRegistry"

    @property
    def session(self) -> RuntimeSession:
        return self.platform.session()
