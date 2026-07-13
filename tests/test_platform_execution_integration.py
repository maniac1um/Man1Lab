"""Integration tests for planned graph execution through the platform."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from application import Man1Lab
from application.platform_execution import PlatformExecutionService
from application.runtime.execution_wiring import (
    bind_workspace_execution_store,
    create_durable_engine,
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
from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor
from execution.input_resolver.in_memory import InMemoryInputResolver
from models.execution_engine import ExecutionRunStatus
from runtime.runtime import PlatformRuntime
from models.execution_materialization import (
    ExecutionMaterialization,
    MaterializationReport,
    MaterializationStatus,
    NodeMaterializationResult,
)
from runtime.session.materialization_artifacts import MaterializationArtifactStore
from tests.execution_engine_fixtures import materialized_linear_graph


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


def _fake_engine_factory(runtime: PlatformRuntime, workspace_root: Path):
    def factory():
        store = bind_workspace_execution_store(runtime.context, workspace_root)
        tracker = InMemoryArtifactTracker(workspace_root=workspace_root.as_posix())
        return create_durable_engine(
            executor=FakeExecutor(),
            persistence=store,
            artifact_tracker=tracker,
            input_resolver=InMemoryInputResolver(tracker),
        )

    return factory


class PlatformExecutionIntegrationTest(unittest.TestCase):
    def test_full_flow_persists_workspace_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            runtime = PlatformRuntime()
            runtime.startup()
            service = PlatformExecutionService(
                runtime.context,
                settings.workspace_root,
                engine_factory=_fake_engine_factory(runtime, settings.workspace_root),
            )
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
                runtime=runtime,
                platform_execution=service,
            )
            graph = materialized_linear_graph()
            report = MaterializationReport(
                status=MaterializationStatus.READY,
                node_results=tuple(
                    NodeMaterializationResult(
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                        status=MaterializationStatus.READY,
                    )
                    for node in graph.nodes
                ),
            )
            MaterializationArtifactStore(settings.workspace_root).save(
                ExecutionMaterialization(
                    materialization_id=graph.materialization_id or "mat-test",
                    strategy_id=graph.strategy_id,
                    graph_id=graph.graph_id,
                    materialized_graph=graph,
                    report=report,
                    created_at=datetime.now(UTC),
                )
            )

            outcome = platform.run_execution()

            run_dir = Path(outcome.run_directory)
            self.assertTrue(run_dir.is_dir())
            self.assertTrue((run_dir / "run.json").is_file())
            self.assertTrue((run_dir / "tasks.json").is_file())
            self.assertTrue((run_dir / "trace.jsonl").is_file())
            self.assertTrue((run_dir / "artifacts.json").is_file())
            self.assertTrue((run_dir / "report.json").is_file())
            self.assertEqual(outcome.status, ExecutionRunStatus.SUCCESS)

            status = platform.execution_status(outcome.run_id)
            self.assertEqual(status.run_id, outcome.run_id)
            self.assertEqual(len(status.tasks), 3)

            report_view = platform.execution_report(outcome.run_id)
            self.assertEqual(report_view.run_id, outcome.run_id)
            self.assertEqual(len(report_view.completed_task_ids), 3)
            self.assertEqual(report_view.report.status, ExecutionRunStatus.SUCCESS)

    def test_second_successful_execution_starts_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _test_settings(Path(temp_dir))
            runtime = PlatformRuntime()
            runtime.startup()
            service = PlatformExecutionService(
                runtime.context,
                settings.workspace_root,
                engine_factory=_fake_engine_factory(runtime, settings.workspace_root),
            )
            platform = Man1Lab(
                settings=settings,
                initialize_configuration=False,
                configure_logging=False,
                runtime=runtime,
                platform_execution=service,
            )
            graph = materialized_linear_graph()
            report = MaterializationReport(
                status=MaterializationStatus.READY,
                node_results=tuple(
                    NodeMaterializationResult(
                        node_id=node.node_id,
                        stage_type=node.stage_type.value,
                        status=MaterializationStatus.READY,
                    )
                    for node in graph.nodes
                ),
            )
            MaterializationArtifactStore(settings.workspace_root).save(
                ExecutionMaterialization(
                    materialization_id=graph.materialization_id or "mat-test",
                    strategy_id=graph.strategy_id,
                    graph_id=graph.graph_id,
                    materialized_graph=graph,
                    report=report,
                    created_at=datetime.now(UTC),
                )
            )

            first = platform.run_execution()
            second = platform.run_execution()

            self.assertFalse(first.resumed)
            self.assertFalse(second.resumed)
            self.assertNotEqual(first.run_id, second.run_id)


if __name__ == "__main__":
    unittest.main()
