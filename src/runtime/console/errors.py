"""Format exception chains for console error output."""

from __future__ import annotations


def format_exception_chain(exc: BaseException) -> str:
    """Render the full exception chain without swallowing root causes."""
    lines: list[str] = []
    current: BaseException | None = exc
    depth = 0
    while current is not None:
        prefix = "caused by: " if depth else ""
        lines.append(f"{prefix}{type(current).__module__}.{type(current).__name__}: {current}")
        current = current.__cause__
        depth += 1
    return "\n".join(lines)
