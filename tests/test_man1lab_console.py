"""Tests for Man1Lab interactive console."""

from __future__ import annotations

import ast
import sys
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
from datetime import UTC, datetime
from models.execution_strategy import (
    AnalysisReference,
    DiscoveryReference,
    ExecutionStrategy,
    InputReferences,
    PlanningStatus,
    Strategy,
    StrategyMetadata,
    StrategyPosture,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import DiscoveryStatus, ResearchResourceDiscovery
from runtime.console import (
    CommandRegistry,
    ConsoleCommand,
    ConsoleContext,
    Man1LabConsole,
    parse_command_line,
    run_console,
)
from runtime.console.builtins import register_builtin_commands
from runtime.console.input import create_console_input_fn, prompt_toolkit_available
from runtime.console.renderer import ConsoleRenderer
from runtime.session.workspace import SessionWorkspace
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


def _minimal_execution_strategy(strategy_id: str = "strategy-1") -> ExecutionStrategy:
    now = datetime.now(UTC)
    return ExecutionStrategy(
        metadata=StrategyMetadata(
            strategy_id=strategy_id,
            created_at=now,
            status=PlanningStatus.COMPLETE,
        ),
        input_references=InputReferences(
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Test Paper",
                analysis_content_hash="analysis-hash",
            ),
            discovery_reference=DiscoveryReference(
                discovery_schema_version="1.0",
                discovery_id="disc-1",
                discovery_content_hash="discovery-hash",
                discovery_status=DiscoveryStatus.COMPLETE,
            ),
        ),
        strategy=Strategy(
            primary_posture=StrategyPosture.GREENFIELD,
            rationale="Console integration test.",
        ),
    )


def _sample_analysis(title: str = "Test Paper") -> PaperReproductionAnalysis:
    from models.paper_reproduction_analysis import (
        AnalysisGoal,
        PaperMetadata,
        PaperReproductionAnalysis,
        ReproductionScope,
    )

    return PaperReproductionAnalysis(
        metadata=PaperMetadata(title=title),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Console test goal.",
        ),
    )


def _sample_discovery() -> ResearchResourceDiscovery:
    from validation.research_resource_discovery import build_research_resource_discovery

    return build_research_resource_discovery(
        {
            "metadata": {
                "discovery_id": "disc-console",
                "created_at": "2026-07-02T00:00:00+00:00",
                "status": "complete",
                "candidate_count": 0,
                "selection_count": 0,
                "unresolved_gap_count": 0,
            },
            "analysis_reference": {
                "analysis_schema_version": "1.0",
                "paper_title": "Test Paper",
                "analysis_content_hash": "hash",
            },
        }
    )


def _mock_platform() -> MagicMock:
    platform = MagicMock()
    platform.version.return_value = "1.2.4"
    workspace_root = Path(tempfile.mkdtemp()) / "workspace"
    platform.settings = MagicMock(workspace_root=workspace_root)
    platform.current_model.return_value = None
    platform.is_runtime_ready.return_value = True
    platform.is_session_active.return_value = False
    platform.runtime.state.value = "ready"
    session = MagicMock()
    session.state = SessionState.NEW
    session.is_active.return_value = False
    session.workspace = SessionWorkspace()

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
            "execute",
            "execution",
            "plan-all",
            "execute-all",
            "reproduce",
        }
        self.assertEqual(set(registry.names()), expected)


