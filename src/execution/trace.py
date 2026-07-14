"""Append-only execution trace construction."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from models.execution_engine import ExecutionTrace, TraceEvent, TraceEventType


def validate_trace_events(*, run_id: str, events: tuple[TraceEvent, ...]) -> None:
    """Reject invalid trace history; do not repair it."""
    event_ids: set[str] = set()
    sequences: set[int] = set()
    last_sequence = -1
    started_attempts: set[tuple[str, str]] = set()

    for event in events:
        if event.run_id != run_id:
            raise ValueError("trace event run_id must match trace run_id")
        if event.event_id in event_ids:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        if event.causation_event_id and event.causation_event_id not in event_ids:
            raise ValueError("causation_event_id must reference an earlier event")
        event_ids.add(event.event_id)
        if event.sequence in sequences:
            raise ValueError(f"duplicate sequence: {event.sequence}")
        sequences.add(event.sequence)
        if event.sequence <= last_sequence:
            raise ValueError("trace events must have strictly increasing sequence")
        last_sequence = event.sequence
        if event.recorded_at.tzinfo is None:
            raise ValueError("trace event recorded_at must be timezone-aware")
        if event.event_type == TraceEventType.TASK_STARTED and event.task_id and event.attempt_id:
            started_attempts.add((event.task_id, event.attempt_id))
        if event.event_type in {TraceEventType.TASK_COMPLETED, TraceEventType.TASK_FAILED}:
            key = (event.task_id, event.attempt_id)
            if key not in started_attempts:
                raise ValueError(f"{event.event_type.value} without prior TaskStarted")


class ExecutionTraceBuilder:
    """Mutable builder that emits immutable trace snapshots."""

    def __init__(
        self,
        *,
        trace_id: str,
        run_id: str,
        graph_id: str = "",
        strategy_id: str = "",
        created_at: datetime | None = None,
        initial_events: tuple[TraceEvent, ...] = (),
    ) -> None:
        self._trace_id = trace_id
        self._run_id = run_id
        self._graph_id = graph_id
        self._strategy_id = strategy_id
        self._created_at = created_at or datetime.now(UTC)
        if self._created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        validate_trace_events(run_id=run_id, events=initial_events)
        self._events: list[TraceEvent] = list(initial_events)
        self._sequence = max((event.sequence for event in initial_events), default=-1) + 1
        self._event_ids = {event.event_id for event in initial_events}

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

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
        proposed_id = event_id or f"evt-{uuid4()}"
        if proposed_id in self._event_ids:
            raise ValueError(f"duplicate event_id: {proposed_id}")
        event = TraceEvent(
            event_id=proposed_id,
            event_type=event_type,
            run_id=self._run_id,
            sequence=self._sequence,
            recorded_at=recorded_at or datetime.now(UTC),
            task_id=task_id,
            attempt_id=attempt_id,
            actor=actor,
            payload=payload or {},
            causation_event_id=causation_event_id,
        )
        self._events.append(event)
        self._event_ids.add(proposed_id)
        self._sequence += 1
        return event

    def build(self) -> ExecutionTrace:
        validate_trace_events(run_id=self._run_id, events=tuple(self._events))
        updated_at = self._events[-1].recorded_at if self._events else self._created_at
        return ExecutionTrace(
            trace_id=self._trace_id,
            run_id=self._run_id,
            graph_id=self._graph_id,
            strategy_id=self._strategy_id,
            created_at=self._created_at,
            updated_at=updated_at,
            events=tuple(self._events),
        )

