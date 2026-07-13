"""Unit tests for PlatformExecutionService resume selection."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from application.platform_execution import PlatformExecutionService
from execution.engine import EngineRunResult
from execution.ports.persistence import ResumableRunSummary
from models.execution_engine import ExecutionRun, ExecutionRunStatus
from models.execution_materialization import (
    MaterializationReport,
    MaterializationStatus,
    NodeMaterializationResult,
)
from runtime.context import RuntimeContext
from runtime.execution_store import ExecutionStoreFactory
from tests.execution_engine_fixtures import linear_graph, materialized_linear_graph


def _ready_report(graph) -> MaterializationReport:
    return MaterializationReport(
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


class PlatformExecutionServiceResumeTest(unittest.TestCase):
    def test_run_execution_resumes_matching_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = RuntimeContext.create()
            factory = ExecutionStoreFactory(root)
            context.bind_execution_store(factory)
            service = PlatformExecutionService(context, root)
            graph = materialized_linear_graph()

            existing_run = ExecutionRun(
                run_id="run-resume",
                graph_id=graph.graph_id,
                strategy_id=graph.strategy_id,
                workspace_ref=root.as_posix(),
                backend_kind="fake",
                policy_snapshot={},
                status=ExecutionRunStatus.INTERRUPTED,
                task_ids=(),
                trace_id="trace-1",
                created_at=datetime.now(UTC),
            )
            engine_result = EngineRunResult(
                run=existing_run,
                tasks=(),
                task_results=(),
                report=None,
                decomposition=MagicMock(),
                scheduler=MagicMock(),
                task_fingerprint="fp",
                graph_fingerprint="gfp",
            )
            engine = MagicMock()
            engine.persistence = factory.store()
            engine.load_and_resume_run.return_value = engine_result
            resumable = ResumableRunSummary(
                run_id="run-resume",
                graph_id=graph.graph_id,
                status=ExecutionRunStatus.INTERRUPTED,
                revision=1,
                updated_at=datetime.now(UTC),
            )

            with (
                patch.object(service, "_engine_factory", return_value=engine),
                patch.object(service, "_find_resumable_run", return_value=resumable),
            ):
                outcome = service.run_execution(
                    graph,
                    materialization_report=_ready_report(graph),
                    resume=True,
                )

            engine.load_and_resume_run.assert_called_once_with(graph, "run-resume")
            engine.start_run.assert_not_called()
            self.assertTrue(outcome.resumed)
            self.assertEqual(outcome.run_id, "run-resume")

    def test_explicit_run_id_does_not_resume_another_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = RuntimeContext.create()
            factory = ExecutionStoreFactory(root)
            context.bind_execution_store(factory)
            service = PlatformExecutionService(context, root)
            graph = materialized_linear_graph()
            engine = MagicMock()
            engine.persistence = factory.store()
            started_run = ExecutionRun(
                run_id="run-requested",
                graph_id=graph.graph_id,
                strategy_id=graph.strategy_id,
                status=ExecutionRunStatus.SUCCESS,
                task_ids=(),
                trace_id="trace-requested",
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            engine.start_run.return_value = EngineRunResult(
                run=started_run,
                tasks=(),
                task_results=(),
                report=None,
                decomposition=MagicMock(),
                scheduler=MagicMock(),
                task_fingerprint="fp",
                graph_fingerprint="gfp",
            )
            other = ResumableRunSummary(
                run_id="run-other",
                graph_id=graph.graph_id,
                status=ExecutionRunStatus.INTERRUPTED,
                revision=1,
                updated_at=datetime.now(UTC),
            )
            with (
                patch.object(service, "_engine_factory", return_value=engine),
                patch.object(factory.store(), "list_resumable_runs", return_value=(other,)),
            ):
                outcome = service.run_execution(
                    graph,
                    materialization_report=_ready_report(graph),
                    run_id="run-requested",
                    resume=True,
                )
            engine.load_and_resume_run.assert_not_called()
            engine.start_run.assert_called_once()
            self.assertEqual(outcome.run_id, "run-requested")


if __name__ == "__main__":
    unittest.main()
