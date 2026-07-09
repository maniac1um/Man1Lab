"""Startup banner composition for the Man1Lab console."""

from __future__ import annotations

from runtime.console.platform import ConsolePlatform
from runtime.console.terminal_style import TerminalStyle

FIGLET_FONTS = ("slant", "standard", "small")
MAX_LOGO_LINES = 12
LABEL_WIDTH = 14

# Slant-style static fallback when pyfiglet is unavailable.
_STATIC_LOGO = """\
    __  ______    _   _______    ___    ____
   /  |/  /   |  / | / <  / /   /   |  / __ )
  / /|_/ / /| | /  |/ // / /   / /| | / __  |
 / /  / / ___ |/ /|  // / /___/ ___ |/ /_/ /
/_/  /_/_/  |_/_/ |_//_/_____/_/  |_/_____/"""

_QUICK_START_COMMANDS = (
    "analyze <paper.pdf>",
    "discover",
    "plan",
    "plan-all",
)


def render_logo(style: TerminalStyle) -> list[str]:
    """Render a compact MAN1LAB logo via pyfiglet or static fallback."""
    logo = _render_pyfiglet_logo() or _STATIC_LOGO
    lines = logo.rstrip().splitlines()
    if style.enabled:
        return [style.cyan(line) for line in lines]
    return lines


def build_startup_banner(platform: ConsolePlatform, *, style: TerminalStyle | None = None) -> str:
    """Build the full startup banner as a single string."""
    resolved_style = style or TerminalStyle()
    lines: list[str] = []

    lines.extend(render_logo(resolved_style))
    lines.append("")
    lines.append(
        resolved_style.bold("Research Paper Reproduction Platform")
        if resolved_style.enabled
        else "Research Paper Reproduction Platform"
    )
    lines.append(f"MAN1LAB {platform.version()}")

    separator = _separator(width=52)
    lines.append("")
    lines.append(resolved_style.dim(separator) if resolved_style.enabled else separator)

    for label, value in _status_rows(platform):
        display_value, tone = _status_tone(label, value)
        styled_value = _apply_tone(resolved_style, display_value, tone)
        label_text = f"{label:<{LABEL_WIDTH}}"
        if resolved_style.enabled:
            label_text = resolved_style.dim(label_text)
        lines.append(f"{label_text}{styled_value}")

    lines.append(resolved_style.dim(separator) if resolved_style.enabled else separator)
    lines.append("")
    lines.append("Quick start:")
    for command in _QUICK_START_COMMANDS:
        lines.append(f"  {command}")
    lines.append("")
    lines.append('Type "help" to see all commands.')

    return "\n".join(lines)


def _separator(*, width: int) -> str:
    return "─" * width


def _render_pyfiglet_logo() -> str | None:
    try:
        import pyfiglet
    except ImportError:
        return None

    for font in FIGLET_FONTS:
        try:
            rendered = pyfiglet.figlet_format("MAN1LAB", font=font)
        except Exception:
            continue
        text = rendered.rstrip("\n")
        line_count = len([line for line in text.splitlines() if line.strip()])
        if 1 <= line_count <= MAX_LOGO_LINES:
            return text
    return None


def _status_rows(platform: ConsolePlatform) -> list[tuple[str, str]]:
    current = platform.current_model()
    if current is None:
        model_label = "none"
    else:
        model_label = f"{current.profile_name} ({current.provider}/{current.model})"

    runtime_label = "ready" if platform.is_runtime_ready() else platform.runtime.state.value
    session_label = platform.session().state.value

    return [
        ("Workspace", str(platform.settings.workspace_root)),
        ("Active Model", model_label),
        ("Runtime", runtime_label),
        ("Session", session_label),
    ]


def _status_tone(label: str, value: str) -> tuple[str, str]:
    normalized = value.strip().lower()

    if label == "Runtime":
        if normalized == "ready":
            return "READY", "green"
        if normalized in {"bootstrapping", "shutting_down"}:
            return normalized.upper(), "yellow"
        if normalized == "stopped":
            return "STOPPED", "red"
        return normalized.upper(), "neutral"

    if label == "Session":
        if normalized == "active":
            return "ACTIVE", "green"
        if normalized == "new":
            return "NEW", "yellow"
        if normalized == "closed":
            return "CLOSED", "neutral"
        return normalized.upper(), "neutral"

    return value, "neutral"


def _apply_tone(style: TerminalStyle, text: str, tone: str) -> str:
    if tone == "green":
        return style.green(text)
    if tone == "yellow":
        return style.yellow(text)
    if tone == "red":
        return style.red(text)
    return text
