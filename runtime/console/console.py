"""Man1Lab interactive console."""

from __future__ import annotations

from collections.abc import Callable
from typing import TextIO

from runtime.console.builtins import ensure_session_open, register_builtin_commands
from runtime.console.command import ConsoleContext, ConsolePlatform
from runtime.console.parser import parse_command_line
from runtime.console.registry import CommandRegistry
from runtime.console.renderer import ConsoleRenderer
from runtime.session.state import SessionState


class Man1LabConsole:
    """Command-driven interactive console over the platform facade and runtime session."""

    PROMPT = "man1lab> "

    def __init__(
        self,
        platform: ConsolePlatform,
        *,
        registry: CommandRegistry | None = None,
        renderer: ConsoleRenderer | None = None,
        input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._platform = platform
        self._registry = registry or CommandRegistry()
        if registry is None:
            register_builtin_commands(self._registry)
        self._renderer = renderer or ConsoleRenderer()
        self._input_fn = input_fn or input

    @property
    def registry(self) -> CommandRegistry:
        return self._registry

    def run(self) -> int:
        """Run the interactive console until exit."""
        ctx = ConsoleContext(
            platform=self._platform,
            renderer=self._renderer,
            registry=self._registry,
        )
        ensure_session_open(ctx)
        self._renderer.render_banner(self._platform)

        while True:
            try:
                line = self._input_fn(self.PROMPT)
            except EOFError:
                return self._shutdown()
            except KeyboardInterrupt:
                self._renderer.write("")
                self._renderer.write("Interrupted.")
                continue

            name, args = parse_command_line(line)
            if not name:
                continue

            command = self._registry.get(name)
            if command is None:
                self._renderer.write_error(f"Unknown command: {name}")
                continue

            try:
                exit_code = command.handler(ctx, args)
            except (ValueError, FileNotFoundError) as exc:
                self._renderer.write_error(f"Error: {exc}")
                continue
            except Exception as exc:
                self._renderer.write_error(f"Error: {exc}")
                continue

            if exit_code != 0:
                return self._shutdown()

        return 0

    def dispatch(self, line: str) -> int:
        """Dispatch a single command line (used by tests)."""
        ctx = ConsoleContext(
            platform=self._platform,
            renderer=self._renderer,
            registry=self._registry,
        )
        ensure_session_open(ctx)
        name, args = parse_command_line(line)
        if not name:
            return 0
        command = self._registry.get(name)
        if command is None:
            self._renderer.write_error(f"Unknown command: {name}")
            return 0
        exit_code = command.handler(ctx, args)
        if exit_code != 0:
            return self._shutdown()
        return 0

    def _shutdown(self) -> int:
        if self._platform.is_session_active():
            self._platform.close_session()
        self._renderer.write("Goodbye.")
        return 0


def run_console(
    platform: ConsolePlatform,
    *,
    input_fn: Callable[[str], str] | None = None,
    output: TextIO | None = None,
) -> int:
    """Start the Man1Lab interactive console."""
    renderer = ConsoleRenderer(output=output)
    console = Man1LabConsole(platform, renderer=renderer, input_fn=input_fn)
    return console.run()
