"""Regression coverage for the second Execution Engine architecture audit."""

from __future__ import annotations

import ast
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor
from execution.decomposition import decompose_execution_graph
from execution.ports.executor import ArtifactCandidate
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from execution.resume import compute_graph_fingerprint, compute_task_fingerprint
from execution.testing import make_test_engine
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    Attempt,
    ExecutionArtifactReference,
    ExecutionError,
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionTaskType,
    LogReference,
    Metric,
    OutputDeclaration,
    ReconciliationState,
    TaskExecutionResult,
    TaskResultSummary,
    TraceEvent,
    TraceEventType,
)
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from tests.execution_engine_fixtures import linear_graph


ROOT = Path(__file__).resolve().parents[1]


def _run_and_trace(graph: ExecutionGraph, run_id: str = "run-resume"):
    now = datetime.now(UTC)
    run = ExecutionRun(
        run_id=run_id,
        graph_id=graph.graph_id,
        strategy_id=graph.strategy_id,
        created_at=now,
    )
    trace = ExecutionTraceBuilder(
        trace_id="trace-resume",
        run_id=run_id,
        graph_id=graph.graph_id,
        strategy_id=graph.strategy_id,
        created_at=now,
    )
    return run, trace


class TerminalResumePolicyTest(unittest.TestCase):
    def test_failed_task_is_not_automatically_retried(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-resume")
        task_id = decomposition.tasks[0].id
        prior = TaskExecutionResult(
            result_id="prior-failure",
            run_id="run-resume",
            task_id=task_id,
            status=ExecutionTaskStatus.FAILED,
            attempts=(Attempt(attempt_id="old-attempt", task_id=task_id),),
            task_result=TaskResultSummary(termination_reason="failed"),
            errors=(ExecutionError(code="old_failure", message="old failure"),),
        )
        executor = FakeExecutor()
        engine = make_test_engine(executor=executor)
        run, trace = _run_and_trace(graph)
        with mock.patch.object(executor, "execute_attempt", wraps=executor.execute_attempt) as call:
            result = engine.resume_run(
                graph,
                run,
                prior_results={task_id: prior},
                stored_task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
                trace_builder=trace,
            )
            call.assert_not_called()
        self.assertEqual(result.run.status, ExecutionRunStatus.FAILED)
        self.assertEqual(result.tasks[0].status, ExecutionTaskStatus.FAILED)
        self.assertEqual(result.task_results[0].errors[0].code, "old_failure")

    def test_unknown_reconciliation_remains_unresolved(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-resume")
        task_id = decomposition.tasks[0].id
        prior = TaskExecutionResult(
            result_id="running",
            run_id="run-resume",
            task_id=task_id,
            status=ExecutionTaskStatus.RUNNING,
            attempts=(Attempt(attempt_id="active", task_id=task_id),),
        )
        executor = FakeExecutor()
        engine = make_test_engine(
            executor=executor,
            reconciliation=InMemoryReconciliationPort(default_state=ReconciliationState.UNKNOWN),
        )
        run, trace = _run_and_trace(graph)
        with mock.patch.object(executor, "execute_attempt", wraps=executor.execute_attempt) as call:
            result = engine.resume_run(
                graph,
                run,
                prior_results={task_id: prior},
                stored_task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
                trace_builder=trace,
            )
            call.assert_not_called()
        self.assertEqual(result.run.status, ExecutionRunStatus.RECONCILIATION_REQUIRED)
        self.assertEqual(result.tasks[0].status, ExecutionTaskStatus.RUNNING)
        self.assertNotIn(TraceEventType.TASK_FAILED, [event.event_type for event in result.scheduler.trace.events])


class RequiredInputPolicyTest(unittest.TestCase):
    def test_missing_required_input_produces_structured_failure(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-input",
            strategy_id="strategy-input",
            created_at=datetime.now(UTC),
            nodes=[
                ExecutionGraphNode(
                    node_id="node-training",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="Training",
                    binding_ids=["missing-binding"],
                )
            ],
        )
        executor = FakeExecutor()
        engine = make_test_engine(executor=executor)
        with mock.patch.object(executor, "execute_attempt", wraps=executor.execute_attempt) as call:
            result = engine.start_run(graph, run_id="run-input")
            call.assert_not_called()
        self.assertEqual(result.run.status, ExecutionRunStatus.FAILED)
        self.assertEqual(result.tasks[0].status, ExecutionTaskStatus.FAILED)
        self.assertEqual(result.task_results[0].errors[0].phase, "input_resolution")
        self.assertIn(TraceEventType.TASK_BLOCKED, [event.event_type for event in result.scheduler.trace.events])


class RequiredOutputReuseTest(unittest.TestCase):
    def test_unrelated_valid_artifact_does_not_satisfy_resume(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-resume")
        task_id = decomposition.tasks[0].id
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-resume",
            task_id=task_id,
            attempt_id="old-attempt",
            candidate=ArtifactCandidate(logical_name="junk", artifact_type="junk"),
        )
        tracker.validate_required_outputs(
            run_id="run-resume",
            task_id=task_id,
            attempt_id="old-attempt",
            declarations=(OutputDeclaration(logical_name="junk", artifact_type="junk"),),
        )
        prior = TaskExecutionResult(
            result_id="prior-success",
            run_id="run-resume",
            task_id=task_id,
            status=ExecutionTaskStatus.SUCCESS,
            attempts=(Attempt(attempt_id="old-attempt", task_id=task_id),),
            task_result=TaskResultSummary(termination_reason="completed"),
            artifact_ids=(artifact.artifact_id,),
        )
        executor = FakeExecutor()
        engine = make_test_engine(executor=executor, artifact_tracker=tracker)
        run, trace = _run_and_trace(graph)
        with mock.patch.object(executor, "execute_attempt", wraps=executor.execute_attempt) as call:
            result = engine.resume_run(
                graph,
                run,
                prior_results={task_id: prior},
                stored_task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
                trace_builder=trace,
            )
            self.assertGreater(call.call_count, 0)
        self.assertNotIn(artifact.artifact_id, result.report.artifact_ids)


class HistoryMergeTest(unittest.TestCase):
    def test_invalidated_success_reexecution_preserves_history(self) -> None:
        graph = linear_graph()
        tracker = InMemoryArtifactTracker()
        engine = make_test_engine(artifact_tracker=tracker)
        first = engine.start_run(graph, run_id="run-history")
        task_id = first.tasks[0].id
        original = first.task_results[0]
        prior = original.model_copy(
            update={
                "errors": (ExecutionError(code="old_warning", message="historic"),),
                "logs": (LogReference(log_id="old-log"),),
                "metrics": (Metric(name="old_metric", value=1.0),),
            }
        )
        for artifact_id in original.artifact_ids:
            tracker.invalidate(artifact_id, reason="test")
        trace = ExecutionTraceBuilder(
            trace_id=first.run.trace_id,
            run_id=first.run.run_id,
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=first.run.created_at,
            initial_events=first.scheduler.trace.events,
        )
        result = engine.resume_run(
            graph,
            first.run,
            prior_results={task_id: prior},
            stored_task_fingerprint=first.task_fingerprint,
            stored_graph_fingerprint=first.graph_fingerprint,
            trace_builder=trace,
        )
        merged = next(item for item in result.task_results if item.task_id == task_id)
        self.assertEqual(len(merged.attempts), 2)
        self.assertIn("old_warning", [item.code for item in merged.errors])
        self.assertIn("old-log", [item.log_id for item in merged.logs])
        self.assertIn("old_metric", [item.name for item in merged.metrics])
        self.assertTrue(all(tracker.artifact_still_valid(item) for item in result.report.artifact_ids))


class ExpandedSemanticValidationTest(unittest.TestCase):
    def test_rejects_empty_name_and_duplicate_dependencies(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionTask(id="task", name="", type=ExecutionTaskType.TRAINING)
        with self.assertRaises(ValidationError):
            ExecutionTask(
                id="task",
                name="Training",
                type=ExecutionTaskType.TRAINING,
                dependencies=("a", "a"),
            )

    def test_rejects_duplicate_attempts_and_non_utc_time(self) -> None:
        attempt = Attempt(attempt_id="a", task_id="task")
        with self.assertRaises(ValidationError):
            TaskExecutionResult(
                result_id="result",
                run_id="run",
                task_id="task",
                status=ExecutionTaskStatus.SUCCESS,
                attempts=(attempt, attempt),
                task_result=TaskResultSummary(termination_reason="completed"),
            )
        with self.assertRaises(ValidationError):
            TraceEvent(
                event_id="event",
                event_type=TraceEventType.RUN_STARTED,
                run_id="run",
                sequence=0,
                recorded_at=datetime.now(timezone(timedelta(hours=8))),
            )

    def test_rejects_started_event_without_identity_and_reversed_run_time(self) -> None:
        with self.assertRaises(ValidationError):
            TraceEvent(
                event_id="event",
                event_type=TraceEventType.TASK_STARTED,
                run_id="run",
                sequence=0,
                recorded_at=datetime.now(UTC),
            )
        now = datetime.now(UTC)
        with self.assertRaises(ValidationError):
            ExecutionRun(
                run_id="run",
                graph_id="graph",
                strategy_id="strategy",
                status=ExecutionRunStatus.SUCCESS,
                created_at=now,
                started_at=now,
                completed_at=now - timedelta(seconds=1),
            )

    def test_rejects_inconsistent_success_report(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionReport(
                report_id="report",
                run_id="run",
                graph_id="graph",
                strategy_id="strategy",
                status=ExecutionRunStatus.SUCCESS,
                status_counts={ExecutionTaskStatus.FAILED.value: 1},
            )


class PublicBoundaryTest(unittest.TestCase):
    def test_capability_root_does_not_export_test_adapters(self) -> None:
        tree = ast.parse((ROOT / "src" / "execution" / "__init__.py").read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertFalse(any(module.startswith("execution.backends") for module in modules))
        self.assertFalse(any(module.startswith("execution.artifacts") for module in modules))
        self.assertNotIn("execution.testing", modules)


if __name__ == "__main__":
    unittest.main()
