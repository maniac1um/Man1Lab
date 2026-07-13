"""Regression tests for execution engine architecture audit remediation."""

from __future__ import annotations

import ast
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor, FakeExecutorRule
from execution.decomposition import decompose_execution_graph, task_id_for_node
from execution.errors import ArtifactValidationError, ExecutionEngineError, InvalidTransitionError
from execution.ports.executor import ArtifactCandidate, TaskAttemptRequest
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from execution.resume import compute_graph_fingerprint, compute_task_fingerprint
from execution.testing import make_test_engine
from execution.trace import ExecutionTraceBuilder, validate_trace_events
from execution.transitions import transition_task
from models.execution_engine import (
    ArtifactScope,
    Attempt,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionTaskType,
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


class ArtifactIsolationTest(unittest.TestCase):
    def test_cross_run_isolation(self) -> None:
        tracker = InMemoryArtifactTracker()
        tracker.register_candidate(
            run_id="run-a",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="dataset"),
        )
        with self.assertRaises(ArtifactValidationError):
            tracker.validate_required_outputs(
                run_id="run-b",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(
                    OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
                ),
            )

    def test_cross_attempt_isolation(self) -> None:
        tracker = InMemoryArtifactTracker()
        tracker.register_candidate(
            run_id="run-a",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="dataset"),
        )
        with self.assertRaises(ArtifactValidationError):
            tracker.validate_required_outputs(
                run_id="run-a",
                task_id="task-1",
                attempt_id="att-2",
                declarations=(
                    OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
                ),
            )

    def test_wrong_type_fails(self) -> None:
        tracker = InMemoryArtifactTracker()
        tracker.register_candidate(
            run_id="run-a",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="wrong"),
        )
        with self.assertRaises(ArtifactValidationError):
            tracker.validate_required_outputs(
                run_id="run-a",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(
                    OutputDeclaration(logical_name="dataset", artifact_type="dataset", required=True),
                ),
            )

    def test_unsupported_rule_fails(self) -> None:
        tracker = InMemoryArtifactTracker()
        tracker.register_candidate(
            run_id="run-a",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="dataset", artifact_type="dataset"),
        )
        with self.assertRaises(ArtifactValidationError):
            tracker.validate_required_outputs(
                run_id="run-a",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(
                    OutputDeclaration(
                        logical_name="dataset",
                        artifact_type="dataset",
                        required=True,
                        validation_rule="sha256",
                    ),
                ),
            )

    def test_optional_missing_ok(self) -> None:
        tracker = InMemoryArtifactTracker()
        validated = tracker.validate_required_outputs(
            run_id="run-a",
            task_id="task-1",
            attempt_id="att-1",
            declarations=(
                OutputDeclaration(logical_name="optional", artifact_type="dataset", required=False),
            ),
        )
        self.assertEqual(validated, ())


