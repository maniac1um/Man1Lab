"""Tests for execution persistence port and file store."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from execution.decomposition import decompose_execution_graph
from execution.errors import (
    CorruptSnapshotError,
    IncompatibleSchemaError,
    MalformedLockError,
    MixedRevisionSnapshotError,
    RunExistsError,
    RunNotFoundError,
    WriterConflictError,
)
from execution.persistence.in_memory import InMemoryExecutionStore
from execution.ports.persistence import RunSnapshot, TransitionCommit
from execution.resume import compute_graph_fingerprint, compute_task_fingerprint
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    ExecutionRun,
    ExecutionRunStatus,
    TraceEventType,
)
from runtime.execution_store.atomic_io import atomic_write_json, read_jsonl
from runtime.execution_store.file_store import FileExecutionStore, REPORT_JSON, RUN_JSON, TASKS_JSON
from runtime.execution_store.journal import JournalStatus, TransitionJournalRecord, journal_path, write_journal
from runtime.execution_store.locking import RunWriterLock
from runtime.execution_store.snapshot_meta import unwrap_snapshot_payload, wrap_snapshot_payload
from tests.execution_engine_fixtures import linear_graph


def _sample_snapshot(run_id: str = "run-test") -> RunSnapshot:
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


class InMemoryExecutionStoreTest(unittest.TestCase):
    def test_create_load_round_trip(self) -> None:
        store = InMemoryExecutionStore()
        snapshot = _sample_snapshot()
        store.create_run(snapshot)
        loaded = store.load_snapshot("run-test")
        self.assertEqual(loaded.run.run_id, "run-test")
        self.assertEqual(len(loaded.tasks), len(snapshot.tasks))
        self.assertEqual(loaded.revision, 0)

    def test_create_duplicate_rejected(self) -> None:
        store = InMemoryExecutionStore()
        store.create_run(_sample_snapshot())
        with self.assertRaises(RunExistsError):
            store.create_run(_sample_snapshot())

    def test_commit_transition_idempotent(self) -> None:
        store = InMemoryExecutionStore()
        snapshot = _sample_snapshot()
        store.create_run(snapshot)
        event = snapshot.trace.events[0]
        commit = TransitionCommit(
            transition_id=event.event_id,
            run=snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING}),
            tasks=snapshot.tasks,
            task_results=(),
            trace_events=(event,),
        )
        store.acquire_writer("run-test")
        try:
            revision = store.commit_transition("run-test", commit)
            again = store.commit_transition("run-test", commit)
        finally:
            store.release_writer("run-test")
        self.assertEqual(revision, again)
        self.assertEqual(store.load_snapshot("run-test").revision, 1)

    def test_writer_conflict(self) -> None:
        store = InMemoryExecutionStore()
        store.acquire_writer("run-1")
        with self.assertRaises(WriterConflictError):
            store.acquire_writer("run-1")
        store.release_writer("run-1")


class FileExecutionStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = FileExecutionStore(Path(self._tmpdir.name) / "runs")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_load_round_trip(self) -> None:
        snapshot = _sample_snapshot("run-file-1")
        self.store.create_run(snapshot)
        loaded = self.store.load_snapshot("run-file-1")
        self.assertEqual(loaded.run.run_id, "run-file-1")
        self.assertTrue((self.store.run_dir("run-file-1") / "run.json").is_file())
        self.assertTrue((self.store.run_dir("run-file-1") / "tasks.json").is_file())
        self.assertTrue((self.store.run_dir("run-file-1") / "artifacts.json").is_file())

    def test_commit_appends_trace_jsonl(self) -> None:
        snapshot = _sample_snapshot("run-file-2")
        self.store.create_run(snapshot)
        event = snapshot.trace.events[0]
        commit = TransitionCommit(
            transition_id=event.event_id,
            run=snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING}),
            tasks=snapshot.tasks,
            task_results=(),
            trace_events=(event,),
        )
        self.store.acquire_writer("run-file-2")
        try:
            self.store.commit_transition("run-file-2", commit)
        finally:
            self.store.release_writer("run-file-2")
        records = read_jsonl(self.store.run_dir("run-file-2") / "trace.jsonl")
        self.assertGreaterEqual(len(records), 1)

    def test_partial_jsonl_tail_ignored(self) -> None:
        snapshot = _sample_snapshot("run-file-3")
        self.store.create_run(snapshot)
        trace_path = self.store.run_dir("run-file-3") / "trace.jsonl"
        valid_event = snapshot.trace.events[0].model_dump(mode="json")
        import json

        trace_path.write_text(
            json.dumps(valid_event) + "\n" + '{"partial":',
            encoding="utf-8",
        )
        loaded = self.store.load_snapshot("run-file-3")
        self.assertIsNotNone(loaded.run.run_id)

    def test_stale_temp_cleaned_on_load(self) -> None:
        snapshot = _sample_snapshot("run-file-4")
        self.store.create_run(snapshot)
        stale = self.store.run_dir("run-file-4") / "tasks.json.tmp"
        stale.write_text("{}", encoding="utf-8")
        self.store.load_snapshot("run-file-4")
        self.assertFalse(stale.exists())

    def test_incompatible_schema_rejected(self) -> None:
        snapshot = _sample_snapshot("run-file-5")
        self.store.create_run(snapshot)
        run_json = self.store.run_dir("run-file-5") / "run.json"
        payload = json.loads(run_json.read_text(encoding="utf-8"))
        payload["schema_version"] = "99.0"
        atomic_write_json(run_json, payload)
        with self.assertRaises(IncompatibleSchemaError):
            self.store.load_snapshot("run-file-5")

    def test_corrupt_snapshot_rejected(self) -> None:
        snapshot = _sample_snapshot("run-file-6")
        self.store.create_run(snapshot)
        tasks_json = self.store.run_dir("run-file-6") / "tasks.json"
        tasks_json.write_text("{not json", encoding="utf-8")
        with self.assertRaises(CorruptSnapshotError):
            self.store.load_snapshot("run-file-6")

    def test_run_not_found(self) -> None:
        with self.assertRaises(RunNotFoundError):
            self.store.load_snapshot("missing-run")

    def test_path_traversal_run_id_rejected(self) -> None:
        with self.assertRaises(Exception):
            self.store.run_dir("../escape")

    def test_list_resumable_runs(self) -> None:
        snapshot = _sample_snapshot("run-resumable")
        running = snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING})
        self.store.create_run(
            RunSnapshot(
                run=running,
                tasks=snapshot.tasks,
                task_results=snapshot.task_results,
                trace=snapshot.trace,
                artifacts=snapshot.artifacts,
                report=None,
                revision=0,
                task_fingerprint=snapshot.task_fingerprint,
                graph_fingerprint=snapshot.graph_fingerprint,
            )
        )
        summaries = self.store.list_resumable_runs()
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].run_id, "run-resumable")

    def test_writer_lock_conflict(self) -> None:
        snapshot = _sample_snapshot("run-lock")
        self.store.create_run(snapshot)
        self.store.acquire_writer("run-lock")
        with self.assertRaises(WriterConflictError):
            self.store.acquire_writer("run-lock")
        self.store.release_writer("run-lock")

    def test_stale_lock_recoverable(self) -> None:
        run_dir = self.store.run_dir("run-stale-lock")
        run_dir.mkdir(parents=True)
        lock = RunWriterLock(run_dir)
        lock_path = run_dir / ".writer.lock"
        lock_path.write_text(
            json.dumps({"pid": 999999999, "acquired_at": "2020-01-01T00:00:00+00:00"}) + "\n",
            encoding="utf-8",
        )
        self.assertTrue(lock.recover_stale())

    def test_mixed_revision_rejected(self) -> None:
        snapshot = _sample_snapshot("run-mixed")
        self.store.create_run(snapshot)
        run_dir = self.store.run_dir("run-mixed")
        envelope = json.loads((run_dir / RUN_JSON).read_text(encoding="utf-8"))
        tasks_payload = json.loads((run_dir / TASKS_JSON).read_text(encoding="utf-8"))
        tasks_payload["revision"] = int(envelope["revision"]) + 1
        atomic_write_json(run_dir / TASKS_JSON, tasks_payload)
        with self.assertRaises(MixedRevisionSnapshotError):
            self.store.load_snapshot("run-mixed")

    def test_malformed_lock_not_removed_on_acquire(self) -> None:
        run_dir = self.store.run_dir("run-bad-lock")
        run_dir.mkdir(parents=True)
        lock_path = run_dir / ".writer.lock"
        lock_path.write_text("not-json", encoding="utf-8")
        lock = RunWriterLock(run_dir)
        with self.assertRaises(MalformedLockError):
            lock.acquire()

    def test_read_only_load_preserves_active_lock(self) -> None:
        snapshot = _sample_snapshot("run-active-lock")
        self.store.create_run(snapshot)
        self.store.acquire_writer("run-active-lock")
        run_dir = self.store.run_dir("run-active-lock")
        self.assertTrue((run_dir / ".writer.lock").is_file())
        other = FileExecutionStore(self.store.runs_root)
        other.load_snapshot("run-active-lock")
        self.assertTrue((run_dir / ".writer.lock").is_file())
        self.store.release_writer("run-active-lock")

    def test_two_store_instances_writer_conflict(self) -> None:
        snapshot = _sample_snapshot("run-two-stores")
        self.store.create_run(snapshot)
        other = FileExecutionStore(self.store.runs_root)
        self.store.acquire_writer("run-two-stores")
        with self.assertRaises(WriterConflictError):
            other.acquire_writer("run-two-stores")
        self.store.release_writer("run-two-stores")

    def test_foreign_live_lock_blocks_acquire(self) -> None:
        run_dir = self.store.run_dir("run-foreign-lock")
        run_dir.mkdir(parents=True)
        lock_path = run_dir / ".writer.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "owner_token": "foreign-token",
                    "pid": 424242,
                    "acquired_at": datetime.now(UTC).isoformat(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with mock.patch(
            "runtime.execution_store.locking._pid_is_running",
            return_value=True,
        ):
            with self.assertRaises(WriterConflictError):
                RunWriterLock(run_dir).acquire()

    def test_live_lock_does_not_expire_by_age(self) -> None:
        run_dir = self.store.run_dir("run-old-live-lock")
        run_dir.mkdir(parents=True)
        lock_path = run_dir / ".writer.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "owner_token": "long-running-owner",
                    "pid": 424242,
                    "acquired_at": "2020-01-01T00:00:00+00:00",
                    "host": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "")),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with mock.patch(
            "runtime.execution_store.locking._pid_is_running",
            return_value=True,
        ):
            self.assertFalse(RunWriterLock(run_dir).recover_stale())
            with self.assertRaises(WriterConflictError):
                RunWriterLock(run_dir).acquire()

    def test_commit_requires_writer_ownership(self) -> None:
        snapshot = _sample_snapshot("run-unowned")
        self.store.create_run(snapshot)
        event = snapshot.trace.events[0]
        commit = TransitionCommit(
            transition_id=event.event_id,
            run=snapshot.run,
            tasks=snapshot.tasks,
            task_results=(),
            trace_events=(event,),
        )
        with self.assertRaises(WriterConflictError):
            self.store.commit_transition("run-unowned", commit)

    def test_subprocess_writer_contention(self) -> None:
        snapshot = _sample_snapshot("run-process-lock")
        self.store.create_run(snapshot)
        run_dir = self.store.run_dir("run-process-lock")
        script = (
            "import sys,time; from pathlib import Path; "
            "from runtime.execution_store.locking import RunWriterLock; "
            "lock=RunWriterLock(Path(sys.argv[1])); lock.acquire(); "
            "print('locked', flush=True); time.sleep(3); lock.release()"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(run_dir)],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        )
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            with self.assertRaises(WriterConflictError):
                RunWriterLock(run_dir).acquire()
        finally:
            process.communicate(timeout=5)

    def test_journal_recovery_after_crash_before_snapshots(self) -> None:
        snapshot = _sample_snapshot("run-crash-1")
        self.store.create_run(snapshot)
        from execution.trace import ExecutionTraceBuilder
        from models.execution_engine import TraceEventType

        builder = ExecutionTraceBuilder(
            trace_id=snapshot.trace.trace_id,
            run_id="run-crash-1",
            graph_id=snapshot.run.graph_id,
            strategy_id=snapshot.run.strategy_id,
            created_at=snapshot.trace.created_at,
            initial_events=snapshot.trace.events,
        )
        new_event = builder.append(TraceEventType.RUN_STARTED, actor="scheduler")
        commit = TransitionCommit(
            transition_id=new_event.event_id,
            run=snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING}),
            tasks=snapshot.tasks,
            task_results=(),
            trace_events=(new_event,),
        )
        run_dir = self.store.run_dir("run-crash-1")
        record = TransitionJournalRecord(
            transition_id=commit.transition_id,
            run_id="run-crash-1",
            base_revision=0,
            target_revision=1,
            status=JournalStatus.JOURNAL_DURABLE,
            updated_snapshots=(),
            trace_events=commit.trace_events,
            run=commit.run,
            tasks=commit.tasks,
            task_results=commit.task_results,
            artifacts=(),
            report=None,
        )
        path = journal_path(run_dir, commit.transition_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_journal(path, record)
        from runtime.execution_store.atomic_io import append_jsonl_line

        for evt in commit.trace_events:
            append_jsonl_line(run_dir / "trace.jsonl", evt.model_dump(mode="json"))
        loaded = self.store.load_snapshot("run-crash-1")
        self.assertEqual(loaded.revision, 1)
        self.assertEqual(loaded.run.status, ExecutionRunStatus.RUNNING)
        self.assertFalse(path.is_file())

    def test_journal_recovery_idempotent(self) -> None:
        snapshot = _sample_snapshot("run-idempotent")
        self.store.create_run(snapshot)
        from execution.trace import ExecutionTraceBuilder
        from models.execution_engine import TraceEventType

        builder = ExecutionTraceBuilder(
            trace_id=snapshot.trace.trace_id,
            run_id="run-idempotent",
            graph_id=snapshot.run.graph_id,
            strategy_id=snapshot.run.strategy_id,
            created_at=snapshot.trace.created_at,
            initial_events=snapshot.trace.events,
        )
        new_event = builder.append(TraceEventType.RUN_STARTED, actor="scheduler")
        commit = TransitionCommit(
            transition_id=new_event.event_id,
            run=snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING}),
            tasks=snapshot.tasks,
            task_results=(),
            trace_events=(new_event,),
        )
        self.store.acquire_writer("run-idempotent")
        try:
            self.store.commit_transition("run-idempotent", commit)
            again = self.store.commit_transition("run-idempotent", commit)
        finally:
            self.store.release_writer("run-idempotent")
        loaded = self.store.load_snapshot("run-idempotent")
        self.assertEqual(loaded.revision, again)
        self.assertEqual(loaded.revision, 1)

    def test_journal_recovers_after_partial_snapshot_materialization(self) -> None:
        snapshot = _sample_snapshot("run-partial-materialization")
        self.store.create_run(snapshot)
        builder = ExecutionTraceBuilder(
            trace_id=snapshot.trace.trace_id,
            run_id=snapshot.run.run_id,
            graph_id=snapshot.run.graph_id,
            strategy_id=snapshot.run.strategy_id,
            created_at=snapshot.trace.created_at,
            initial_events=snapshot.trace.events,
        )
        event = builder.append(TraceEventType.RUN_STARTED, actor="scheduler")
        record = TransitionJournalRecord(
            transition_id=event.event_id,
            run_id=snapshot.run.run_id,
            base_revision=0,
            target_revision=1,
            status=JournalStatus.SNAPSHOTS_PARTIAL,
            updated_snapshots=(TASKS_JSON,),
            trace_events=(event,),
            run=snapshot.run.model_copy(update={"status": ExecutionRunStatus.RUNNING}),
            tasks=snapshot.tasks,
            task_results=(),
            artifacts=(),
            report=None,
        )
        run_dir = self.store.run_dir(snapshot.run.run_id)
        path = journal_path(run_dir, event.event_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_journal(path, record)
        # Simulate a crash after tasks.json reached target revision while
        # run.json and artifacts.json remain at the base revision.
        self.store._write_tasks_file(run_dir, record)
        loaded = FileExecutionStore(self.store.runs_root).load_snapshot(snapshot.run.run_id)
        self.assertEqual(loaded.revision, 1)
        self.assertEqual(loaded.run.status, ExecutionRunStatus.RUNNING)
        self.assertFalse(path.exists())
        for filename in (TASKS_JSON, "artifacts.json"):
            envelope = json.loads((run_dir / filename).read_text(encoding="utf-8"))
            self.assertEqual(envelope["revision"], 1)

    def test_corrupt_incomplete_journal_is_not_ignored(self) -> None:
        snapshot = _sample_snapshot("run-corrupt-journal")
        self.store.create_run(snapshot)
        journal_dir = self.store.run_dir(snapshot.run.run_id) / "journal"
        journal_dir.mkdir()
        (journal_dir / "broken.journal.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(CorruptSnapshotError):
            self.store.load_snapshot(snapshot.run.run_id)


if __name__ == "__main__":
    unittest.main()
    def test_atomic_replace_survives_reader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            atomic_write_json(path, {"value": 1})
            atomic_write_json(path, {"value": 2})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["value"], 2)


if __name__ == "__main__":
    unittest.main()
