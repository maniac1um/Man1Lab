"""Tests for Man1Lab interactive console."""

from __future__ import annotations

import ast
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from configuration.models import (
    AppSettings,
    DiscoveryConfig,
    ExecutionPlanningConfig,
    LLMConfig,
    LoggingConfig,
    ParserConfig,
    TrackingConfig,
    WorkflowConfig,
)
from runtime.console import (
    CommandRegistry,
    ConsoleCommand,
    ConsoleContext,
    Man1LabConsole,
    parse_command_line,
    run_console,
)
from runtime.console.builtins import register_builtin_commands
from runtime.console.renderer import ConsoleRenderer
from runtime.session.state import SessionState
from typer.testing import CliRunner

from interfaces.cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _test_settings(temp_dir: Path) -> AppSettings:
    return AppSettings(
        workspace_root=temp_dir / "workspace",
        outputs_dir=temp_dir / "outputs",
        logs_dir=temp_dir / "logs",
        prompts_dir=Path("prompts"),
        paper_path=temp_dir / "paper.pdf",
        parser=ParserConfig(backend="pymupdf"),
        discovery=DiscoveryConfig(enabled=True),
        execution_planning=ExecutionPlanningConfig(enabled=True),
        workflow=WorkflowConfig(max_review_iterations=1),
        llm=LLMConfig(),
        logging=LoggingConfig(),
        tracking=TrackingConfig(enabled=False, backend="noop"),
    )


def _mock_platform() -> MagicMock:
    platform = MagicMock()
    platform.version.return_value = "1.2.3"
    platform.settings.workspace_root = Path("/tmp/workspace")
    platform.current_model.return_value = None
    platform.is_runtime_ready.return_value = True
    platform.is_session_active.return_value = False
    platform.runtime.state.value = "ready"
    session = MagicMock()
    session.state = SessionState.NEW
    session.is_active.return_value = False
    session.workspace.current_paper = None
    session.workspace.current_analysis = None
    session.workspace.current_discovery = None
    session.workspace.current_strategy = None

    def _open() -> None:
        session.state = SessionState.ACTIVE
        session.is_active.return_value = True
        platform.is_session_active.return_value = True

    def _close() -> None:
        session.state = SessionState.CLOSED
        session.is_active.return_value = False
        platform.is_session_active.return_value = False

    session.open.side_effect = _open
    session.close.side_effect = _close
    platform.session.return_value = session
    return platform


class ParserTest(unittest.TestCase):
    def test_parse_simple_command(self) -> None:
        self.assertEqual(parse_command_line("help"), ("help", []))

    def test_parse_command_with_args(self) -> None:
        self.assertEqual(parse_command_line("analyze paper.pdf"), ("analyze", ["paper.pdf"]))

    def test_parse_quoted_args(self) -> None:
        self.assertEqual(
            parse_command_line('model use "my profile"'),
            ("model", ["use", "my profile"]),
        )


class CommandRegistryTest(unittest.TestCase):
    def test_register_and_get(self) -> None:
        registry = CommandRegistry()
        command = ConsoleCommand("help", "help text", lambda _ctx, _args: 0)
        registry.register(command)
        self.assertIs(registry.get("help"), command)

    def test_rejects_duplicate(self) -> None:
        registry = CommandRegistry()
        registry.register(ConsoleCommand("help", "a", lambda _c, _a: 0))
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(ConsoleCommand("help", "b", lambda _c, _a: 0))

    def test_builtin_commands_registered(self) -> None:
        registry = CommandRegistry()
        register_builtin_commands(registry)
        expected = {
            "help",
            "doctor",
            "profile",
            "model",
            "clear",
            "exit",
            "analyze",
            "discover",
            "plan",
        }
        self.assertEqual(set(registry.names()), expected)