class ResumeReconciliationTest(unittest.TestCase):
    def test_running_resume_does_not_redispatch(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        task_id = decomposition.tasks[0].id
        executor = FakeExecutor()
        reconciliation = InMemoryReconciliationPort(
            default_state=ReconciliationState.STILL_RUNNING,
            states_by_attempt={"att-1": ReconciliationState.STILL_RUNNING},
        )
        engine = make_test_engine(executor=executor, reconciliation=reconciliation)
        prior = {
            task_id: TaskExecutionResult(
                result_id="res-1",
                run_id="run-1",
                task_id=task_id,
                status=ExecutionTaskStatus.RUNNING,
                attempts=(Attempt(attempt_id="att-1", task_id=task_id),),
            )
        }
        run = ExecutionRun(
            run_id="run-1",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
        )
        trace_builder = ExecutionTraceBuilder(
            trace_id="trace-1",
            run_id="run-1",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=run.created_at,
        )
        with mock.patch.object(executor, "execute_attempt", wraps=executor.execute_attempt) as execute_mock:
            result = engine.resume_run(
                graph,
                run,
                prior_results=prior,
                stored_task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
                trace_builder=trace_builder,
            )
            execute_mock.assert_not_called()
        started = [
            event
            for event in result.scheduler.trace.events
            if event.event_type == TraceEventType.TASK_STARTED and event.task_id == task_id
        ]
        self.assertEqual(len(started), 0)
        self.assertEqual(result.run.status, ExecutionRunStatus.INTERRUPTED)


class FingerprintTest(unittest.TestCase):
    def test_status_change_does_not_change_task_fingerprint(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        fp1 = compute_task_fingerprint(decomposition.tasks)
        changed = tuple(
            task.model_copy(update={"status": ExecutionTaskStatus.SUCCESS}) for task in decomposition.tasks
        )
        fp2 = compute_task_fingerprint(changed)
        self.assertEqual(fp1, fp2)

    def test_description_change_changes_task_fingerprint(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        fp1 = compute_task_fingerprint(decomposition.tasks)
        changed = (decomposition.tasks[0].model_copy(update={"description": "changed"}),) + decomposition.tasks[1:]
        fp2 = compute_task_fingerprint(changed)
        self.assertNotEqual(fp1, fp2)

    def test_graph_label_change_changes_graph_fingerprint(self) -> None:
        graph = linear_graph()
        fp1 = compute_graph_fingerprint(graph)
        node = graph.nodes[0].model_copy(update={"label": "Changed"})
        changed = ExecutionGraph(
            graph_id=graph.graph_id,
            created_at=graph.created_at,
            strategy_id=graph.strategy_id,
            nodes=[node] + graph.nodes[1:],
        )
        fp2 = compute_graph_fingerprint(changed)
        self.assertNotEqual(fp1, fp2)


class SemanticValidationTest(unittest.TestCase):
    def test_rejects_secret_metadata_key(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionTask(
                id="task-1",
                name="x",
                type=ExecutionTaskType.TRAINING,
                metadata={"api_key": "secret"},
            )

    def test_failed_result_requires_errors(self) -> None:
        with self.assertRaises(ValidationError):
            TaskExecutionResult(
                result_id="res-1",
                run_id="run-1",
                task_id="task-1",
                status=ExecutionTaskStatus.FAILED,
                attempts=(Attempt(attempt_id="att-1", task_id="task-1"),),
                task_result=TaskResultSummary(termination_reason="failed"),
            )


class ImportBoundaryTest(unittest.TestCase):
    def _forbidden_imports(self, relative_path: str) -> list[str]:
        path = ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                if module.startswith("execution.backends") or module.startswith("execution.artifacts"):
                    forbidden.append(module)
        return forbidden

    def test_engine_import_boundary(self) -> None:
        self.assertEqual(self._forbidden_imports("execution/engine.py"), [])

    def test_scheduling_import_boundary(self) -> None:
        self.assertEqual(self._forbidden_imports("execution/scheduling.py"), [])


class ExecutorExceptionTest(unittest.TestCase):
    def test_executor_exception_marks_failed(self) -> None:
        class BrokenExecutor:
            backend_kind = "fake"

            def execute_attempt(self, request):
                raise RuntimeError("password=secret boom")

        graph = linear_graph()
        engine = make_test_engine(executor=BrokenExecutor())
        result = engine.start_run(graph, run_id="run-exc")
        self.assertEqual(result.run.status, ExecutionRunStatus.FAILED)
        failed = next(item for item in result.task_results if item.status == ExecutionTaskStatus.FAILED)
        self.assertNotIn("secret", failed.errors[0].message)
        self.assertTrue(all(task.status != ExecutionTaskStatus.RUNNING for task in result.tasks))


class TransitionApiTest(unittest.TestCase):
    def test_legal_and_illegal_transitions(self) -> None:
        task = ExecutionTask(id="t", name="n", type=ExecutionTaskType.TRAINING)
        ready = transition_task(task, ExecutionTaskStatus.READY)
        self.assertEqual(ready.status, ExecutionTaskStatus.READY)
        with self.assertRaises(InvalidTransitionError):
            transition_task(task, ExecutionTaskStatus.SUCCESS)


class TraceValidationTest(unittest.TestCase):
    def test_rejects_completion_before_start(self) -> None:
        now = datetime(2026, 7, 13, tzinfo=UTC)
        events = (
            TraceEvent(
                event_id="evt-1",
                event_type=TraceEventType.TASK_COMPLETED,
                run_id="run-1",
                sequence=0,
                recorded_at=now,
                task_id="task-1",
                attempt_id="att-1",
            ),
        )
        with self.assertRaises(ValueError):
            validate_trace_events(run_id="run-1", events=events)


if __name__ == "__main__":
    unittest.main()
