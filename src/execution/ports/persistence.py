"""Execution-owned persistence port for durable run state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from models.execution_engine import (
    Artifact,
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTrace,
    TaskExecutionResult,
    TraceEvent,
)


@dataclass(frozen=True)
class ResumableRunSummary:
    """Lightweight listing entry for resumable runs."""

    run_id: str
    graph_id: str
    status: ExecutionRunStatus
    revision: int
    updated_at: datetime


@dataclass(frozen=True)
class RunSnapshot:
    """Consistent materialized view of one execution run."""

    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_results: tuple[TaskExecutionResult, ...]
    trace: ExecutionTrace
    artifacts: tuple[Artifact, ...]
    report: ExecutionReport | None
    revision: int
    task_fingerprint: str
    graph_fingerprint: str
    committed_transition_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TransitionCommit:
    """One logical scheduler transition to journal and snapshot."""

    transition_id: str
    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_results: tuple[TaskExecutionResult, ...]
    trace_events: tuple[TraceEvent, ...]
    artifacts: tuple[Artifact, ...] = ()
    report: ExecutionReport | None = None


class ExecutionPersistencePort(Protocol):
    """Domain persistence contract; implementations live in Runtime."""

    def create_run(self, snapshot: RunSnapshot) -> None:
        """Persist initial run state; reject if run_id already exists."""

    def load_snapshot(self, run_id: str) -> RunSnapshot:
        """Load a consistent snapshot, recovering from partial writes when safe."""

    def commit_transition(self, run_id: str, commit: TransitionCommit) -> int:
        """Journal trace events then atomically update snapshots; return new revision."""

    def save_report(self, run_id: str, report: ExecutionReport) -> None:
        """Persist or replace the latest execution report."""

    def list_resumable_runs(self) -> tuple[ResumableRunSummary, ...]:
        """Enumerate runs eligible for cross-process resume."""

    def acquire_writer(self, run_id: str) -> None:
        """Acquire exclusive writer ownership for a run."""

    def release_writer(self, run_id: str) -> None:
        """Release writer ownership acquired by this process."""
