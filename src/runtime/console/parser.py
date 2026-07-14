"""Console command-line parsing."""

from __future__ import annotations

import os
import shlex


def parse_command_line(line: str) -> tuple[str, list[str]]:
    """Parse a user line into a command name and arguments."""
    stripped = line.strip()
    if not stripped:
        return "", []
    parts = shlex.split(stripped, posix=os.name != "nt")
    if os.name == "nt":
        parts = [_strip_matching_quotes(part) for part in parts]
    return parts[0].lower(), parts[1:]


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
