"""Phase 2 integration tests for durable execution runtime."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor
from execution.decomposition import decompose_execution_graph
from execution.engine import ExecutionEngine
from execution.errors import (
    ArtifactIntegrityError,
    ArtifactProducerMismatchError,
    UnsafeArtifactLocationError,
)
from execution.input_resolver.in_memory import InMemoryInputResolver
from execution.persistence.in_memory import InMemoryExecutionStore
from execution.ports.executor import ArtifactCandidate
from execution.ports.persistence import RunSnapshot
from execution.reconciliation.in_memory import InMemoryReconciliationPort
from execution.resume import compute_graph_fingerprint, compute_task_fingerprint
from execution.testing import make_test_engine
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    ArtifactScope,
    ArtifactValidationState,
    Attempt,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTaskStatus,
    OutputDeclaration,
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
    module_path = Path(__file__).resolve().parents[1] / "src" / "application" / "runtime" / "execution_wiring.py"
    spec = importlib.util.spec_from_file_location("execution_wiring_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _create_durable_engine(
    workspace_root: Path,
    *,
    artifact_tracker: InMemoryArtifactTracker | None = None,
) -> ExecutionEngine:
    wiring = _load_execution_wiring()
    store = ExecutionStoreFactory(workspace_root).store()
    tracker = artifact_tracker or InMemoryArtifactTracker()
    return wiring.create_durable_engine(
        executor=FakeExecutor(),
        persistence=store,
        artifact_tracker=tracker,
        input_resolver=InMemoryInputResolver(tracker),
    )


class ExecutionRuntimeIntegrationTest(unittest.TestCase):
    def test_durable_start_run_persists_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = _create_durable_engine(Path(tmp))
            graph = linear_graph()
            result = engine.start_run(graph, run_id="run-durable-1")
            store = ExecutionStoreFactory(Path(tmp)).store()
            snapshot = store.load_snapshot("run-durable-1")
            self.assertEqual(snapshot.run.run_id, "run-durable-1")
            self.assertGreater(snapshot.revision, 0)
            self.assertGreater(len(snapshot.trace.events), 0)
            self.assertIsNotNone(result.report)
            self.assertTrue((store.run_dir("run-durable-1") / "report.json").is_file())

    def test_cross_process_load_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = linear_graph()
            first = _create_durable_engine(root)
            first_result = first.start_run(graph, run_id="run-resume-1")
            self.assertEqual(first_result.run.status, ExecutionRunStatus.SUCCESS)

            second_tracker = InMemoryArtifactTracker()
            second = _create_durable_engine(root, artifact_tracker=second_tracker)
            resumed = second.load_and_resume_run(graph, "run-resume-1")
            self.assertEqual(resumed.run.run_id, "run-resume-1")
            self.assertEqual(resumed.run.status, ExecutionRunStatus.SUCCESS)

    def test_in_memory_persistence_with_engine(self) -> None:
        store = InMemoryExecutionStore()
        engine = make_test_engine(persistence=store)
        graph = linear_graph()
        engine.start_run(graph, run_id="run-mem-1")
        snapshot = store.load_snapshot("run-mem-1")
        self.assertGreater(snapshot.revision, 0)

    def test_reconcile_running_attempt_on_resume(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-reconcile")
        task_id = decomposition.tasks[0].id
        store = InMemoryExecutionStore()
        reconciliation = InMemoryReconciliationPort(
            states_by_attempt={"att-1": ReconciliationState.SUCCEEDED},
        )
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-reconcile",
            task_id=task_id,
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="environment", artifact_type="environment"),
        )
        tracker.validate_required_outputs(
            run_id="run-reconcile",
            task_id=task_id,
            attempt_id="att-1",
            declarations=decomposition.tasks[0].outputs,
        )
        engine = make_test_engine(
            persistence=store,
            reconciliation=reconciliation,
            artifact_tracker=tracker,
        )
        now = datetime(2026, 7, 13, tzinfo=UTC)
        trace_builder = ExecutionTraceBuilder(
            trace_id="trace-reconcile",
            run_id="run-reconcile",
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
            run_id="run-reconcile",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            status=ExecutionRunStatus.RUNNING,
            task_ids=tuple(task.id for task in decomposition.tasks),
            trace_id="trace-reconcile",
            created_at=now,
            started_at=now,
        )
        prior = {
            task_id: TaskExecutionResult(
                result_id="res-1",
                run_id="run-reconcile",
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
        self.assertIn(
            TraceEventType.RUN_RESUMED,
            {event.event_type for event in result.scheduler.trace.events},
        )
        self.assertEqual(result.run.status, ExecutionRunStatus.SUCCESS)

    def test_artifact_verification_before_reuse(self) -> None:
        graph = linear_graph()
        store = InMemoryExecutionStore()
        tracker = InMemoryArtifactTracker()
        engine = make_test_engine(persistence=store, artifact_tracker=tracker)
        engine.start_run(graph, run_id="run-artifacts")
        snapshot = store.load_snapshot("run-artifacts")
        self.assertGreater(len(snapshot.artifacts), 0)

    def test_runtime_application_wiring_path(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = PlatformRuntime()
            context = runtime.startup()
            store = wiring.bind_workspace_execution_store(context, root)
            engine = wiring.create_runtime_durable_engine(context, executor=FakeExecutor())
            graph = linear_graph()
            result = engine.start_run(graph, run_id="run-runtime-path")
            self.assertEqual(result.run.status, ExecutionRunStatus.SUCCESS)
            reloaded = store.load_snapshot("run-runtime-path")
            self.assertEqual(reloaded.run.run_id, "run-runtime-path")
            runtime.shutdown()

    def test_workspace_switch_uses_scoped_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_a = Path(tmp) / "ws-a"
            root_b = Path(tmp) / "ws-b"
            root_a.mkdir()
            root_b.mkdir()
            factory = ExecutionStoreFactory(root_a)
            store_a = factory.store()
            store_b = factory.for_workspace(root_b).store()
            snapshot = _sample_snapshot_for_workspace("run-ws", root_a)
            store_a.create_run(snapshot)
            with self.assertRaises(Exception):
                store_b.load_snapshot("run-ws")

    def test_runtime_shutdown_releases_locks(self) -> None:
        wiring = _load_execution_wiring()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = PlatformRuntime()
            context = runtime.startup()
            wiring.bind_workspace_execution_store(context, root)
            store = context.execution_store()
            snapshot = _sample_snapshot_for_workspace("run-lock-release", root)
            store.create_run(snapshot)
            store.acquire_writer("run-lock-release")
            runtime.shutdown()
            other = FileExecutionStore(root / "execution" / "runs")
            other.acquire_writer("run-lock-release")
            other.release_writer("run-lock-release")


class ArtifactVerificationTest(unittest.TestCase):
    def test_path_traversal_rejected(self) -> None:
        tracker = InMemoryArtifactTracker()
        with self.assertRaises(UnsafeArtifactLocationError):
            tracker.register_candidate(
                run_id="run-1",
                task_id="task-1",
                attempt_id="att-1",
                candidate=ArtifactCandidate(
                    logical_name="output",
                    artifact_type="file",
                    location_ref="../escape/data.bin",
                ),
            )

    def test_producer_mismatch_rejected(self) -> None:
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-1",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(logical_name="environment", artifact_type="environment"),
        )
        tracker._artifacts[artifact.artifact_id] = artifact.model_copy(
            update={"producer_task_id": "task-other"}
        )
        with self.assertRaises(ArtifactProducerMismatchError):
            tracker.validate_required_outputs(
                run_id="run-1",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(OutputDeclaration(logical_name="environment", artifact_type="environment"),),
            )

    def test_checksum_mismatch_rejected(self) -> None:
        tracker = InMemoryArtifactTracker()
        tracker.register_candidate(
            run_id="run-1",
            task_id="task-1",
            attempt_id="att-1",
            candidate=ArtifactCandidate(
                logical_name="model",
                artifact_type="checkpoint",
                integrity_digest="abc123",
            ),
        )
        with self.assertRaises(ArtifactIntegrityError):
            tracker.validate_required_outputs(
                run_id="run-1",
                task_id="task-1",
                attempt_id="att-1",
                declarations=(
                    OutputDeclaration(
                        logical_name="model",
                        artifact_type="checkpoint",
                        validation_rule="digest",
                        integrity_hint="different",
                    ),
                ),
            )

    def test_invalid_state_blocks_reuse(self) -> None:
        graph = linear_graph()
        decomposition = decompose_execution_graph(graph, run_id="run-invalid-art")
        task_id = decomposition.tasks[0].id
        tracker = InMemoryArtifactTracker()
        artifact = tracker.register_candidate(
            run_id="run-invalid-art",
            task_id=task_id,
            attempt_id="att-old",
            candidate=ArtifactCandidate(logical_name="environment", artifact_type="environment"),
        )
        tracker.validate_required_outputs(
            run_id="run-invalid-art",
            task_id=task_id,
            attempt_id="att-old",
            declarations=decomposition.tasks[0].outputs,
        )
        tracker.invalidate(artifact.artifact_id, reason="missing_on_disk")
        prior = TaskExecutionResult(
            result_id="res-old",
            run_id="run-invalid-art",
            task_id=task_id,
            status=ExecutionTaskStatus.SUCCESS,
            attempts=(Attempt(attempt_id="att-old", task_id=task_id),),
            task_result=TaskResultSummary(termination_reason="completed"),
            artifact_ids=(artifact.artifact_id,),
        )
        executor = FakeExecutor()
        engine = make_test_engine(artifact_tracker=tracker, executor=executor)
        run = ExecutionRun(
            run_id="run-invalid-art",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime.now(UTC),
        )
        trace = ExecutionTraceBuilder(
            trace_id="trace-invalid",
            run_id="run-invalid-art",
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=datetime.now(UTC),
        )
        from unittest import mock

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
        self.assertIn(task_id, {event.task_id for event in result.scheduler.trace.events})


def _sample_snapshot_for_workspace(run_id: str, workspace_root: Path) -> RunSnapshot:
    graph = linear_graph()
    decomposition = decompose_execution_graph(graph, run_id=run_id)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    trace = ExecutionTraceBuilder(
        trace_id="trace-1",
        run_id=run_id,
        graph_id=graph.graph_id,
        strategy_id=graph.strategy_id,
        created_at=now,
        initial_events=decomposition.events,
    ).build()
    run = ExecutionRun(
        run_id=run_id,
        graph_id=graph.graph_id,
        strategy_id=graph.strategy_id,
        status=ExecutionRunStatus.PENDING,
        task_ids=tuple(task.id for task in decomposition.tasks),
        trace_id="trace-1",
        created_at=now,
    )
    return RunSnapshot(
        run=run,
        tasks=decomposition.tasks,
        task_results=(),
        trace=trace,
        artifacts=(),
        report=None,
        revision=0,
        task_fingerprint=compute_task_fingerprint(decomposition.tasks),
        graph_fingerprint=compute_graph_fingerprint(graph),
    )


class ImportBoundaryTest(unittest.TestCase):
    def test_engine_does_not_import_runtime(self) -> None:
        import execution.engine as engine_module

        source_path = Path(engine_module.__file__).resolve()
        text = source_path.read_text(encoding="utf-8")
        self.assertNotIn("runtime.", text)
        self.assertNotIn("from runtime", text)

    def test_runtime_file_store_does_not_import_scheduler(self) -> None:
        import runtime.execution_store.file_store as store_module

        text = Path(store_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("execution.scheduling", text)
        self.assertNotIn("execution.engine", text)


if __name__ == "__main__":
    unittest.main()
