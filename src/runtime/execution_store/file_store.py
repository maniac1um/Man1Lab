"""Workspace-scoped file execution store."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from execution.errors import (
    CorruptSnapshotError,
    IncompatibleSchemaError,
    InconsistentTraceError,
    InvalidTransitionCommitError,
    MixedRevisionSnapshotError,
    PersistenceIOError,
    RunExistsError,
    RunNotFoundError,
    WriterConflictError,
)
from execution.ports.persistence import (
    ResumableRunSummary,
    RunSnapshot,
    TransitionCommit,
)
from models.execution_engine import (
    SCHEMA_VERSION,
    Artifact,
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTrace,
    TaskExecutionResult,
    TraceEvent,
)
from runtime.execution_store.atomic_io import (
    append_jsonl_line,
    atomic_write_json,
    cleanup_stale_temps,
    load_json,
    read_jsonl,
)
from runtime.execution_store.journal import (
    JOURNAL_DIR,
    JournalStatus,
    SNAPSHOT_FILE_ORDER,
    TransitionJournalRecord,
    journal_path,
    list_incomplete_journals,
    remove_journal,
    write_journal,
)
from runtime.execution_store.locking import RunWriterLock
from runtime.execution_store.snapshot_meta import (
    unwrap_snapshot_payload,
    validate_snapshot_set,
    wrap_snapshot_payload,
)

RUN_JSON = "run.json"
TASKS_JSON = "tasks.json"
TRACE_JSONL = "trace.jsonl"
ARTIFACTS_JSON = "artifacts.json"
REPORT_JSON = "report.json"
LOGS_DIR = "logs"

_SUPPORTED_SCHEMA_MAJOR = 1


class FileExecutionStore:
    """Runtime-owned workspace filesystem adapter for execution runs."""

    def __init__(self, runs_root: Path) -> None:
        self._runs_root = runs_root
        self._active_locks: dict[str, RunWriterLock] = {}

    @property
    def runs_root(self) -> Path:
        return self._runs_root

    def run_dir(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self._runs_root / run_id

    def run_logs_dir(self, run_id: str) -> Path:
        """Return the runtime-owned log storage directory for one run."""
        return self.run_dir(run_id) / LOGS_DIR

    def attempt_logs_dir(self, run_id: str, attempt_id: str) -> Path:
        """Return the authorized directory for one attempt's stdout/stderr files."""
        self._validate_run_id(run_id)
        if not attempt_id or "/" in attempt_id or "\\" in attempt_id:
            raise ValueError(f"invalid attempt_id: {attempt_id!r}")
        logs_dir = self.run_logs_dir(run_id) / attempt_id
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def create_run(self, snapshot: RunSnapshot) -> None:
        run_dir = self.run_dir(snapshot.run.run_id)
        self._runs_root.mkdir(parents=True, exist_ok=True)
        try:
            run_dir.mkdir()
        except FileExistsError as exc:
            raise RunExistsError(f"run already exists: {snapshot.run.run_id}") from exc
        try:
            self._write_snapshot(run_dir, snapshot)
        except Exception:
            # Preserve the directory as evidence of an interrupted creation;
            # another creator must not silently claim the same run_id.
            raise

    def load_snapshot(self, run_id: str) -> RunSnapshot:
        run_dir = self.run_dir(run_id)
        if not run_dir.is_dir():
            raise RunNotFoundError(f"run not found: {run_id}")
        RunWriterLock(run_dir).recover_stale(read_only=True)
        journals = list_incomplete_journals(run_dir)
        if journals:
            temporary_lock: RunWriterLock | None = None
            if run_id not in self._active_locks:
                temporary_lock = RunWriterLock(run_dir)
                temporary_lock.acquire()
            try:
                self._recover_incomplete_journals(run_dir, run_id, journals)
            finally:
                if temporary_lock is not None:
                    temporary_lock.release()
        cleanup_stale_temps(run_dir)
        return self._load_raw_snapshot(run_dir, run_id)

    def commit_transition(self, run_id: str, commit: TransitionCommit) -> int:
        self._require_writer(run_id)
        if commit.run.run_id != run_id:
            raise InvalidTransitionCommitError("commit run_id mismatch")
        if not commit.trace_events:
            raise InvalidTransitionCommitError("commit requires trace events")
        run_dir = self.run_dir(run_id)
        snapshot = self.load_snapshot(run_id)
        if commit.transition_id in snapshot.committed_transition_ids:
            return snapshot.revision

        base_revision = snapshot.revision
        target_revision = base_revision + 1
        journal_record = TransitionJournalRecord(
            transition_id=commit.transition_id,
            run_id=run_id,
            base_revision=base_revision,
            target_revision=target_revision,
            status=JournalStatus.JOURNAL_DURABLE,
            updated_snapshots=(),
            trace_events=commit.trace_events,
            run=commit.run,
            tasks=commit.tasks,
            task_results=commit.task_results,
            artifacts=commit.artifacts or snapshot.artifacts,
            report=commit.report if commit.report is not None else snapshot.report,
        )
        journal_file = journal_path(run_dir, commit.transition_id)
        journal_file.parent.mkdir(parents=True, exist_ok=True)
        write_journal(journal_file, journal_record)

        existing_trace_ids = {item.get("event_id") for item in read_jsonl(run_dir / TRACE_JSONL)}
        for event in commit.trace_events:
            if event.event_id not in existing_trace_ids:
                append_jsonl_line(run_dir / TRACE_JSONL, event.model_dump(mode="json"))
                existing_trace_ids.add(event.event_id)

        updated_files: list[str] = []
        self._write_tasks_file(run_dir, journal_record)
        updated_files.append(TASKS_JSON)
        journal_record = replace(
            journal_record,
            status=JournalStatus.SNAPSHOTS_PARTIAL,
            updated_snapshots=tuple(updated_files),
        )
        write_journal(journal_file, journal_record)

        self._write_artifacts_file(run_dir, journal_record)
        updated_files.append(ARTIFACTS_JSON)
        journal_record = replace(
            journal_record,
            updated_snapshots=tuple(updated_files),
        )
        write_journal(journal_file, journal_record)

        if journal_record.report is not None:
            self._write_report_file(run_dir, journal_record)
            updated_files.append(REPORT_JSON)
            journal_record = replace(
                journal_record,
                updated_snapshots=tuple(updated_files),
            )
            write_journal(journal_file, journal_record)

        new_events = snapshot.trace.events + commit.trace_events
        new_trace = snapshot.trace.model_copy(
            update={
                "events": new_events,
                "updated_at": commit.trace_events[-1].recorded_at,
            }
        )
        new_committed = snapshot.committed_transition_ids | {commit.transition_id}
        committed_snapshot = replace(
            snapshot,
            run=commit.run,
            tasks=commit.tasks,
            task_results=commit.task_results,
            trace=new_trace,
            artifacts=journal_record.artifacts,
            report=journal_record.report,
            revision=target_revision,
            committed_transition_ids=new_committed,
        )
        self._write_run_envelope(run_dir, committed_snapshot)
        journal_record = replace(
            journal_record,
            status=JournalStatus.SNAPSHOTS_COMPLETE,
            updated_snapshots=tuple(updated_files),
        )
        write_journal(journal_file, journal_record)

        remove_journal(journal_file)
        return target_revision

    def save_report(self, run_id: str, report: ExecutionReport) -> None:
        self._require_writer(run_id)
        run_dir = self.run_dir(run_id)
        snapshot = self.load_snapshot(run_id)
        atomic_write_json(
            run_dir / REPORT_JSON,
            wrap_snapshot_payload(
                run_id=run_id,
                revision=snapshot.revision,
                payload=report.model_dump(mode="json"),
            ),
        )
        updated = replace(snapshot, report=report)
        self._write_run_envelope(run_dir, updated)

    def list_resumable_runs(self) -> tuple[ResumableRunSummary, ...]:
        if not self._runs_root.is_dir():
            return ()
        summaries: list[ResumableRunSummary] = []
        for child in sorted(self._runs_root.iterdir()):
            if not child.is_dir():
                continue
            run_json = child / RUN_JSON
            if not run_json.is_file():
                continue
            try:
                snapshot = self.load_snapshot(child.name)
            except (
                CorruptSnapshotError,
                IncompatibleSchemaError,
                InconsistentTraceError,
                MixedRevisionSnapshotError,
            ):
                continue
            if snapshot.run.status in {
                ExecutionRunStatus.RUNNING,
                ExecutionRunStatus.INTERRUPTED,
                ExecutionRunStatus.RECONCILIATION_REQUIRED,
                ExecutionRunStatus.PENDING,
            }:
                summaries.append(
                    ResumableRunSummary(
                        run_id=snapshot.run.run_id,
                        graph_id=snapshot.run.graph_id,
                        status=snapshot.run.status,
                        revision=snapshot.revision,
                        updated_at=snapshot.trace.updated_at,
                    )
                )
        return tuple(sorted(summaries, key=lambda item: item.updated_at, reverse=True))

    def acquire_writer(self, run_id: str) -> None:
        if run_id in self._active_locks:
            raise WriterConflictError(f"writer already held for run: {run_id}")
        run_dir = self.run_dir(run_id)
        lock = RunWriterLock(run_dir)
        lock.recover_stale()
        lock.acquire()
        self._active_locks[run_id] = lock

    def release_writer(self, run_id: str) -> None:
        lock = self._active_locks.pop(run_id, None)
        if lock is not None:
            lock.release()

    def release_all_writers(self) -> None:
        for run_id in list(self._active_locks):
            self.release_writer(run_id)

    def _load_raw_snapshot(self, run_dir: Path, run_id: str) -> RunSnapshot:
        envelope = load_json(run_dir / RUN_JSON)
        self._validate_schema(envelope)
        revision = int(envelope.get("revision", 0))
        task_fingerprint = str(envelope.get("task_fingerprint", ""))
        graph_fingerprint = str(envelope.get("graph_fingerprint", ""))
        committed_ids = frozenset(str(item) for item in envelope.get("committed_transition_ids", []))
        run = ExecutionRun.model_validate(envelope["run"])
        if run.run_id != run_id:
            raise InconsistentTraceError("run_id directory mismatch")

        file_revisions: dict[str, tuple[str, int]] = {}
        tasks_payload = load_json(run_dir / TASKS_JSON)
        tasks_run_id, tasks_revision, tasks_content = unwrap_snapshot_payload(
            tasks_payload, file_label=TASKS_JSON, expected_run_id=run_id, expected_revision=revision
        )
        file_revisions[TASKS_JSON] = (tasks_run_id, tasks_revision)
        tasks = tuple(ExecutionTask.model_validate(item) for item in tasks_content.get("tasks", []))
        task_results = tuple(
            TaskExecutionResult.model_validate(item) for item in tasks_content.get("task_results", [])
        )

        artifacts: tuple[Artifact, ...] = ()
        if (run_dir / ARTIFACTS_JSON).is_file():
            artifacts_payload = load_json(run_dir / ARTIFACTS_JSON)
            art_run_id, art_revision, art_content = unwrap_snapshot_payload(
                artifacts_payload,
                file_label=ARTIFACTS_JSON,
                expected_run_id=run_id,
                expected_revision=revision,
            )
            file_revisions[ARTIFACTS_JSON] = (art_run_id, art_revision)
            artifacts = tuple(
                Artifact.model_validate(item) for item in art_content.get("artifacts", [])
            )
        else:
            file_revisions[ARTIFACTS_JSON] = (run_id, revision)

        report = None
        if (run_dir / REPORT_JSON).is_file():
            report_payload = load_json(run_dir / REPORT_JSON)
            rep_run_id, rep_revision, rep_content = unwrap_snapshot_payload(
                report_payload,
                file_label=REPORT_JSON,
                expected_run_id=run_id,
                expected_revision=revision,
            )
            file_revisions[REPORT_JSON] = (rep_run_id, rep_revision)
            report = ExecutionReport.model_validate(rep_content)
        else:
            file_revisions[REPORT_JSON] = (run_id, revision)

        validate_snapshot_set(run_id=run_id, revision=revision, file_revisions=file_revisions)

        trace_records = read_jsonl(run_dir / TRACE_JSONL)
        trace_events = tuple(TraceEvent.model_validate(item) for item in trace_records)
        trace = ExecutionTrace.model_validate(
            {
                "trace_id": run.trace_id,
                "run_id": run_id,
                "graph_id": run.graph_id,
                "strategy_id": run.strategy_id,
                "created_at": envelope.get("trace_created_at", run.created_at.isoformat()),
                "updated_at": (
                    trace_events[-1].recorded_at.isoformat()
                    if trace_events
                    else envelope.get("trace_updated_at", run.created_at.isoformat())
                ),
                "events": [event.model_dump(mode="json") for event in trace_events],
            }
        )
        return RunSnapshot(
            run=run,
            tasks=tasks,
            task_results=task_results,
            trace=trace,
            artifacts=artifacts,
            report=report,
            revision=revision,
            task_fingerprint=task_fingerprint,
            graph_fingerprint=graph_fingerprint,
            committed_transition_ids=committed_ids,
        )

    def _recover_incomplete_journals(
        self,
        run_dir: Path,
        run_id: str,
        journals: list[TransitionJournalRecord],
    ) -> None:
        envelope = load_json(run_dir / RUN_JSON)
        self._validate_schema(envelope)
        current_revision = int(envelope.get("revision", 0))
        committed_ids = set(str(item) for item in envelope.get("committed_transition_ids", []))
        for record in sorted(journals, key=lambda item: item.target_revision):
            if record.run_id != run_id or record.run.run_id != run_id:
                raise CorruptSnapshotError("journal run_id mismatch")
            if record.target_revision != record.base_revision + 1:
                raise CorruptSnapshotError("journal revision must advance by one")
            if record.transition_id in committed_ids and record.target_revision <= current_revision:
                remove_journal(journal_path(run_dir, record.transition_id))
                continue
            if record.base_revision != current_revision:
                raise MixedRevisionSnapshotError(
                    f"journal base revision {record.base_revision} does not match committed revision "
                    f"{current_revision}"
                )
            self._replay_journal(run_dir, envelope, committed_ids, record)
            current_revision = record.target_revision
            committed_ids.add(record.transition_id)
            envelope = load_json(run_dir / RUN_JSON)

    def _replay_journal(
        self,
        run_dir: Path,
        envelope: dict,
        committed_ids: set[str],
        record: TransitionJournalRecord,
    ) -> None:
        path = journal_path(run_dir, record.transition_id)
        # The journal is the authoritative target image. Re-materialize every
        # target file unconditionally; atomic replacement makes replay
        # idempotent even when the recorded progress lagged the filesystem.
        self._write_tasks_file(run_dir, record)
        self._write_artifacts_file(run_dir, record)
        if record.report is not None:
            self._write_report_file(run_dir, record)
        elif (run_dir / REPORT_JSON).is_file():
            (run_dir / REPORT_JSON).unlink()

        trace_records = read_jsonl(run_dir / TRACE_JSONL)
        existing_ids = {item.get("event_id") for item in trace_records}
        for event in record.trace_events:
            if event.event_id not in existing_ids:
                append_jsonl_line(run_dir / TRACE_JSONL, event.model_dump(mode="json"))

        trace_records = read_jsonl(run_dir / TRACE_JSONL)
        trace_events = tuple(TraceEvent.model_validate(item) for item in trace_records)
        trace = ExecutionTrace.model_validate(
            {
                "trace_id": record.run.trace_id,
                "run_id": record.run_id,
                "graph_id": record.run.graph_id,
                "strategy_id": record.run.strategy_id,
                "created_at": envelope.get("trace_created_at", record.run.created_at.isoformat()),
                "updated_at": (
                    trace_events[-1].recorded_at.isoformat()
                    if trace_events
                    else envelope.get("trace_updated_at", record.run.created_at.isoformat())
                ),
                "events": [event.model_dump(mode="json") for event in trace_events],
            }
        )
        committed = RunSnapshot(
            run=record.run,
            tasks=record.tasks,
            task_results=record.task_results,
            trace=trace,
            artifacts=record.artifacts,
            report=record.report,
            revision=record.target_revision,
            task_fingerprint=str(envelope.get("task_fingerprint", "")),
            graph_fingerprint=str(envelope.get("graph_fingerprint", "")),
            committed_transition_ids=frozenset(committed_ids | {record.transition_id}),
        )
        self._write_run_envelope(run_dir, committed)
        remove_journal(path)

    def _require_writer(self, run_id: str) -> None:
        if run_id not in self._active_locks:
            raise WriterConflictError(f"writer ownership required for run: {run_id}")

    def _write_snapshot(self, run_dir: Path, snapshot: RunSnapshot) -> None:
        record = TransitionJournalRecord(
            transition_id="__initial__",
            run_id=snapshot.run.run_id,
            base_revision=0,
            target_revision=snapshot.revision,
            status=JournalStatus.COMMITTED,
            updated_snapshots=SNAPSHOT_FILE_ORDER,
            trace_events=snapshot.trace.events,
            run=snapshot.run,
            tasks=snapshot.tasks,
            task_results=snapshot.task_results,
            artifacts=snapshot.artifacts,
            report=snapshot.report,
        )
        self._write_tasks_file(run_dir, record)
        self._write_artifacts_file(run_dir, record)
        if snapshot.report is not None:
            self._write_report_file(run_dir, record)
        self._write_run_envelope(run_dir, snapshot)
        trace_path = run_dir / TRACE_JSONL
        if not trace_path.is_file() and snapshot.trace.events:
            for event in snapshot.trace.events:
                append_jsonl_line(trace_path, event.model_dump(mode="json"))

    def _write_tasks_file(self, run_dir: Path, record: TransitionJournalRecord) -> None:
        atomic_write_json(
            run_dir / TASKS_JSON,
            wrap_snapshot_payload(
                run_id=record.run_id,
                revision=record.target_revision,
                payload={
                    "tasks": [task.model_dump(mode="json") for task in record.tasks],
                    "task_results": [result.model_dump(mode="json") for result in record.task_results],
                },
            ),
        )

    def _write_artifacts_file(self, run_dir: Path, record: TransitionJournalRecord) -> None:
        atomic_write_json(
            run_dir / ARTIFACTS_JSON,
            wrap_snapshot_payload(
                run_id=record.run_id,
                revision=record.target_revision,
                payload={
                    "artifacts": [artifact.model_dump(mode="json") for artifact in record.artifacts],
                },
            ),
        )

    def _write_report_file(self, run_dir: Path, record: TransitionJournalRecord) -> None:
        if record.report is None:
            return
        atomic_write_json(
            run_dir / REPORT_JSON,
            wrap_snapshot_payload(
                run_id=record.run_id,
                revision=record.target_revision,
                payload=record.report.model_dump(mode="json"),
            ),
        )

    def _write_run_envelope(self, run_dir: Path, snapshot: RunSnapshot) -> None:
        atomic_write_json(
            run_dir / RUN_JSON,
            {
                "schema_version": SCHEMA_VERSION,
                "revision": snapshot.revision,
                "task_fingerprint": snapshot.task_fingerprint,
                "graph_fingerprint": snapshot.graph_fingerprint,
                "committed_transition_ids": sorted(snapshot.committed_transition_ids),
                "trace_created_at": snapshot.trace.created_at.isoformat(),
                "trace_updated_at": snapshot.trace.updated_at.isoformat(),
                "run": snapshot.run.model_dump(mode="json"),
            },
        )

    def _validate_schema(self, envelope: dict) -> None:
        version = str(envelope.get("schema_version", ""))
        if not version:
            raise IncompatibleSchemaError("missing schema_version")
        try:
            major = int(version.split(".", 1)[0])
        except ValueError as exc:
            raise IncompatibleSchemaError(f"invalid schema_version: {version}") from exc
        if major > _SUPPORTED_SCHEMA_MAJOR:
            raise IncompatibleSchemaError(f"unsupported schema_version: {version}")

    def _validate_run_id(self, run_id: str) -> None:
        if not run_id or run_id in {".", ".."}:
            raise PersistenceIOError("invalid run_id")
        if "/" in run_id or "\\" in run_id or ".." in run_id:
            raise PersistenceIOError("run_id must not contain path separators")
