"""Tests for platform execution facade delegation."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from application import Man1Lab
from application.platform_execution import (
    ExecutionReportView,
    ExecutionRunOutcome,
    ExecutionStatusView,
    PlatformExecutionService,
)
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
from models.execution_engine import ExecutionRunStatus
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from runtime.session.workspace_store import WorkspaceArtifactStore


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


def _sample_graph() -> ExecutionGraph:
    return ExecutionGraph(
        graph_id="graph-facade",
        created_at=datetime.now(UTC),
        strategy_id="strategy-facade",
        nodes=[
            ExecutionGraphNode(
                node_id="node-prepare-environment",
                stage_type=ExecutionGraphStageType.PREPARE_ENVIRONMENT,
                label="Prepare Environment",
            )
        ],
    )


class PlatformExecutionFacadeTest(unittest.TestCase):
    def test_run_execution_delegates_to_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            service = MagicMock(spec=PlatformExecutionService)
            outcome = ExecutionRunOutcome(
                run_id="run-1",
                status=ExecutionRunStatus.SUCCESS,
                resumed=False,
                run_directory=str(settings.workspace_root / "execution" / "runs" / "run-1"),
                report=None,
            )
            service.run_execution.return_value = outcome
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
                platform_execution=service,
            )
            WorkspaceArtifactStore(settings.workspace_root).save_execution_graph(_sample_graph())

            result = platform.run_execution()

            service.run_execution.assert_called_once()
            self.assertEqual(result.run_id, "run-1")
            self.assertEqual(platform.session().workspace.current_execution_run_id, "run-1")

    def test_run_execution_requires_execution_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            platform = Man1Lab(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
            )
            with self.assertRaisesRegex(ValueError, "Execution graph not found"):
                platform.run_execution()

    def test_execution_status_delegates_to_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MagicMock(spec=PlatformExecutionService)
            status = ExecutionStatusView(
                run_id="run-1",
                status=ExecutionRunStatus.SUCCESS,
                graph_id="graph-facade",
                strategy_id="strategy-facade",
                backend_kind="fake",
                tasks=(),
                run_directory="/tmp/run-1",
                report_path="/tmp/run-1/report.json",
                resumable=False,
            )
            service.execution_status.return_value = status
            platform = Man1Lab(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
                platform_execution=service,
            )
            platform.session().workspace.current_execution_run_id = "run-1"

            result = platform.execution_status()

            service.execution_status.assert_called_once_with("run-1")
            self.assertEqual(result.run_id, "run-1")

    def test_execution_report_delegates_to_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MagicMock(spec=PlatformExecutionService)
            report = MagicMock()
            report.status = ExecutionRunStatus.SUCCESS
            report.summary = "ok"
            view = ExecutionReportView(
                run_id="run-1",
                report=report,
                run_directory="/tmp/run-1",
                report_path="/tmp/run-1/report.json",
                completed_task_ids=("task-1",),
                failed_task_ids=(),
                artifact_ids=("artifact-1",),
            )
            service.execution_report.return_value = view
            platform = Man1Lab(
                settings=_test_settings(Path(temp_dir)),
                initialize_configuration=False,
                configure_logging=False,
                platform_execution=service,
            )
            platform.session().workspace.current_execution_run_id = "run-1"

            result = platform.execution_report("run-1")

            service.execution_report.assert_called_once_with("run-1")
            self.assertEqual(result.completed_task_ids, ("task-1",))


if __name__ == "__main__":
    unittest.main()
