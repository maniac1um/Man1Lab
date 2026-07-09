"""Tests for console startup banner and terminal styling."""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from runtime.console.banner import build_startup_banner, render_logo
from runtime.console.renderer import ConsoleRenderer
from runtime.console.terminal_style import TerminalStyle, supports_color
from runtime.session.state import SessionState


def _mock_platform() -> MagicMock:
    platform = MagicMock()
    platform.version.return_value = "1.2.4"
    platform.settings.workspace_root = "/tmp/workspace"
    platform.current_model.return_value = None
    platform.is_runtime_ready.return_value = True
    platform.runtime.state.value = "ready"
    session = MagicMock()
    session.state = SessionState.ACTIVE
    platform.session.return_value = session
    return platform


class TerminalStyleTest(unittest.TestCase):
    def test_plain_text_when_color_disabled(self) -> None:
        style = TerminalStyle(enabled=False)
        self.assertEqual(style.cyan("MAN1LAB"), "MAN1LAB")
        self.assertEqual(style.dim("label"), "label")

    def test_ansi_codes_when_color_enabled(self) -> None:
        style = TerminalStyle(enabled=True)
        self.assertIn("\033[36m", style.cyan("MAN1LAB"))
        self.assertIn("\033[0m", style.cyan("MAN1LAB"))

    def test_supports_color_false_for_stringio(self) -> None:
        self.assertFalse(supports_color(StringIO()))


class BannerLogoTest(unittest.TestCase):
    @patch("runtime.console.banner._render_pyfiglet_logo", return_value=None)
    def test_static_fallback_logo_is_compact(self, _mock_figlet: MagicMock) -> None:
        style = TerminalStyle(enabled=False)
        lines = render_logo(style)
        self.assertGreaterEqual(len(lines), 3)
        self.assertLessEqual(len(lines), 12)
        joined = "\n".join(lines)
        self.assertIn("/  |/  /", joined)

    @patch("runtime.console.banner._render_pyfiglet_logo", return_value="FIGLET\nLOGO")
    def test_prefers_pyfiglet_when_available(self, _mock_figlet: MagicMock) -> None:
        style = TerminalStyle(enabled=False)
        lines = render_logo(style)
        self.assertEqual(lines, ["FIGLET", "LOGO"])


class StartupBannerTest(unittest.TestCase):
    def test_banner_includes_status_and_quick_start(self) -> None:
        banner = build_startup_banner(_mock_platform(), style=TerminalStyle(enabled=False))
        self.assertIn("Research Paper Reproduction Platform", banner)
        self.assertIn("MAN1LAB 1.2.4", banner)
        self.assertIn("Workspace", banner)
        self.assertIn("/tmp/workspace", banner)
        self.assertIn("Active Model", banner)
        self.assertIn("Runtime", banner)
        self.assertIn("READY", banner)
        self.assertIn("Session", banner)
        self.assertIn("ACTIVE", banner)
        self.assertIn("Quick start:", banner)
        self.assertIn("analyze <paper.pdf>", banner)
        self.assertIn("discover", banner)
        self.assertIn("plan-all", banner)
        self.assertIn('Type "help" to see all commands.', banner)

    def test_banner_uses_separators(self) -> None:
        banner = build_startup_banner(_mock_platform(), style=TerminalStyle(enabled=False))
        self.assertIn("─" * 52, banner)

    def test_banner_colors_runtime_and_session_when_enabled(self) -> None:
        banner = build_startup_banner(_mock_platform(), style=TerminalStyle(enabled=True))
        self.assertIn("\033[32mREADY\033[0m", banner)
        self.assertIn("\033[32mACTIVE\033[0m", banner)
        self.assertIn("\033[2mWorkspace", banner)

    def test_banner_warning_and_error_tones(self) -> None:
        platform = _mock_platform()
        platform.is_runtime_ready.return_value = False
        platform.runtime.state.value = "bootstrapping"
        platform.session.return_value.state = SessionState.NEW

        banner = build_startup_banner(platform, style=TerminalStyle(enabled=True))
        self.assertIn("\033[33mBOOTSTRAPPING\033[0m", banner)
        self.assertIn("\033[33mNEW\033[0m", banner)

        platform.runtime.state.value = "stopped"
        banner = build_startup_banner(platform, style=TerminalStyle(enabled=True))
        self.assertIn("\033[31mSTOPPED\033[0m", banner)


class ConsoleRendererBannerTest(unittest.TestCase):
    def test_render_banner_writes_to_output(self) -> None:
        output = StringIO()
        renderer = ConsoleRenderer(output=output, use_color=False)
        renderer.render_banner(_mock_platform())
        text = output.getvalue()
        self.assertIn("MAN1LAB 1.2.4", text)
        self.assertNotIn("\033[", text)
