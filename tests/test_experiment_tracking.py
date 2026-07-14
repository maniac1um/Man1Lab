"""Tests for experiment tracking infrastructure."""

from __future__ import annotations

import ast
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from adapters.pymupdf_parser import PyMuPDFParser
from configuration.models import TrackingConfig
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import mock_command_runner
from tracking.bootstrap import build_experiment_tracker
from tracking.mlflow_tracker import MLflowExperimentTracker
from tracking.noop_tracker import NoOpExperimentTracker
from tracking.protocol import ExperimentTracker
from tracking.workflow import TrackedWorkflowOrchestrator
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


class RecordingExperimentTracker:
    """In-memory tracker for workflow instrumentation tests."""

    def __init__(self) -> None:
        self.runs: list[str] = []
        self.nested_runs: list[str] = []
        self.params: dict[str, str | int | float | bool] = {}
        self.metrics: dict[str, float] = {}
        self.tags: dict[str, str] = {}
        self.artifacts: list[str] = []

    @contextmanager
    def start_run(
        self,
        *,
        run_name: str,
        experiment_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Iterator[RecordingExperimentTracker]:
        del experiment_name
        self.runs.append(run_name)
        if tags:
            self.tags.update(tags)
        yield self

    @contextmanager
    def start_nested_run(
        self,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Iterator[RecordingExperimentTracker]:
        self.nested_runs.append(name)
        if tags:
            self.tags.update(tags)
        yield self

    def log_param(self, key: str, value: str | int | float | bool) -> None:
        self.params[key] = value

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        del step
        self.metrics[key] = value

    def log_artifact(self, local_path: str | Path) -> None:
        self.artifacts.append(str(local_path))

    def set_tag(self, key: str, value: str) -> None:
        self.tags[key] = value


class ExperimentTrackerBootstrapTest(unittest.TestCase):
    def test_build_noop_when_disabled(self) -> None:
        tracker = build_experiment_tracker(
            TrackingConfig(enabled=False, backend="mlflow")
        )
        self.assertIsInstance(tracker, NoOpExperimentTracker)

    def test_build_noop_backend(self) -> None:
        tracker = build_experiment_tracker(TrackingConfig(backend="noop"))
        self.assertIsInstance(tracker, NoOpExperimentTracker)

    def test_build_mlflow_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            "os.environ", {"MLFLOW_ALLOW_FILE_STORE": "true"}
        ):
            tracking_root = Path(temp_dir) / "mlruns"
            tracker = build_experiment_tracker(
                TrackingConfig(
                    enabled=True,
                    backend="mlflow",
                    tracking_uri=tracking_root.as_uri(),
                )
            )
        self.assertIsInstance(tracker, MLflowExperimentTracker)


class MLflowExperimentTrackerTest(unittest.TestCase):
    def test_records_run_params_metrics_artifacts_and_nested_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            "os.environ", {"MLFLOW_ALLOW_FILE_STORE": "true"}
        ):
            tracking_root = Path(temp_dir) / "mlruns"
            tracking_uri = tracking_root.as_uri()
            tracker = MLflowExperimentTracker(
                tracking_uri=tracking_uri,
                experiment_name="test-experiment",
            )

            artifact = Path(temp_dir) / "report.md"
            artifact.write_text("# report\n", encoding="utf-8")

            with tracker.start_run(run_name="paper-run", tags={"component": "test"}):
                tracker.log_param("paper_path", "paper.pdf")
                tracker.log_metric("stage_count", 3.0)
                tracker.set_tag("final_status", "SUCCESS")
                with tracker.start_nested_run("Reader"):
                    tracker.log_metric("duration_seconds", 1.5)
                    tracker.set_tag("status", "SUCCESS")
                tracker.log_artifact(artifact)

            self.assertTrue(tracking_root.exists())


class TrackedWorkflowOrchestratorTest(unittest.TestCase):
    def test_one_parent_run_and_nested_stage_runs(self) -> None:
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
                    environment_service=EnvironmentService(
                        command_runner=mock_command_runner
                    ),
                    execution_service=ExecutionService(
                        command_runner=mock_command_runner
                    ),
                ),
                reviewer=Reviewer(prompt_builder=default_prompt_builder()),
                reporter=Reporter(),
                workspace_manager=workspace_manager,
                experiment_tracker=tracker,
            )

            report = orchestrator.run(paper_path)

        self.assertEqual(tracker.runs, ["paper"])
        self.assertIn("Reader", tracker.nested_runs)
        self.assertIn("Planner", tracker.nested_runs)
        self.assertIn("Coder", tracker.nested_runs)
        self.assertIn("Runner", tracker.nested_runs)
        self.assertIn("Reviewer", tracker.nested_runs)
        self.assertIn("Reporter", tracker.nested_runs)
        self.assertEqual(tracker.params["paper_path"], str(paper_path))
        self.assertEqual(tracker.tags["final_status"], report.final_status)
        self.assertGreater(tracker.metrics["stage_count"], 0.0)
        self.assertTrue(tracker.artifacts)


class BusinessModuleImportAuditTest(unittest.TestCase):
    _BUSINESS_ROOTS = ("agents", "workflow", "services", "models", "validation")

    def test_business_modules_do_not_import_mlflow(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        for root_name in self._BUSINESS_ROOTS:
            for path in (repo_root / root_name).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "mlflow" or alias.name.startswith("mlflow."):
                                offenders.append(f"{path}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if node.module == "mlflow" or node.module.startswith("mlflow."):
                            offenders.append(f"{path}: from {node.module}")
        self.assertEqual(offenders, [])


class ProtocolConformanceTest(unittest.TestCase):
    def test_noop_and_recording_implement_protocol(self) -> None:
        self.assertIsInstance(NoOpExperimentTracker(), ExperimentTracker)
        self.assertIsInstance(RecordingExperimentTracker(), ExperimentTracker)


if __name__ == "__main__":
    unittest.main()
