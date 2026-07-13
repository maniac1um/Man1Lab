"""In-memory execution store for unit tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from execution.errors import (
    InvalidTransitionCommitError,
    RunExistsError,
    RunNotFoundError,
    WriterConflictError,
)
from execution.ports.persistence import (
    ResumableRunSummary,
    RunSnapshot,
    TransitionCommit,
)
from models.execution_engine import ExecutionReport, ExecutionRunStatus


class InMemoryExecutionStore:
    """Process-local execution store without filesystem side effects."""

    def __init__(self) -> None:
        self._snapshots: dict[str, RunSnapshot] = {}
        self._writers: dict[str, int] = {}
        self._writer_token = 0

    def create_run(self, snapshot: RunSnapshot) -> None:
        if snapshot.run.run_id in self._snapshots:
            raise RunExistsError(f"run already exists: {snapshot.run.run_id}")
        self._snapshots[snapshot.run.run_id] = snapshot

    def load_snapshot(self, run_id: str) -> RunSnapshot:
        snapshot = self._snapshots.get(run_id)
        if snapshot is None:
            raise RunNotFoundError(f"run not found: {run_id}")
        return snapshot

    def commit_transition(self, run_id: str, commit: TransitionCommit) -> int:
        self._require_writer(run_id)
        snapshot = self.load_snapshot(run_id)
        if commit.transition_id in snapshot.committed_transition_ids:
            return snapshot.revision
        if commit.run.run_id != run_id:
            raise InvalidTransitionCommitError("commit run_id mismatch")
        if not commit.trace_events:
            raise InvalidTransitionCommitError("commit requires trace events")
        new_events = snapshot.trace.events + commit.trace_events
        new_trace = snapshot.trace.model_copy(
            update={
                "events": new_events,
                "updated_at": commit.trace_events[-1].recorded_at,
            }
        )
        new_revision = snapshot.revision + 1
        new_committed = snapshot.committed_transition_ids | {commit.transition_id}
        updated = replace(
            snapshot,
            run=commit.run,
            tasks=commit.tasks,
            task_results=commit.task_results,
            trace=new_trace,
            artifacts=commit.artifacts or snapshot.artifacts,
            report=commit.report if commit.report is not None else snapshot.report,
            revision=new_revision,
            committed_transition_ids=new_committed,
        )
        self._snapshots[run_id] = updated
        return new_revision

    def save_report(self, run_id: str, report: ExecutionReport) -> None:
        self._require_writer(run_id)
        snapshot = self.load_snapshot(run_id)
        self._snapshots[run_id] = replace(snapshot, report=report)

    def list_resumable_runs(self) -> tuple[ResumableRunSummary, ...]:
        summaries: list[ResumableRunSummary] = []
        for snapshot in self._snapshots.values():
            if snapshot.run.status in {
                ExecutionRunStatus.RUNNING,
                ExecutionRunStatus.INTERRUPTED,
                ExecutionRunStatus.RECONCILIATION_REQUIRED,
                ExecutionRunStatus.PENDING,
            }:
                updated_at = snapshot.trace.updated_at
                summaries.append(
                    ResumableRunSummary(
                        run_id=snapshot.run.run_id,
                        graph_id=snapshot.run.graph_id,
                        status=snapshot.run.status,
                        revision=snapshot.revision,
                        updated_at=updated_at,
                    )
                )
        return tuple(sorted(summaries, key=lambda item: item.updated_at, reverse=True))

    def acquire_writer(self, run_id: str) -> None:
        if run_id in self._writers:
            raise WriterConflictError(f"writer already held for run: {run_id}")
        self._writer_token += 1
        self._writers[run_id] = self._writer_token

    def release_writer(self, run_id: str) -> None:
        self._writers.pop(run_id, None)

    def _require_writer(self, run_id: str) -> None:
        if run_id not in self._writers:
            raise WriterConflictError(f"writer ownership required for run: {run_id}")
