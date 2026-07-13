"""Tests for resume foundation logic."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor
from execution.decomposition import decompose_execution_graph, task_id_for_node
from execution.testing import make_test_engine
from execution.errors import ResumeRejectedError
from execution.resume import (
    apply_resume_reuse,
    assert_resume_compatible,
    compute_graph_fingerprint,
    compute_task_fingerprint,
    evaluate_resume_tasks,
)
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    Attempt,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTaskStatus,
    TaskExecutionResult,
    TaskResultSummary,
    TraceEventType,
)
from tests.execution_engine_fixtures import linear_graph


class ExecutionResumeTest(unittest.TestCase):
    def test_fingerprint_mismatch_rejects_resume(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        run = ExecutionRun(
            run_id="run-1",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
        )
        with self.assertRaises(ResumeRejectedError):
            assert_resume_compatible(
                existing_run=run,
                graph=graph,
                tasks=decomposition.tasks,
                stored_task_fingerprint="different",
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
            )

    def test_graph_id_mismatch_rejects_resume(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        run = ExecutionRun(
            run_id="run-1",
            graph_id="other-graph",
            strategy_id=graph.strategy_id,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
        )
        with self.assertRaises(ResumeRejectedError):
            assert_resume_compatible(
                existing_run=run,
                graph=graph,
                tasks=decomposition.tasks,
                stored_task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                stored_graph_fingerprint=compute_graph_fingerprint(graph),
            )

    def test_running_task_is_indeterminate(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        task_id = decomposition.tasks[0].id
        prior = {
            task_id: TaskExecutionResult(
                result_id="res-1",
                run_id="run-1",
                task_id=task_id,
                status=ExecutionTaskStatus.RUNNING,
                attempts=(Attempt(attempt_id="att-1", task_id=task_id),),
            )
        }
        evaluation = evaluate_resume_tasks(
            tasks=decomposition.tasks,
            prior_results=prior,
            artifact_valid=lambda _artifact_id: True,
        )
        self.assertIn(task_id, evaluation.indeterminate_task_ids)

    def test_success_reused_only_when_artifacts_valid(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        task_id = decomposition.tasks[0].id
        prior = {
            task_id: TaskExecutionResult(
                result_id="res-1",
                run_id="run-1",
                task_id=task_id,
                status=ExecutionTaskStatus.SUCCESS,
                attempts=(Attempt(attempt_id="att-1", task_id=task_id),),
                artifact_ids=("art-1",),
                task_result=TaskResultSummary(termination_reason="completed"),
            )
        }
        invalid = evaluate_resume_tasks(
            tasks=decomposition.tasks,
            prior_results=prior,
            artifact_valid=lambda _artifact_id: False,
        )
        self.assertNotIn(task_id, invalid.reusable_task_ids)

        valid = evaluate_resume_tasks(
            tasks=decomposition.tasks,
            prior_results=prior,
            artifact_valid=lambda _artifact_id: True,
        )
        self.assertIn(task_id, valid.reusable_task_ids)

    def test_apply_resume_reuse_marks_success_tasks(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-1")
        task_id = decomposition.tasks[0].id
        from execution.resume import ResumeEvaluation

        evaluation = ResumeEvaluation(
            reusable_task_ids=(task_id,),
            pending_task_ids=tuple(task.id for task in decomposition.tasks[1:]),
            indeterminate_task_ids=(),
            rejected_task_ids=(),
        )
        resumed = apply_resume_reuse(decomposition.tasks, evaluation)
        self.assertEqual(resumed[0].status, ExecutionTaskStatus.SUCCESS)

    def test_engine_resume_emits_run_resumed(self) -> None:
        engine = make_test_engine()
        graph = linear_graph()
        first = engine.start_run(graph, run_id="run-resume")
        prep_task = task_id_for_node("node-prepare-environment")
        prior = {result.task_id: result for result in first.task_results}
        trace_builder = ExecutionTraceBuilder(
            trace_id=first.run.trace_id,
            run_id=first.run.run_id,
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=first.run.created_at,
            initial_events=first.scheduler.trace.events,
        )
        resumed = engine.resume_run(
            graph,
            first.run,
            prior_results=prior,
            stored_task_fingerprint=first.task_fingerprint,
            stored_graph_fingerprint=first.graph_fingerprint,
            trace_builder=trace_builder,
        )
        event_types = [event.event_type for event in resumed.scheduler.trace.events]
        self.assertIn(TraceEventType.RUN_RESUMED, event_types)
        self.assertEqual(resumed.run.status, ExecutionRunStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
