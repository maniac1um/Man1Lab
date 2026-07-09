"""Format exception chains for LLM provider failures."""

from __future__ import annotations


def root_exception(exc: BaseException) -> BaseException:
    """Return the deepest __cause__ in the exception chain."""
    current = exc
    while current.__cause__ is not None:
        current = current.__cause__
    return current


def root_exception_label(exc: BaseException) -> str:
    """Return a stable label for the root failure type."""
    root = root_exception(exc)
    return f"{type(root).__module__}.{type(root).__name__}"


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