class ConsoleDispatchTest(unittest.TestCase):
    def test_help_command(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        self.assertEqual(console.dispatch("help"), 0)
        self.assertIn("Available commands", output.getvalue())
        self.assertIn("Workflow:", output.getvalue())
        self.assertIn("plan-all", output.getvalue())

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
            input_fn=lambda _prompt: "exit",
        )
        console.run()
        platform.session.return_value.open.assert_called_once()

    def test_analyze_updates_session(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = _sample_analysis()
        platform.analyze.return_value = analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")
            platform.settings = MagicMock(workspace_root=Path(temp_dir) / "workspace")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch(f"analyze {paper}")

        self.assertEqual(session.workspace.current_paper, paper.resolve())
        self.assertIs(session.workspace.current_analysis, analysis)
        platform.analyze.assert_called_once_with(paper.resolve())

    def test_discover_uses_session_analysis(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = _sample_analysis()
        discovery = _sample_discovery()
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
        analysis = _sample_analysis()
        discovery = _sample_discovery()
        strategy = _minimal_execution_strategy("strategy-1")
        session.workspace.current_analysis = analysis
        session.workspace.current_discovery = discovery
        platform.plan.return_value = strategy

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("plan")

        platform.plan.assert_called_once_with(analysis, discovery)
        self.assertIs(session.workspace.current_strategy, strategy)
        text = output.getvalue()
        self.assertIn("✓ Execution strategy generated", text)
        self.assertIn("Execution Strategy", text)
        self.assertIn("Next: execute", text)

    def test_plan_displays_metadata_strategy_id_not_top_level_attribute(self) -> None:
        """Regression: plan must read strategy.metadata.strategy_id, not strategy.strategy_id."""
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        session.workspace.current_analysis = _sample_analysis()
        session.workspace.current_discovery = _sample_discovery()
        platform.plan.return_value = _minimal_execution_strategy("strategy-regression")

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        code = console.dispatch("plan")

        self.assertEqual(code, 0)
        self.assertIn("✓ Execution strategy generated", output.getvalue())


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
            input_fn=lambda _prompt: "exit",
        )
        console.run()
        text = output.getvalue()
        self.assertIn("MAN1LAB 1.2.4", text)
        self.assertIn("Research Paper Reproduction Platform", text)
        self.assertIn("Workspace", text)
        self.assertIn("Active Model", text)
        self.assertIn("Runtime", text)
        self.assertIn("Session", text)
        self.assertIn("Quick start:", text)
        self.assertIn('Type "help" to see all commands.', text)


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
            self.assertIn("MAN1LAB", output.getvalue())
            self.assertIn("Quick start:", output.getvalue())


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


class GuidedOutputTest(unittest.TestCase):
    def test_analyze_shows_guided_success(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        analysis = _sample_analysis()
        platform.analyze.return_value = analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")
            platform.settings = MagicMock(workspace_root=Path(temp_dir) / "workspace")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch(f"analyze {paper}")

        text = output.getvalue()
        self.assertIn("✓ Paper analyzed successfully", text)
        self.assertIn("Generated:", text)
        self.assertIn("Analysis", text)
        self.assertIn("Next: discover", text)

    def test_discover_shows_guided_success(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = _sample_analysis()
        discovery = _sample_discovery()
        session.workspace.current_analysis = analysis
        platform.discover.return_value = discovery
        platform.settings = MagicMock(workspace_root=Path(tempfile.mkdtemp()) / "workspace")

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("discover")

        text = output.getvalue()
        self.assertIn("✓ Resources discovered", text)
        self.assertIn("Next: plan", text)


class ExecutionConsoleCommandTest(unittest.TestCase):
    def test_execute_delegates_to_facade(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        outcome = MagicMock(
            run_id="run-console",
            status=MagicMock(value="success"),
            resumed=False,
            run_directory="/workspace/execution/runs/run-console",
            report=MagicMock(),
        )
        platform.run_execution.return_value = outcome

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            platform.settings = MagicMock(workspace_root=root)
            from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
            from runtime.session.workspace_store import WorkspaceArtifactStore

            graph = ExecutionGraph(
                graph_id="graph-console",
                created_at=datetime.now(UTC),
                strategy_id="strategy-1",
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-1",
                        stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                        label="Prepare Environment",
                    )
                ],
            )
            WorkspaceArtifactStore(root).save_execution_graph(graph)

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            code = console.dispatch("execute")

        self.assertEqual(code, 0)
        platform.run_execution.assert_called_once_with(run_id=None, resume=True)
        self.assertEqual(session.workspace.current_execution_run_id, "run-console")
        self.assertIn("run-console", output.getvalue())

    def test_execute_missing_graph_shows_diagnostic(self) -> None:
        platform = _mock_platform()
        platform.run_execution.side_effect = ValueError(
            "Execution graph not found in workspace. Run plan before execute."
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            platform.settings = MagicMock(workspace_root=Path(temp_dir) / "workspace")
            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=StringIO()))
            with patch("runtime.console.renderer.print") as mock_print:
                console.dispatch("execute")
                messages = [
                    str(call.args[0])
                    for call in mock_print.call_args_list
                    if call.kwargs.get("file") is sys.stderr
                ]
                self.assertTrue(any("plan" in msg for msg in messages))
        platform.run_execution.assert_called_once_with(run_id=None, resume=True)

    def test_execution_status_delegates_to_facade(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        task = MagicMock(task_id="task-1", name="Prepare Environment", status=MagicMock(value="success"))
        status = MagicMock(
            run_id="run-console",
            status=MagicMock(value="success"),
            graph_id="graph-console",
            backend_kind="fake",
            run_directory="/workspace/execution/runs/run-console",
            report_path="/workspace/execution/runs/run-console/report.json",
            tasks=[task],
        )
        platform.execution_status.return_value = status

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("execution status")

        platform.execution_status.assert_called_once_with(None)
        self.assertIn("run-console", output.getvalue())
        self.assertIn("Prepare Environment", output.getvalue())

    def test_execution_report_delegates_to_facade(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        report = MagicMock(status=MagicMock(value="success"), summary="done")
        report_view = MagicMock(
            run_id="run-console",
            report=report,
            report_path="/workspace/execution/runs/run-console/report.json",
            run_directory="/workspace/execution/runs/run-console",
            completed_task_ids=("task-1",),
            failed_task_ids=(),
            artifact_ids=("artifact-1",),
        )
        platform.execution_report.return_value = report_view

        console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
        console.dispatch("execution report run-console")

        platform.execution_report.assert_called_once_with("run-console")
        self.assertIn("report.json", output.getvalue())
        self.assertIn("artifact-1", output.getvalue())


class PipelineCommandTest(unittest.TestCase):
    def test_plan_all_delegates_to_facade_stages(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        session = platform.session.return_value
        analysis = _sample_analysis()
        discovery = _sample_discovery()
        strategy = _minimal_execution_strategy()
        platform.analyze.return_value = analysis
        platform.discover.return_value = discovery
        platform.plan.return_value = strategy

        with tempfile.TemporaryDirectory() as temp_dir:
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")
            platform.settings = MagicMock(workspace_root=Path(temp_dir) / "workspace")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch(f"plan-all {paper}")

        platform.analyze.assert_called_once()
        platform.discover.assert_called_once_with(analysis)
        platform.plan.assert_called_once_with(analysis, discovery)
        self.assertIs(session.workspace.current_strategy, strategy)
        self.assertIn("✓ Execution strategy generated", output.getvalue())

    def test_execute_all_delegates_to_execute(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        outcome = MagicMock(
            run_id="run-all",
            status=MagicMock(value="success"),
            resumed=False,
            run_directory="/workspace/execution/runs/run-all",
            report=None,
        )
        platform.run_execution.return_value = outcome

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            platform.settings = MagicMock(workspace_root=root)
            from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
            from runtime.session.workspace_store import WorkspaceArtifactStore

            graph = ExecutionGraph(
                graph_id="graph-all",
                created_at=datetime.now(UTC),
                strategy_id="strategy-1",
                nodes=[
                    ExecutionGraphNode(
                        node_id="node-1",
                        stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                        label="Prepare Environment",
                    )
                ],
            )
            WorkspaceArtifactStore(root).save_execution_graph(graph)

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch("execute-all")

        platform.run_execution.assert_called_once()

    def test_reproduce_runs_plan_all_then_execute(self) -> None:
        output = StringIO()
        platform = _mock_platform()
        analysis = _sample_analysis()
        discovery = _sample_discovery()
        strategy = _minimal_execution_strategy()
        outcome = MagicMock(
            run_id="run-reproduce",
            status=MagicMock(value="success"),
            resumed=False,
            run_directory="/workspace/execution/runs/run-reproduce",
            report=None,
        )
        platform.analyze.return_value = analysis
        platform.discover.return_value = discovery
        platform.plan.return_value = strategy
        platform.run_execution.return_value = outcome

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            platform.settings = MagicMock(workspace_root=root)
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=output))
            console.dispatch(f"reproduce {paper}")

        platform.analyze.assert_called_once()
        platform.plan.assert_called_once()
        platform.run_execution.assert_called_once()


class WorkspacePersistenceConsoleTest(unittest.TestCase):
    def test_analyze_persists_workspace_artifacts(self) -> None:
        from models.paper_reproduction_analysis import (
            AnalysisGoal,
            PaperMetadata,
            PaperReproductionAnalysis,
            ReproductionScope,
        )

        platform = _mock_platform()
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Persisted"),
            goal=AnalysisGoal(
                scope=ReproductionScope.TRAINING,
                research_goal="Persist analysis artifact.",
            ),
        )
        platform.analyze.return_value = analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            platform.settings = MagicMock(workspace_root=root)
            paper = Path(temp_dir) / "paper.pdf"
            paper.write_bytes(b"%PDF-1.4 test")

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=StringIO()))
            console.dispatch(f"analyze {paper}")

            self.assertTrue((root / "analysis" / "analysis.json").exists())


