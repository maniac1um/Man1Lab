"""Platform integration — Analysis → Discovery → ExecutionPlanning → Planner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from adapters.pymupdf_parser import PyMuPDFParser
from configuration.bootstrap import initialize_app_configuration
from configuration.hydra_provider import HydraSettingsProvider
from discovery.empty import build_empty_discovery
from discovery.workflow import DiscoveryWorkflow
from execution_planning.workflow import ExecutionPlanningWorkflow
from hydra import compose, initialize_config_dir
from models.execution_strategy import ExecutionStrategy, StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from models.task import TaskModel
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from tests.fixtures import create_sample_paper_pdf, sample_reproduction_analysis
from tests.runner_mocks import mock_command_runner
from tests.test_execution_strategy_builder import _minimal_risk_result, _input_references
from execution_planning.builder import ExecutionStrategyBuilder
from tracking.workflow import TrackedWorkflowOrchestrator
from tests.test_experiment_tracking import RecordingExperimentTracker
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


def _noop_discovery_workflow() -> DiscoveryWorkflow:
    return DiscoveryWorkflow(
        collection_service=CollectionService(providers=[NoOpCollectionProvider()]),
        evidence_service=EvidenceService(providers=[NoOpEvidenceProvider()]),
        verification_service=VerificationService(providers=[NoOpVerificationProvider()]),
        ranking_service=RankingService(providers=[NoOpRankingProvider()]),
    )


def _embedded_discovery_workflow() -> DiscoveryWorkflow:
    return DiscoveryWorkflow(
        collection_service=CollectionService(
            providers=[EmbeddedResourceProvider(), NoOpCollectionProvider()]
        ),
        evidence_service=EvidenceService(
            providers=[EmbeddedEvidenceProvider(), NoOpEvidenceProvider()]
        ),
        verification_service=VerificationService(
            providers=[EmbeddedVerificationProvider(), NoOpVerificationProvider()]
        ),
        ranking_service=RankingService(
            providers=[EmbeddedRankingProvider(), NoOpRankingProvider()]
        ),
    )


def _sample_strategy() -> ExecutionStrategy:
    return ExecutionStrategyBuilder.build(
        _minimal_risk_result(),
        strategy_id="strategy-test",
        input_references=_input_references(),
        summary="Test strategy for planner integration.",
    )


class ExecutionPlanningWorkflowTest(unittest.TestCase):
    def test_produces_execution_strategy_from_empty_discovery(self) -> None:
        analysis = sample_reproduction_analysis(source_path=Path("paper.pdf"))
        discovery = build_empty_discovery(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertIsInstance(strategy, ExecutionStrategy)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.GREENFIELD)

    def test_produces_official_repository_strategy_from_embedded_discovery(self) -> None:
        from tests.test_discovery_collection import _analysis_with_embedded_resources

        analysis = _analysis_with_embedded_resources()
        discovery = _embedded_discovery_workflow().run(analysis)
        strategy = ExecutionPlanningWorkflow.default().run(analysis, discovery)
        self.assertGreater(len(discovery.candidate_resources.candidates), 0)
        self.assertGreater(discovery.metadata.selection_count, 0)
        self.assertEqual(strategy.strategy.primary_posture, StrategyPosture.OFFICIAL_REPOSITORY)


class PlannerStrategyConsumptionTest(unittest.TestCase):
    def test_planner_accepts_execution_strategy(self) -> None:
        from tests.test_planner import FakeLLMProvider, FakePromptBuilder

        llm = FakeLLMProvider()
        planner = Planner(prompt_builder=FakePromptBuilder(), llm=llm)
        task = planner.run(_sample_strategy())
        self.assertIsInstance(task, TaskModel)
        self.assertIn("execution strategy", llm.messages[1].content.lower())
        self.assertIn("Strategy:", llm.messages[1].content)
        self.assertNotIn("infer strategy", llm.messages[1].content)


class PlatformPipelineIntegrationTest(unittest.TestCase):
    def _orchestrator(
        self,
        temp_path: Path,
        *,
        discovery_enabled: bool = True,
        execution_planning_enabled: bool = True,
        discovery_workflow: DiscoveryWorkflow | None = None,
    ) -> tuple[WorkflowOrchestrator, dict[str, object]]:
        paper_path = temp_path / "paper.pdf"
        create_sample_paper_pdf(paper_path)
        workspace_manager = WorkspaceManager(
            root=temp_path / "workspace/tasks",
            outputs_dir=temp_path / "outputs",
        )
        captured: dict[str, object] = {}

        class CapturingReporter(Reporter):
            def run(self, history):
                captured["history"] = history
                return super().run(history)

        orchestrator = WorkflowOrchestrator(
            reader=Reader(document_parser=PyMuPDFParser(), prompt_builder=default_prompt_builder()),
            planner=Planner(prompt_builder=default_prompt_builder()),
            coder=Coder(workspace_manager=workspace_manager, prompt_builder=default_prompt_builder()),
            runner=Runner(
                environment_service=EnvironmentService(command_runner=mock_command_runner),
                execution_service=ExecutionService(command_runner=mock_command_runner),
            ),
            reviewer=Reviewer(prompt_builder=default_prompt_builder()),
            reporter=CapturingReporter(),
            workspace_manager=workspace_manager,
            discovery_workflow=discovery_workflow or _embedded_discovery_workflow(),
            execution_planning_workflow=ExecutionPlanningWorkflow.default(),
            discovery_enabled=discovery_enabled,
            execution_planning_enabled=execution_planning_enabled,
        )
        return orchestrator, captured

    def test_end_to_end_with_discovery_and_execution_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator, captured = self._orchestrator(Path(temp_dir))
            report = orchestrator.run(Path(temp_dir) / "paper.pdf")
            history = captured["history"]
            self.assertIsInstance(history.analysis, PaperReproductionAnalysis)
            self.assertIsInstance(history.discovery, ResearchResourceDiscovery)
            self.assertIsInstance(history.execution_strategy, ExecutionStrategy)
            self.assertIsInstance(history.task, TaskModel)
            self.assertGreater(len(history.task.steps), 0)
            self.assertIsNotNone(report.report_path)

    def test_noop_discovery_still_runs_execution_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator, captured = self._orchestrator(
                Path(temp_dir),
                discovery_workflow=_noop_discovery_workflow(),
            )
            orchestrator.run(Path(temp_dir) / "paper.pdf")
            history = captured["history"]
            self.assertEqual(history.discovery.candidate_resources.candidates, [])
            self.assertIsNotNone(history.execution_strategy)
            self.assertEqual(
                history.execution_strategy.strategy.primary_posture,
                StrategyPosture.GREENFIELD,
            )

    def test_disabled_discovery_uses_empty_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator, captured = self._orchestrator(
                Path(temp_dir),
                discovery_enabled=False,
            )
            orchestrator.run(Path(temp_dir) / "paper.pdf")
            history = captured["history"]
            self.assertEqual(history.discovery.metadata.candidate_count, 0)
            self.assertIsNotNone(history.execution_strategy)

    def test_disabled_execution_planning_uses_legacy_planner_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator, captured = self._orchestrator(
                Path(temp_dir),
                execution_planning_enabled=False,
            )
            orchestrator.run(Path(temp_dir) / "paper.pdf")
            history = captured["history"]
            self.assertIsNone(history.execution_strategy)
            self.assertIsInstance(history.task, TaskModel)


class HydraPlatformConfigTest(unittest.TestCase):
    def test_discovery_and_execution_planning_enabled_by_default(self) -> None:
        conf_dir = Path(__file__).resolve().parents[1] / "conf"
        with initialize_config_dir(config_dir=str(conf_dir), version_base=None):
            cfg = compose(config_name="config")
        settings = HydraSettingsProvider(cfg).get_settings()
        self.assertTrue(settings.discovery.enabled)
        self.assertTrue(settings.execution_planning.enabled)


class PlatformTrackingIntegrationTest(unittest.TestCase):
    def test_tracked_orchestrator_logs_discovery_and_strategy(self) -> None:
        tracker = RecordingExperimentTracker()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)
            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            orchestrator = TrackedWorkflowOrchestrator(
                reader=Reader(document_parser=PyMuPDFParser(), prompt_builder=default_prompt_builder()),
                planner=Planner(prompt_builder=default_prompt_builder()),
                coder=Coder(workspace_manager=workspace_manager, prompt_builder=default_prompt_builder()),
                runner=Runner(
                    environment_service=EnvironmentService(command_runner=mock_command_runner),
                    execution_service=ExecutionService(command_runner=mock_command_runner),
                ),
                reviewer=Reviewer(prompt_builder=default_prompt_builder()),
                reporter=Reporter(),
                workspace_manager=workspace_manager,
                discovery_workflow=_embedded_discovery_workflow(),
                execution_planning_workflow=ExecutionPlanningWorkflow.default(),
                experiment_tracker=tracker,
            )
            orchestrator.run(paper_path)

        self.assertIn("Discovery", tracker.nested_runs)
        self.assertIn("ExecutionPlanning", tracker.nested_runs)
        self.assertIn("Planner", tracker.nested_runs)
        self.assertIn("strategy_posture", tracker.tags)
        self.assertIn("discovery_status", tracker.tags)
        self.assertTrue(any(name.endswith("discovery.json") for name in tracker.artifacts))
        self.assertTrue(
            any(name.endswith("execution_strategy.json") for name in tracker.artifacts)
        )


if __name__ == "__main__":
    unittest.main()
