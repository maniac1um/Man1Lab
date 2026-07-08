"""Console rendering helpers."""

from __future__ import annotations

import sys
from typing import Any, TextIO

from runtime.console.platform import ConsolePlatform


class ConsoleRenderer:
    """Render console banners, help, and command output."""

    def __init__(self, output: TextIO | None = None) -> None:
        self._output = output or sys.stdout

    def write(self, message: str = "", *, end: str = "\n") -> None:
        print(message, file=self._output, end=end)

    def write_error(self, message: str) -> None:
        print(message, file=sys.stderr)

    def clear(self) -> None:
        if hasattr(self._output, "write"):
            try:
                self._output.write("\033[2J\033[H")
                self._output.flush()
                return
            except Exception:
                pass
        self.write("")

    def render_banner(self, platform: ConsolePlatform) -> None:
        self.write("Man1Lab Console")
        self.write("")
        self.write(f"Version ........ {platform.version()}")
        self.write(f"Workspace ...... {platform.settings.workspace_root}")
        current = platform.current_model()
        if current is None:
            model_label = "none"
        else:
            model_label = f"{current.profile_name} ({current.provider}/{current.model})"
        self.write(f"Active Model ... {model_label}")
        runtime_label = "ready" if platform.is_runtime_ready() else platform.runtime.state.value
        session_label = platform.session().state.value
        self.write(f"Runtime ........ {runtime_label}")
        self.write(f"Session ........ {session_label}")
        self.write("")
        self.write("Type 'help' for available commands.")

    def render_help(self, registry) -> None:
        self.write("Available commands:")
        for command in registry.commands():
            self.write(f"  {command.name:<10} {command.help}")

    def render_json(self, payload: Any) -> None:
        if hasattr(payload, "model_dump_json"):
            self.write(payload.model_dump_json(indent=2))
        else:
            self.write(str(payload))
