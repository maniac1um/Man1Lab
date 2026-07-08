"""Console command-line parsing."""

from __future__ import annotations

import shlex


def parse_command_line(line: str) -> tuple[str, list[str]]:
    """Parse a user line into a command name and arguments."""
    stripped = line.strip()
    if not stripped:
        return "", []
    parts = shlex.split(stripped)
    return parts[0].lower(), parts[1:]
