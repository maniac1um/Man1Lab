"""Console input with optional prompt_toolkit enhancements."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

_HISTORY_ENV = "MAN1LAB_CONSOLE_HISTORY"
_DEFAULT_HISTORY = Path.home() / ".man1lab" / "console_history"


def create_console_input_fn(
    command_names: Iterable[str] | None = None,
    *,
    history_path: Path | None = None,
) -> Callable[[str], str]:
    """Return an input function with history and completion when prompt_toolkit is available."""
    names = tuple(sorted(command_names or ()))
    path = history_path or _DEFAULT_HISTORY

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
    except ImportError:
        return input

    path.parent.mkdir(parents=True, exist_ok=True)
    completer = WordCompleter(names, ignore_case=True) if names else None
    session = PromptSession(
        history=FileHistory(str(path)),
        completer=completer,
    )

    def _prompt_toolkit_input(prompt: str) -> str:
        return session.prompt(prompt)

    return _prompt_toolkit_input


def prompt_toolkit_available() -> bool:
    """Return whether prompt_toolkit can be imported."""
    try:
        import prompt_toolkit  # noqa: F401
    except ImportError:
        return False
    return True
