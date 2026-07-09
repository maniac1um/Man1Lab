"""ANSI terminal styling with graceful degradation."""

from __future__ import annotations

import os
import sys
from typing import TextIO

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def supports_color(stream: TextIO | None = None) -> bool:
    """Return True when ANSI styling is likely to render correctly."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    target = stream or sys.stdout
    if not hasattr(target, "isatty") or not target.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return True


class TerminalStyle:
    """Apply ANSI colors when enabled; otherwise return plain text."""

    def __init__(self, *, enabled: bool | None = None, stream: TextIO | None = None) -> None:
        if enabled is None:
            enabled = supports_color(stream)
        self.enabled = enabled

    def wrap(self, text: str, *codes: str) -> str:
        if not self.enabled or not codes:
            return text
        prefix = "".join(codes)
        return f"{prefix}{text}{RESET}"

    def dim(self, text: str) -> str:
        return self.wrap(text, DIM)

    def bold(self, text: str) -> str:
        return self.wrap(text, BOLD)

    def cyan(self, text: str) -> str:
        return self.wrap(text, CYAN)

    def blue(self, text: str) -> str:
        return self.wrap(text, BLUE)

    def green(self, text: str) -> str:
        return self.wrap(text, GREEN)

    def yellow(self, text: str) -> str:
        return self.wrap(text, YELLOW)

    def red(self, text: str) -> str:
        return self.wrap(text, RED)
