"""Tests for the Man1Lab platform facade."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from adapters.pymupdf_parser import PyMuPDFParser
from agents.planner import Planner
from agents.reader import Reader
from application import PLATFORM_VERSION, Man1Lab
from application.facade import ExecuteResult
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
from discovery.empty import build_empty_discovery
from discovery.workflow import DiscoveryWorkflow
from execution_planning.workflow import ExecutionPlanningWorkflow
from models.execution import ExecutionResult
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.report import ReportModel
from models.research_resource_discovery import ResearchResourceDiscovery
from models.task import TaskModel
from models.workspace import Workspace
from providers.noop.collection import NoOpCollectionProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from tests.fixtures import create_sample_paper_pdf, sample_reproduction_analysis
from tests.runner_mocks import mock_command_runner
from tests.test_execution_strategy_builder import _input_references, _minimal_risk_result
from execution_planning.builder import ExecutionStrategyBuilder
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from agents.coder import Coder
from agents.runner import Runner
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


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


def _noop_discovery_workflow() -> DiscoveryWorkflow:
    return DiscoveryWorkflow(
        collection_service=CollectionService(providers=[NoOpCollectionProvider()]),
        evidence_service=EvidenceService(providers=[NoOpEvidenceProvider()]),
        verification_service=VerificationService(providers=[NoOpVerificationProvider()]),
        ranking_service=RankingService(providers=[NoOpRankingProvider()]),
    )


class Man1LabConstructionTest(unittest.TestCase):
    def test_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            platform = Man1Lab(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
            )
            self.assertEqual(platform.version(), PLATFORM_VERSION)
            self.assertEqual(PLATFORM_VERSION, "1.2.3")

    def test_configuration_returns_effective_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            configuration = platform.configuration()
            self.assertEqual(configuration["parser"]["backend"], "pymupdf")
            self.assertTrue(configuration["discovery"]["enabled"])
            self.assertTrue(configuration["execution_planning"]["enabled"])

    def test_doctor_reports_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            platform = Man1Lab(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
            )
            report = platform.doctor()
            self.assertTrue(report.healthy)
            self.assertGreater(len(report.checks), 0)
            check_names = {check.name for check in report.checks}
            self.assertIn("workspace", check_names)
            self.assertIn("Configuration", check_names)
            self.assertIn("Python", check_names)


class Man1LabDelegationTest(unittest.TestCase):
    def test_reproduce_delegates_to_orchestrator(self) -> None:
        orchestrator = MagicMock()
        expected = ReportModel(
            reproduction_summary="ok",
            implementation_summary="ok",
            final_status="SUCCESS",
        )
        orchestrator.run.return_value = expected

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            settings = _test_settings(temp_path)
            settings = AppSettings(
                workspace_root=settings.workspace_root,
                outputs_dir=settings.outputs_dir,
                logs_dir=settings.logs_dir,
                prompts_dir=settings.prompts_dir,
                paper_path=paper_path,
                parser=settings.parser,
                discovery=settings.discovery,
                execution_planning=settings.execution_planning,
                workflow=settings.workflow,
                llm=settings.llm,
                logging=settings.logging,
                tracking=settings.tracking,
            )
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
                orchestrator=orchestrator,
            )
            report = platform.reproduce()
            orchestrator.run.assert_called_once_with(paper_path)
            self.assertEqual(report, expected)

    def test_analyze_delegates_to_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            platform = Man1Lab(
                settings=_test_settings(temp_path),
                initialize_configuration=False,
                configure_logging=False,
            )
            platform._reader = Reader(document_parser=PyMuPDFParser(), prompt_builder=default_prompt_builder(), llm=MockLLMProvider())
            analysis = platform.analyze(paper_path)
            self.assertIsInstance(analysis, PaperReproductionAnalysis)
            self.assertIn("Diffusion Policy", analysis.metadata.title)

    def test_discover_delegates_to_discovery_workflow(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        platform = Man1Lab(
            settings=_test_settings(Path(tempfile.gettempdir())),
            initialize_configuration=False,
            configure_logging=False,
        )
        platform._discovery_workflow = _noop_discovery_workflow()
        discovery = platform.discover(analysis)
        self.assertIsInstance(discovery, ResearchResourceDiscovery)

    def test_discover_disabled_returns_empty_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            settings = AppSettings(
                workspace_root=settings.workspace_root,
                outputs_dir=settings.outputs_dir,
                logs_dir=settings.logs_dir,
                prompts_dir=settings.prompts_dir,
                paper_path=settings.paper_path,
                parser=settings.parser,
                discovery=DiscoveryConfig(enabled=False),
                execution_planning=settings.execution_planning,
                workflow=settings.workflow,
                llm=settings.llm,
                logging=settings.logging,
                tracking=settings.tracking,
            )
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
            )
            discovery = platform.discover(sample_reproduction_analysis(source_path=Path("paper.pdf")))
            self.assertEqual(discovery.candidate_resources.candidates, [])

    def test_plan_delegates_to_execution_planning_workflow(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        platform = Man1Lab(
            settings=_test_settings(Path(tempfile.gettempdir())),
            initialize_configuration=False,
            configure_logging=False,
        )
        strategy = platform.plan(analysis, discovery)
        self.assertIsInstance(strategy, ExecutionStrategy)

    def test_execute_runs_planner_coder_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace",
                outputs_dir=temp_path / "outputs",
            )
            platform = Man1Lab(
                settings=_test_settings(temp_path),
                initialize_configuration=False,
                configure_logging=False,
            )
            platform._workspace_manager = workspace_manager
            platform._planner = Planner(
                prompt_builder=default_prompt_builder(),
                llm=MockLLMProvider(MOCK_PLANNER_JSON),
            )
            platform._coder = Coder(workspace_manager=workspace_manager, prompt_builder=default_prompt_builder())
            platform._runner = Runner(
                environment_service=EnvironmentService(command_runner=mock_command_runner),
                execution_service=ExecutionService(command_runner=mock_command_runner),
            )
            analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
            strategy = ExecutionStrategyBuilder.build(
                _minimal_risk_result(),
                strategy_id="strategy-facade",
                input_references=_input_references(),
                summary="Facade execute test.",
            )
            result = platform.execute(strategy, analysis)
            self.assertIsInstance(result, ExecuteResult)
            self.assertIsInstance(result.task, TaskModel)
            self.assertIsInstance(result.workspace, Workspace)
            self.assertIsInstance(result.execution_result, ExecutionResult)


class Man1LabBackwardCompatibilityTest(unittest.TestCase):
    def test_app_main_uses_facade(self) -> None:
        with patch("app.Man1Lab") as facade_cls:
            facade = facade_cls.return_value
            facade.reproduce.return_value = ReportModel(
                reproduction_summary="ok",
                implementation_summary="ok",
                final_status="SUCCESS",
                report_path=Path("outputs/report.md"),
            )
            from app import main

            main()
            facade_cls.assert_called_once()
            facade.reproduce.assert_called_once()

    def test_facade_does_not_import_workflow_from_app(self) -> None:
        import ast
        from pathlib import Path as PathLib

        source = PathLib("app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        self.assertIn("application", imports)
        self.assertNotIn("workflow.orchestrator", imports)
        self.assertNotIn("tracking.workflow", imports)


class Man1LabBoundaryTest(unittest.TestCase):
    def test_workflow_does_not_import_facade(self) -> None:
        import ast
        from pathlib import Path as PathLib

        repo_root = PathLib(__file__).resolve().parents[1]
        offenders: list[str] = []
        for path in (repo_root / "workflow").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "application" in node.module:
                    offenders.append(f"{path}: from {node.module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
