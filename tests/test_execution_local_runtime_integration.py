"""Integration tests for Runtime-owned persistence with LocalExecutor."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from execution.backends.fake_executor import FakeExecutor
from execution.backends.local_executor import LocalExecutor
from execution.decomposition import decompose_execution_graph
from execution.engine import ExecutionEngine
from execution.ports.executor import TaskAttemptOutcome, TaskAttemptRequest
from execution.ports.persistence import RunSnapshot
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from execution.resume import compute_graph_fingerprint, compute_task_fingerprint
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    Attempt,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTaskStatus,
    ReconciliationState,
    TaskExecutionResult,
    TaskResultSummary,
    TraceEventType,
)
from runtime.context import RuntimeContext
from runtime.execution_store import ExecutionStoreFactory, FileExecutionStore
from runtime.runtime import PlatformRuntime
from tests.execution_engine_fixtures import linear_graph


def _load_execution_wiring():
    module_path = Path(__file__).resolve().parents[1] / "application" / "runtime" / "execution_wiring.py"
    spec = importlib.util.spec_from_file_location("execution_wiring_local_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _CapturingExecutor:
    """Record the last dispatch request for scheduler wiring assertions."""

    backend_kind = "fake"

    def __init__(self) -> None:
        self.last_request: TaskAttemptRequest | None = None
        self._delegate = FakeExecutor()

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        self.last_request = request
        return self._delegate.execute_attempt(request)


class _InspectingExecutor:
    """Inspect the durable snapshot at the side-effect boundary."""

    backend_kind = "fake"

    def __init__(self, store: FileExecutionStore) -> None:
        self._store = store
        self._delegate = FakeExecutor()
        self.running_snapshot = None

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        self.running_snapshot = self._store.load_snapshot(request.run_id)
        return self._delegate.execute_attempt(request)


class RuntimePersistenceOwnershipTest(unittest.TestCase):
    def test_runtime_context_owns_store_engine_receives_injection(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = PlatformRuntime()
            context = runtime.startup()
            store = wiring.bind_workspace_execution_store(context, root)
            engine = wiring.create_runtime_durable_engine(context, executor=FakeExecutor())
            self.assertIs(engine.persistence, store)
            self.assertIsInstance(store, FileExecutionStore)
            runtime.shutdown()

    def test_engine_does_not_construct_execution_store(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            factory = ExecutionStoreFactory(root)
            store = factory.store()
            engine = wiring.create_durable_engine(executor=FakeExecutor(), persistence=store)
            self.assertIs(engine.persistence, store)
            graph = linear_graph()
            engine.start_run(graph, run_id="run-owned-store")
            other = factory.store()
            self.assertIs(other, store)

    def test_file_store_run_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ExecutionStoreFactory(Path(tmp)).store()
            run_id = "run-layout-1"
            attempt_id = "att-layout-1"
            logs_dir = store.attempt_logs_dir(run_id, attempt_id)
            self.assertEqual(
                logs_dir,
                store.run_dir(run_id) / "logs" / attempt_id,
            )
            self.assertTrue(logs_dir.is_dir())


class LocalExecutorRuntimeIntegrationTest(unittest.TestCase):
    def test_logs_persisted_through_runtime_store_layout(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = wiring.workspace_execution_store(root)
            executor = wiring.create_local_executor(root)
            command = json.dumps([sys.executable, "-c", "print('runtime-log-test')"])
            task = _local_command_task(command)
            attempt_id = "att-logs-1"
            logs_dir = store.attempt_logs_dir("run-logs-1", attempt_id)
            outcome = executor.execute_attempt(
                TaskAttemptRequest(
                    run_id="run-logs-1",
                    task=task,
                    attempt_id=attempt_id,
                    logs_dir=logs_dir.as_posix(),
                )
            )
            self.assertTrue(outcome.succeeded)
            stdout_log = next(log for log in outcome.logs if log.stream == "stdout")
            log_path = Path(stdout_log.location_ref)
            self.assertTrue(log_path.is_file())
            self.assertEqual(log_path.parent, logs_dir)
            self.assertIn("runtime-log-test", log_path.read_text(encoding="utf-8"))

    def test_local_executor_requires_runtime_provided_log_path(self) -> None:
        executor = LocalExecutor()
        task = _local_command_task(json.dumps([sys.executable, "-c", "print('x')"]))
        with self.assertRaises(ValueError):
            executor.execute_attempt(
                TaskAttemptRequest(run_id="run-1", task=task, attempt_id="att-1")
            )

    def test_scheduler_injects_runtime_logs_dir(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = wiring.workspace_execution_store(root)
            capturing = _CapturingExecutor()
            engine = wiring.create_durable_engine(
                executor=capturing,
                persistence=store,
            )
            engine.start_run(linear_graph(), run_id="run-scheduler-logs")
            self.assertIsNotNone(capturing.last_request)
            assert capturing.last_request is not None
            self.assertTrue(capturing.last_request.logs_dir)
            expected_prefix = store.run_logs_dir("run-scheduler-logs").as_posix()
            self.assertTrue(capturing.last_request.logs_dir.startswith(expected_prefix))

    def test_runtime_durable_local_engine_wiring(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = PlatformRuntime()
            context = runtime.startup()
            engine = wiring.create_runtime_durable_local_engine(context, root)
            self.assertIsInstance(engine.persistence, FileExecutionStore)
            runtime.shutdown()


class DurablePersistenceResumeTest(unittest.TestCase):
    def test_attempt_is_durable_before_executor_side_effect(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = wiring.workspace_execution_store(root)
            executor = _InspectingExecutor(store)
            engine = wiring.create_durable_engine(executor=executor, persistence=store)
            engine.start_run(linear_graph(), run_id="run-attempt-boundary")
            snapshot = executor.running_snapshot
            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            running_results = [
                result
                for result in snapshot.task_results
                if result.status is ExecutionTaskStatus.RUNNING
            ]
            self.assertEqual(len(running_results), 1)
            self.assertEqual(len(running_results[0].attempts), 1)
            self.assertTrue(running_results[0].attempts[0].backend_operation_ref)

    def test_reload_completed_task_after_restart(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = wiring.create_durable_engine(
                executor=FakeExecutor(),
                persistence=wiring.workspace_execution_store(root),
            )
            graph = linear_graph()
            first.start_run(graph, run_id="run-reload-1")
            second = wiring.create_durable_engine(
                executor=FakeExecutor(),
                persistence=wiring.workspace_execution_store(root),
            )
            resumed = second.load_and_resume_run(graph, "run-reload-1")
            self.assertEqual(resumed.run.status, ExecutionRunStatus.SUCCESS)

    def test_reconcile_interrupted_running_task(self) -> None:
        wiring = _load_execution_wiring()
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-interrupted")
        task_id = decomposition.tasks[0].id
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = wiring.workspace_execution_store(root)
            reconciliation = InMemoryReconciliationPort(
                states_by_attempt={"att-1": ReconciliationState.SUCCEEDED},
            )
            from execution.artifacts.in_memory import InMemoryArtifactTracker
            from execution.input_resolver.in_memory import InMemoryInputResolver
            from execution.ports.executor import ArtifactCandidate

            tracker = InMemoryArtifactTracker()
            artifact = tracker.register_candidate(
                run_id="run-interrupted",
                task_id=task_id,
                attempt_id="att-1",
                candidate=ArtifactCandidate(logical_name="environment", artifact_type="environment"),
            )
            tracker.validate_required_outputs(
                run_id="run-interrupted",
                task_id=task_id,
                attempt_id="att-1",
                declarations=decomposition.tasks[0].outputs,
            )
            engine = wiring.create_durable_engine(
                executor=FakeExecutor(),
                persistence=store,
                artifact_tracker=tracker,
                input_resolver=InMemoryInputResolver(tracker),
                reconciliation=reconciliation,
            )
            now = datetime(2026, 7, 13, tzinfo=UTC)
            trace_builder = ExecutionTraceBuilder(
                trace_id="trace-interrupted",
                run_id="run-interrupted",
                graph_id=graph.graph_id,
                strategy_id=graph.strategy_id,
                created_at=now,
                initial_events=decomposition.events,
            )
            trace_builder.append(
                TraceEventType.TASK_STARTED,
                task_id=task_id,
                attempt_id="att-1",
                actor="scheduler",
            )
            run = ExecutionRun(
                run_id="run-interrupted",
                graph_id=graph.graph_id,
                strategy_id=graph.strategy_id,
                status=ExecutionRunStatus.RUNNING,
                task_ids=tuple(task.id for task in decomposition.tasks),
                trace_id="trace-interrupted",
                created_at=now,
                started_at=now,
            )
            prior = {
                task_id: TaskExecutionResult(
                    result_id="res-1",
                    run_id="run-interrupted",
                    task_id=task_id,
                    status=ExecutionTaskStatus.RUNNING,
                    attempts=(
                        Attempt(
                            attempt_id="att-1",
                            task_id=task_id,
                            backend_operation_ref="op-1",
                            started_at=now,
                        ),
                    ),
                    task_result=TaskResultSummary(termination_reason="running"),
                    artifact_ids=(artifact.artifact_id,),
                )
            }
            snapshot = RunSnapshot(
                run=run,
                tasks=decomposition.tasks,
                task_results=tuple(prior.values()),
                trace=trace_builder.build(),
                artifacts=(artifact,),
                report=None,
                revision=1,
                task_fingerprint=compute_task_fingerprint(decomposition.tasks),
                graph_fingerprint=compute_graph_fingerprint(graph),
            )
            store.create_run(snapshot)
            result = engine.resume_run(
                graph,
                run,
                prior_results=prior,
                stored_task_fingerprint=snapshot.task_fingerprint,
                stored_graph_fingerprint=snapshot.graph_fingerprint,
                trace_builder=trace_builder,
            )
            self.assertEqual(result.run.status, ExecutionRunStatus.SUCCESS)
            reloaded = store.load_snapshot("run-interrupted")
            self.assertGreater(reloaded.revision, snapshot.revision)

    def test_missing_artifact_invalidates_success_on_resume(self) -> None:
        wiring = _load_execution_wiring()
        graph = linear_graph()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = wiring.workspace_execution_store(root)
            from execution.artifacts.in_memory import InMemoryArtifactTracker
            from execution.input_resolver.in_memory import InMemoryInputResolver
            from execution.ports.executor import ArtifactCandidate
            from unittest import mock

            tracker = InMemoryArtifactTracker()
            engine = wiring.create_durable_engine(
                executor=FakeExecutor(),
                persistence=store,
                artifact_tracker=tracker,
                input_resolver=InMemoryInputResolver(tracker),
            )
            engine.start_run(graph, run_id="run-missing-artifact")
            snapshot = store.load_snapshot("run-missing-artifact")
            self.assertGreater(len(snapshot.artifacts), 0)
            artifact_id = snapshot.artifacts[0].artifact_id
            tracker.invalidate(artifact_id, reason="missing_on_disk")
            resumed = engine.load_and_resume_run(graph, "run-missing-artifact")
            self.assertEqual(resumed.run.status, ExecutionRunStatus.SUCCESS)


def _local_command_task(command_args: str):
    from models.execution_engine import ExecutionTask, ExecutionTaskType

    return ExecutionTask(
        id="task-local-cmd",
        name="Local Command",
        type=ExecutionTaskType.TRAINING,
        metadata={"command": command_args},
    )


if __name__ == "__main__":
    unittest.main()
