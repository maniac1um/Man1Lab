"""Bridge scheduler transitions to the persistence port."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from execution.ports.persistence import ExecutionPersistencePort, TransitionCommit
from execution.trace import ExecutionTraceBuilder
from models.execution_engine import (
    Artifact,
    ExecutionReport,
    ExecutionRun,
    ExecutionTask,
    TaskExecutionResult,
    TraceEvent,
    TraceEventType,
)


@dataclass
class SchedulerRunState:
    """Mutable scheduler state referenced during durable commits."""

    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_map: dict[str, ExecutionTask]
    results: dict[str, TaskExecutionResult]


class TransitionCommitter:
    """Commits durable state after each scheduler trace append."""

    def __init__(
        self,
        *,
        store: ExecutionPersistencePort,
        run_id: str,
        artifact_supplier: Callable[[], tuple[Artifact, ...]] | None = None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._artifact_supplier = artifact_supplier
        self._pending_events: list[TraceEvent] = []

    def stage_event(self, event: TraceEvent) -> None:
        self._pending_events.append(event)

    def commit(
        self,
        *,
        run: ExecutionRun,
        tasks: tuple[ExecutionTask, ...],
        task_results: dict[str, TaskExecutionResult],
        report: ExecutionReport | None = None,
    ) -> None:
        if not self._pending_events:
            return
        transition_id = self._pending_events[-1].event_id
        artifacts = self._artifact_supplier() if self._artifact_supplier else ()
        commit = TransitionCommit(
            transition_id=transition_id,
            run=run,
            tasks=tasks,
            task_results=tuple(task_results[task.id] for task in tasks if task.id in task_results),
            trace_events=tuple(self._pending_events),
            artifacts=artifacts,
            report=report,
        )
        self._store.commit_transition(self._run_id, commit)
        self._pending_events.clear()


class PersistingTraceBuilder:
    """Wraps ExecutionTraceBuilder to commit after each append."""

    def __init__(
        self,
        inner: ExecutionTraceBuilder,
        *,
        committer: TransitionCommitter,
        run_state: SchedulerRunState,
    ) -> None:
        self._inner = inner
        self._committer = committer
        self._run_state = run_state

    @property
    def trace_id(self) -> str:
        return self._inner.trace_id

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return self._inner.events

    def append(
        self,
        event_type: TraceEventType,
        *,
        task_id: str = "",
        attempt_id: str = "",
        actor: str = "scheduler",
        payload: dict[str, str] | None = None,
        causation_event_id: str = "",
        recorded_at: datetime | None = None,
        event_id: str | None = None,
    ) -> TraceEvent:
        event = self._inner.append(
            event_type,
            task_id=task_id,
            attempt_id=attempt_id,
            actor=actor,
            payload=payload,
            causation_event_id=causation_event_id,
            recorded_at=recorded_at,
            event_id=event_id,
        )
        self._committer.stage_event(event)
        self._committer.commit(
            run=self._run_state.run,
            tasks=tuple(self._run_state.task_map[task.id] for task in self._run_state.tasks),
            task_results=self._run_state.results,
        )
        return event

    def build(self):
        return self._inner.build()


def wrap_trace_builder(
    trace_builder: ExecutionTraceBuilder,
    *,
    committer: TransitionCommitter | None,
    run_state: SchedulerRunState,
) -> ExecutionTraceBuilder | PersistingTraceBuilder:
    if committer is None:
        return trace_builder
    return PersistingTraceBuilder(trace_builder, committer=committer, run_state=run_state)