class ResumeConsoleTest(unittest.TestCase):
    def test_discover_skips_analyze_when_persisted(self) -> None:
        from models.paper_reproduction_analysis import (
            AnalysisGoal,
            PaperMetadata,
            PaperReproductionAnalysis,
            ReproductionScope,
        )
        from runtime.session.workspace_store import WorkspaceArtifactStore

        platform = _mock_platform()
        discovery = _sample_discovery()
        platform.discover.return_value = discovery

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            platform.settings = MagicMock(workspace_root=root)
            analysis = PaperReproductionAnalysis(
                metadata=PaperMetadata(title="Cached"),
                goal=AnalysisGoal(
                    scope=ReproductionScope.TRAINING,
                    research_goal="Goal",
                ),
            )
            WorkspaceArtifactStore(root).save_analysis(analysis)

            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=StringIO()))
            console.dispatch("discover")

        platform.analyze.assert_not_called()
        platform.discover.assert_called_once()

    def test_plan_diagnostic_when_analysis_missing(self) -> None:
        platform = _mock_platform()
        with tempfile.TemporaryDirectory() as temp_dir:
            platform.settings = MagicMock(workspace_root=Path(temp_dir) / "workspace")
            console = Man1LabConsole(platform, renderer=ConsoleRenderer(output=StringIO()))
            with patch("runtime.console.renderer.print") as mock_print:
                console.dispatch("plan")
                messages = [
                    str(call.args[0])
                    for call in mock_print.call_args_list
                    if call.kwargs.get("file") is sys.stderr
                ]
                self.assertTrue(any("analyze <paper.pdf>" in msg for msg in messages))


class ConsoleInputTest(unittest.TestCase):
    def test_create_console_input_fn_returns_callable(self) -> None:
        input_fn = create_console_input_fn(["help", "exit"])
        self.assertTrue(callable(input_fn))

    def test_prompt_toolkit_availability_is_boolean(self) -> None:
        self.assertIsInstance(prompt_toolkit_available(), bool)


class ConsoleBoundaryTest(unittest.TestCase):
    _FORBIDDEN_ROOTS = (
        "workflow",
        "execution_planning",
        "discovery",
        "agents",
        "providers",
        "execution",
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
        self.assertNotIn("execution.", source)
        self.assertNotIn("LocalExecutor", source)


if __name__ == "__main__":
    unittest.main()
