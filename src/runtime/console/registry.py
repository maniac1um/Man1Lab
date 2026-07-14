"""Interactive console command registry."""

from __future__ import annotations

from runtime.console.command import ConsoleCommand


class CommandRegistry:
    """Register and resolve console commands without central dispatch branches."""

    def __init__(self) -> None:
        self._commands: dict[str, ConsoleCommand] = {}

    def register(self, command: ConsoleCommand) -> None:
        if command.name in self._commands:
            raise ValueError(f"Console command '{command.name}' is already registered.")
        self._commands[command.name] = command

    def get(self, name: str) -> ConsoleCommand | None:
        return self._commands.get(name)

    def commands(self) -> tuple[ConsoleCommand, ...]:
        return tuple(self._commands[name] for name in sorted(self._commands))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._commands))
