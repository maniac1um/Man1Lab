"""Console rendering helpers."""

from __future__ import annotations

import sys
from typing import Any, TextIO

from runtime.console.banner import build_startup_banner
from runtime.console.platform import ConsolePlatform
from runtime.console.terminal_style import TerminalStyle


class ConsoleRenderer:
    """Render console banners, help, and command output."""

    def __init__(self, output: TextIO | None = None, *, use_color: bool | None = None) -> None:
        self._output = output or sys.stdout
        self._style = TerminalStyle(enabled=use_color, stream=self._output)

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
        self.write(build_startup_banner(platform, style=self._style))

    def render_help(self, registry) -> None:
        self.write("Available commands:")
        for command in registry.commands():
            self.write(f"  {command.name:<12} {command.help}")
        self.write("")
        self.write("Workflow:")
        self.write("  analyze <paper.pdf>  →  discover  →  plan  →  execute")
        self.write("")
        self.write("Pipeline:")
        self.write("  plan-all <paper.pdf>   Run analyze, discover, and plan")
        self.write("  execute-all            Run the planned execution graph")
        self.write("  reproduce <paper.pdf>  Run plan-all then execute")
        self.write("")
        self.write("Execution:")
        self.write("  execution status [run_id]   Show current run task status")
        self.write("  execution report [run_id]   Show execution report and artifacts")

    def render_command_success(
        self,
        *,
        message: str,
        generated: tuple[str, ...],
        next_command: str,
    ) -> None:
        self.write(f"✓ {message}")
        if generated:
            self.write("")
            self.write("Generated:")
            for item in generated:
                self.write(f"  - {item}")
        self.write("")
        self.write(f"Next: {next_command}")

    def render_json(self, payload: Any) -> None:
        if hasattr(payload, "model_dump_json"):
            self.write(payload.model_dump_json(indent=2))
        else:
            self.write(str(payload))