class ConsoleDispatchTest(unittest.TestCase):
    def test_help_command(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        self.assertEqual(console.dispatch("help"), 0)
        self.assertIn("Available commands", output.getvalue())

    def test_exit_command(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        self.assertEqual(console.dispatch("exit"), 0)
        platform.close_session.assert_called_once()
        self.assertIn("Goodbye", output.getvalue())

    def test_unknown_command(self) -> None:
        platform = _mock_platform()
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=StringIO()))
        with patch("runtime.console.renderer.print") as mock_print:
            self.assertEqual(console.dispatch("missing"), 0)
            messages = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
            self.assertIn("Unknown command", messages)

    def test_doctor_delegates_to_facade(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        check = MagicMock(status="ok", name="Workspace", message="ready")
        report = MagicMock(healthy=True, checks=[check])
        platform.doctor.return_value = report
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("doctor")
        platform.doctor.assert_called_once()

    def test_profile_delegates_to_facade(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        profile = MagicMock()
        profile.format_report.return_value = "Runtime Profile"
        platform.run_startup_profile.return_value = profile
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("profile")
        platform.run_startup_profile.assert_called_once()


class SessionIntegrationTest(unittest.TestCase):
    def test_console_opens_session_on_run(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        inputs = iter(["exit\n"])
        console = Man1LabConsole(
            platform,
            renderer=ConsoleRenderer(output=output),
            input_fn=lambda _prompt: next(inputs),
        )
        console.run()
        platform.session.return_value.open.assert_called_once()

    def test_analyze_updates_session(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = MagicMock()
        analysis.metadata.title = "Test Paper"
        platform.analyze.return_value = analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch(f"analyze {paper}")

        self.assertEqual(session.workspace.current_paper, paper.resolve())
        self.assertIs(session.workspace.current_analysis, analysis)
        platform.analyze.assert_called_once_with(paper.resolve())

    def test_discover_uses_session_analysis(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = MagicMock()
        discovery = MagicMock()
        discovery.metadata.status.value = "complete"
        session.workspace.current_analysis = analysis
        platform.discover.return_value = discovery

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("discover")

        platform.discover.assert_called_once_with(analysis)
        self.assertIs(session.workspace.current_discovery, discovery)

    def test_plan_uses_session_discovery(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = MagicMock()
        discovery = MagicMock()
        strategy = MagicMock(strategy_id="strategy-1")
        session.workspace.current_analysis = analysis
        session.workspace.current_discovery = discovery
        platform.plan.return_value = strategy

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("plan")

        platform.plan.assert_called_once_with(analysis, discovery)
        self.assertIs(session.workspace.current_strategy, strategy)


class ConsoleRunLoopTest(unittest.TestCase):
    def test_eof_exits_gracefully(self) -> None:
        output = StringIO()
        platform = _mock_platform()

        def _raise_eof(_prompt: str) -> str:
            raise EOFError

        console = Man1LabConsole(
            platform,
            renderer=ConsoleRenderer(output=output),
            input_fn=_raise_eof,
        )
        code = console.run()
        self.assertEqual(code, 0)
        self.assertIn("Goodbye", output.getvalue())

    def test_keyboard_interrupt_continues(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        calls = {"count": 0}

        def _input(_prompt: str) -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise KeyboardInterrupt
            return "exit"

        console = Man1LabConsole(
            platform,
            renderer=ConsoleRenderer(output=output),
            input_fn=_input,
        )
        code = console.run()
        self.assertEqual(code, 0)
        self.assertIn("Interrupted", output.getvalue())

    def test_banner_shows_runtime_details(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        inputs = iter(["exit\n"])
        console = Man1LabConsole(
            platform,
            renderer=ConsoleRenderer(output=output),
            input_fn=lambda _prompt: next(inputs),
        )
        console.run()
        text = output.getvalue()
        self.assertIn("Man1Lab Console", text)
        self.assertIn("Version", text)
        self.assertIn("Workspace", text)
        self.assertIn("Active Model", text)
        self.assertIn("Runtime", text)
        self.assertIn("Session", text)


class FacadeConsoleIntegrationTest(unittest.TestCase):
    def test_run_console_with_facade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            from application import Man1Lab

            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            output = StringIO()
            code = run_console(platform, input_fn=lambda _p: "exit", output=output)
            self.assertEqual(code, 0)
            self.assertIn("Man1Lab Console", output.getvalue())


class CLIConsoleEntryTest(unittest.TestCase):
    runner = CliRunner()

    @patch("runtime.console.run_console", return_value=0)
    @patch("interfaces.cli.common.get_platform")
    def test_man1lab_without_args_enters_console(
        self,
        get_platform_mock: MagicMock,
        run_console_mock: MagicMock,
    ) -> None:
        result = self.runner.invoke(app, [])
        self.assertEqual(result.exit_code, 0)
        run_console_mock.assert_called_once()
        get_platform_mock.assert_called_once()


class ConsoleBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
    )

    def test_console_package_has_no_forbidden_imports(self) -> None:
        console_dir = REPO_ROOT / "runtime" / "console"
        offenders: list[str] = []
        for path in sorted(console_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                if module is None:
                    continue
                root = module.split(".", 1)[0]
                if root in self._FORBIDDEN_ROOTS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
        self.assertEqual(offenders, [])

    def test_console_does_not_import_workflow_modules(self) -> None:
        source = "\n".join(
            (REPO_ROOT / "runtime" / "console" / name).read_text(encoding="utf-8")
            for name in sorted(p.name for p in (REPO_ROOT / "runtime" / "console").glob("*.py"))
        )
        self.assertNotIn("workflow.", source)
        self.assertNotIn("providers.", source)


if __name__ == "__main__":
    unittest.main()
