"""Tests for sequential scheduler behavior."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor, FakeExecutorRule
from execution.decomposition import decompose_execution_graph, task_id_for_node
from execution.input_resolver.in_memory import InMemoryInputResolver
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from execution.scheduling import SequentialScheduler
from execution.trace import ExecutionTraceBuilder
from execution.transitions import transition_task
from execution.errors import InvalidTransitionError
from models.execution_engine import (
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTaskStatus,
    TraceEventType,
)
from tests.execution_engine_fixtures import branching_graph, linear_graph


class SequentialSchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tracker = InMemoryArtifactTracker()
        self._resolver = InMemoryInputResolver(self._tracker)
        self._reconciliation = InMemoryReconciliationPort()

    def _scheduler(self, executor: FakeExecutor | None = None) -> SequentialScheduler:
        return SequentialScheduler(
            executor or FakeExecutor(),
            self._tracker,
            self._resolver,
            self._reconciliation,
        )

    def _run_graph(self, graph, *, executor: FakeExecutor | None = None, cancelled: bool = False):
        decomposition = decompose_execution_graph(graph, run_id="run-sched")
        trace_builder = ExecutionTraceBuilder(
            trace_id="trace-sched",
            run_id="run-sched",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
            initial_events=decomposition.events,
        )
        run = ExecutionRun(
            run_id="run-sched",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
        )
        return self._scheduler(executor).run(
            run=run,
            tasks=decomposition.tasks,
            trace_builder=trace_builder,
            cancelled=cancelled,
        )

    def test_linear_success_path(self) -> None:
        result = self._run_graph(linear_graph())
        self.assertEqual(result.run.status, ExecutionRunStatus.SUCCESS)
        self.assertTrue(all(task.status == ExecutionTaskStatus.SUCCESS for task in result.tasks))

    def test_branching_dag_success(self) -> None:
        result = self._run_graph(branching_graph())
        self.assertEqual(result.run.status, ExecutionRunStatus.SUCCESS)
        self.assertEqual(len(result.task_results), 4)

    def test_failure_propagation_and_fail_fast(self) -> None:
        failing_task = task_id_for_node("node-training")
        executor = FakeExecutor(
            rules_by_task_id={
                failing_task: FakeExecutorRule(succeed=False, exit_code=1, produce_outputs=False),
            }
        )
        result = self._run_graph(linear_graph(), executor=executor)
        self.assertEqual(result.run.status, ExecutionRunStatus.FAILED)
        by_id = {task.id: task for task in result.tasks}
        self.assertEqual(by_id[failing_task].status, ExecutionTaskStatus.FAILED)
        self.assertEqual(
            by_id[task_id_for_node("node-evaluation")].status,
            ExecutionTaskStatus.SKIPPED,
        )

    def test_branch_fail_fast_skips_independent_branch(self) -> None:
        failing_task = task_id_for_node("node-download-dataset")
        executor = FakeExecutor(
            rules_by_task_id={
                failing_task: FakeExecutorRule(succeed=False, produce_outputs=False),
            }
        )
        result = self._run_graph(branching_graph(), executor=executor)
        by_id = {task.id: task for task in result.tasks}
        self.assertEqual(by_id[failing_task].status, ExecutionTaskStatus.FAILED)
        self.assertEqual(
            by_id[task_id_for_node("node-training")].status,
            ExecutionTaskStatus.SKIPPED,
        )

    def test_cancel_run(self) -> None:
        result = self._run_graph(linear_graph(), cancelled=True)
        self.assertEqual(result.run.status, ExecutionRunStatus.CANCELLED)
        self.assertTrue(
            all(
                task.status == ExecutionTaskStatus.CANCELLED
                for task in result.tasks
            )
        )

    def test_artifact_validation_failure_marks_task_failed(self) -> None:
        failing_task = task_id_for_node("node-training")
        executor = FakeExecutor(
            rules_by_task_id={
                failing_task: FakeExecutorRule(succeed=True, produce_outputs=False),
            }
        )
        result = self._run_graph(linear_graph(), executor=executor)
        by_id = {task.id: task for task in result.tasks}
        self.assertEqual(by_id[failing_task].status, ExecutionTaskStatus.FAILED)

    def test_event_sequence_contains_lifecycle_events(self) -> None:
        result = self._run_graph(linear_graph())
        event_types = [event.event_type for event in result.trace.events]
        self.assertIn(TraceEventType.RUN_STARTED, event_types)
        self.assertIn(TraceEventType.TASK_READY, event_types)
        self.assertIn(TraceEventType.TASK_STARTED, event_types)
        self.assertIn(TraceEventType.TASK_COMPLETED, event_types)
        self.assertIn(TraceEventType.RUN_COMPLETED, event_types)

    def test_illegal_transition_raises(self) -> None:
        decomposition = decompose_execution_graph(linear_graph(), run_id="run-illegal")
        task = decomposition.tasks[0]
        with self.assertRaises(InvalidTransitionError):
            transition_task(task, ExecutionTaskStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
