"""Canonical execution engine models (v1.3 foundation).

Legacy local command results remain in ``models.execution.ExecutionResult``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "1.0"
DECOMPOSITION_VERSION = "1.0"

MAX_METADATA_ENTRIES = 64
MAX_METADATA_KEY_LEN = 128
MAX_METADATA_VALUE_LEN = 1024
MAX_ERRORS = 32
MAX_METRICS = 64
MAX_LOG_REFS = 16
MAX_TRACE_EVENTS = 10_000


_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)


def _is_secret_like_key(key: str) -> bool:
    normalized = key.replace("-", "_").replace(" ", "_")
    return bool(_SECRET_KEY_PATTERN.search(normalized))


def _reject_secret_metadata_keys(metadata: dict[str, str]) -> dict[str, str]:
    for key in metadata:
        if _is_secret_like_key(key):
            raise ValueError(f"secret-like metadata key not allowed: {key}")
    return metadata


def _validate_bounded_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    if len(metadata) > MAX_METADATA_ENTRIES:
        raise ValueError(f"metadata exceeds {MAX_METADATA_ENTRIES} entries")
    for key, value in metadata.items():
        if len(key) > MAX_METADATA_KEY_LEN:
            raise ValueError(f"metadata key exceeds {MAX_METADATA_KEY_LEN} characters")
        if isinstance(value, str) and len(value) > MAX_METADATA_VALUE_LEN:
            raise ValueError(f"metadata value for {key!r} exceeds {MAX_METADATA_VALUE_LEN} characters")
    if all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()):
        _reject_secret_metadata_keys(metadata)  # type: ignore[arg-type]
    return metadata


def _require_utc(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
        raise ValueError("datetime must use UTC")
    return value


class ExecutionTaskType(str, Enum):
    REPOSITORY = "repository"
    ENVIRONMENT = "environment"
    DATASET = "dataset"
    CHECKPOINT = "checkpoint"
    CONFIGURATION = "configuration"
    TRAINING = "training"
    EVALUATION = "evaluation"
    REPORT = "report"


class ExecutionTaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


_TERMINAL_TASK_STATUSES = frozenset(
    {
        ExecutionTaskStatus.SUCCESS,
        ExecutionTaskStatus.FAILED,
        ExecutionTaskStatus.SKIPPED,
        ExecutionTaskStatus.CANCELLED,
    }
)


class ExecutionRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class ReconciliationState(str, Enum):
    STILL_RUNNING = "still_running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOST = "lost"
    UNKNOWN = "unknown"


class TraceEventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_READY = "task_ready"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_BLOCKED = "task_blocked"
    TASK_SKIPPED = "task_skipped"
    TASK_CANCELLED = "task_cancelled"
    ARTIFACT_REGISTERED = "artifact_registered"
    ARTIFACT_INVALIDATED = "artifact_invalidated"
    RUN_STARTED = "run_started"
    RUN_INTERRUPTED = "run_interrupted"
    RUN_RESUMED = "run_resumed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"


class ArtifactValidationState(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"


class ArtifactScope(str, Enum):
    REPOSITORY = "repository"
    RUNTIME_RUN = "runtime_run"
    EXTERNAL = "external"


class ExecutionArtifactReference(BaseModel):
    """Declared input or resolved artifact reference for a task."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = ""
    logical_name: str
    artifact_type: str
    required: bool = True
    role: str = ""
    location_ref: str = ""
    integrity_hint: str = ""


class OutputDeclaration(BaseModel):
    """Declared output expectation for a task."""

    model_config = ConfigDict(frozen=True)

    logical_name: str
    artifact_type: str
    required: bool = True
    scope: ArtifactScope = ArtifactScope.RUNTIME_RUN
    validation_rule: str = "presence"
    integrity_hint: str = ""


class ExecutionError(BaseModel):
    """Structured execution failure record."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    phase: str = ""
    retryable: bool = False
    causal_task_id: str = ""
    causal_attempt_id: str = ""
    causal_artifact_id: str = ""
    backend_details: dict[str, str] = Field(default_factory=dict)

    @field_validator("backend_details")
    @classmethod
    def _bounded_backend_details(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]


class ReconciliationResult(BaseModel):
    """Outcome of reconciling one indeterminate RUNNING attempt."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    task_id: str
    attempt_id: str
    backend_operation_ref: str = ""
    reconciled_state: ReconciliationState
    outcome_ref: str = ""
    error: ExecutionError | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _utc_recorded_at(cls, value: datetime) -> datetime:
        result = _require_utc(value)
        assert result is not None
        return result


class MetricIdentity(BaseModel):
    """Stable metric identity for report aggregation."""

    model_config = ConfigDict(frozen=True)

    name: str
    unit: str = ""
    split: str = ""

    def identity_key(self) -> str:
        return f"{self.name}|{self.unit}|{self.split}"


class Metric(BaseModel):

    model_config = ConfigDict(frozen=True)

    name: str
    value: float
    unit: str = ""
    step: int | None = None
    epoch: int | None = None
    split: str = ""
    recorded_at: datetime | None = None
    source_artifact_id: str = ""

    @field_validator("recorded_at")
    @classmethod
    def _utc_recorded_at(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)


class LogReference(BaseModel):
    """Bounded log descriptor."""

    model_config = ConfigDict(frozen=True)

    log_id: str
    stream: str = ""
    category: str = ""
    location_ref: str = ""
    size_bytes: int | None = None
    recorded_at: datetime | None = None
    excerpt: str = ""

    @field_validator("excerpt")
    @classmethod
    def _bounded_excerpt(cls, value: str) -> str:
        if len(value) > MAX_METADATA_VALUE_LEN:
            raise ValueError(f"excerpt exceeds {MAX_METADATA_VALUE_LEN} characters")
        return value

    @field_validator("recorded_at")
    @classmethod
    def _utc_recorded_at(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)


class Attempt(BaseModel):
    """One dispatch attempt for a task."""

    model_config = ConfigDict(frozen=True)

    attempt_id: str
    task_id: str
    backend_kind: str = "fake"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    termination_reason: str = ""
    backend_operation_ref: str = ""

    @field_validator("started_at", "completed_at")
    @classmethod
    def _utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)

    @model_validator(mode="after")
    def _validate_attempt(self) -> Attempt:
        if not self.attempt_id:
            raise ValueError("attempt_id must be non-empty")
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not precede started_at")
        return self


class Artifact(BaseModel):
    """Registered artifact metadata."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    logical_name: str
    artifact_type: str
    producer_run_id: str
    producer_task_id: str
    producer_attempt_id: str = ""
    scope: ArtifactScope = ArtifactScope.RUNTIME_RUN
    location_ref: str = ""
    size_bytes: int | None = None
    integrity_digest: str = ""
    created_at: datetime | None = None
    validation_state: ArtifactValidationState = ArtifactValidationState.PENDING
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]


class TaskResultSummary(BaseModel):
    """Backend-neutral completion evidence."""

    model_config = ConfigDict(frozen=True)

    termination_reason: str
    exit_code: int | None = None
    backend_operation_ref: str = ""
    output_summary: str = ""
    cancelled: bool = False
    timed_out: bool = False


class TaskExecutionResult(BaseModel):
    """Canonical immutable outcome for one task after terminal scheduling."""

    model_config = ConfigDict(frozen=True)

    result_id: str
    run_id: str
    task_id: str
    status: ExecutionTaskStatus
    attempts: tuple[Attempt, ...] = Field(default_factory=tuple)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    backend_kind: str = ""
    task_result: TaskResultSummary | None = None
    logs: tuple[LogReference, ...] = Field(default_factory=tuple)
    artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    errors: tuple[ExecutionError, ...] = Field(default_factory=tuple)
    metrics: tuple[Metric, ...] = Field(default_factory=tuple)
    metadata: dict[str, str] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]

    @field_validator("errors")
    @classmethod
    def _bounded_errors(cls, value: tuple[ExecutionError, ...]) -> tuple[ExecutionError, ...]:
        if len(value) > MAX_ERRORS:
            raise ValueError(f"errors exceeds {MAX_ERRORS} entries")
        return value

    @field_validator("metrics")
    @classmethod
    def _bounded_metrics(cls, value: tuple[Metric, ...]) -> tuple[Metric, ...]:
        if len(value) > MAX_METRICS:
            raise ValueError(f"metrics exceeds {MAX_METRICS} entries")
        return value

    @field_validator("logs")
    @classmethod
    def _bounded_logs(cls, value: tuple[LogReference, ...]) -> tuple[LogReference, ...]:
        if len(value) > MAX_LOG_REFS:
            raise ValueError(f"logs exceeds {MAX_LOG_REFS} entries")
        return value

    @field_validator("started_at", "completed_at")
    @classmethod
    def _utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)

    @model_validator(mode="after")
    def _validate_result_semantics(self) -> TaskExecutionResult:
        if not self.result_id:
            raise ValueError("result_id must be non-empty")
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        attempt_ids: set[str] = set()
        for attempt in self.attempts:
            if attempt.task_id != self.task_id:
                raise ValueError("attempt task_id must match result task_id")
            if attempt.attempt_id in attempt_ids:
                raise ValueError(f"duplicate attempt_id: {attempt.attempt_id}")
            attempt_ids.add(attempt.attempt_id)
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not precede started_at")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if self.status == ExecutionTaskStatus.SUCCESS:
            if self.task_result is None:
                raise ValueError("SUCCESS result requires task_result evidence")
            if not self.attempts:
                raise ValueError("SUCCESS result requires at least one attempt")
        elif self.status == ExecutionTaskStatus.FAILED:
            if not self.errors:
                raise ValueError("FAILED result requires at least one structured error")
        elif self.status == ExecutionTaskStatus.CANCELLED:
            if self.task_result is None and not self.errors:
                raise ValueError("CANCELLED result requires task_result or errors")
        elif self.status == ExecutionTaskStatus.RUNNING:
            if not self.attempts:
                raise ValueError("RUNNING result requires at least one attempt")
        return self


class ExecutionTask(BaseModel):
    """Canonical backend-neutral scheduling unit."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    type: ExecutionTaskType
    description: str = ""
    dependencies: tuple[str, ...] = Field(default_factory=tuple)
    inputs: tuple[ExecutionArtifactReference, ...] = Field(default_factory=tuple)
    outputs: tuple[OutputDeclaration, ...] = Field(default_factory=tuple)
    status: ExecutionTaskStatus = ExecutionTaskStatus.PENDING
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_task(self) -> ExecutionTask:
        if not self.id:
            raise ValueError("task id must be non-empty")
        if not self.name.strip():
            raise ValueError("task name must be non-empty")
        if self.id in self.dependencies:
            raise ValueError("task cannot depend on itself")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("task dependencies must be unique")
        input_keys = [(item.logical_name, item.role) for item in self.inputs]
        if len(input_keys) != len(set(input_keys)):
            raise ValueError("task input logical identities must be unique")
        output_names = [item.logical_name for item in self.outputs]
        if len(output_names) != len(set(output_names)):
            raise ValueError("task output logical names must be unique")
        return self


class TraceEvent(BaseModel):
    """Append-only lifecycle event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: TraceEventType
    run_id: str
    sequence: int
    recorded_at: datetime
    task_id: str = ""
    attempt_id: str = ""
    actor: str = "scheduler"
    payload: dict[str, str] = Field(default_factory=dict)
    causation_event_id: str = ""

    @field_validator("payload")
    @classmethod
    def _bounded_payload(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]

    @field_validator("recorded_at")
    @classmethod
    def _utc_recorded_at(cls, value: datetime) -> datetime:
        result = _require_utc(value)
        assert result is not None
        return result

    @model_validator(mode="after")
    def _validate_event(self) -> TraceEvent:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if not self.run_id:
            raise ValueError("event run_id must be non-empty")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        task_events = {
            TraceEventType.TASK_READY,
            TraceEventType.TASK_STARTED,
            TraceEventType.TASK_COMPLETED,
            TraceEventType.TASK_FAILED,
            TraceEventType.TASK_BLOCKED,
            TraceEventType.TASK_SKIPPED,
            TraceEventType.TASK_CANCELLED,
            TraceEventType.ARTIFACT_REGISTERED,
            TraceEventType.ARTIFACT_INVALIDATED,
        }
        if self.event_type in task_events and not self.task_id:
            raise ValueError(f"{self.event_type.value} requires task_id")
        if self.event_type in {
            TraceEventType.TASK_STARTED,
            TraceEventType.TASK_COMPLETED,
            TraceEventType.TASK_FAILED,
        } and not self.attempt_id:
            raise ValueError(f"{self.event_type.value} requires attempt_id")
        return self


class ExecutionTrace(BaseModel):
    """Append-oriented execution lifecycle history."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    run_id: str
    graph_id: str = ""
    strategy_id: str = ""
    created_at: datetime
    updated_at: datetime
    events: tuple[TraceEvent, ...] = Field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    @field_validator("events")
    @classmethod
    def _bounded_events(cls, value: tuple[TraceEvent, ...]) -> tuple[TraceEvent, ...]:
        if len(value) > MAX_TRACE_EVENTS:
            raise ValueError(f"events exceeds {MAX_TRACE_EVENTS} entries")
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def _utc_envelope(cls, value: datetime) -> datetime:
        result = _require_utc(value)
        assert result is not None
        return result

    @model_validator(mode="after")
    def _validate_trace(self) -> ExecutionTrace:
        if not self.trace_id or not self.run_id:
            raise ValueError("trace_id and run_id must be non-empty")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        event_ids: set[str] = set()
        sequences: set[int] = set()
        last_sequence = -1
        started_attempts: set[tuple[str, str]] = set()
        for event in self.events:
            if event.run_id != self.run_id:
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
            if event.event_type == TraceEventType.TASK_STARTED and event.task_id and event.attempt_id:
                started_attempts.add((event.task_id, event.attempt_id))
            if event.event_type in {
                TraceEventType.TASK_COMPLETED,
                TraceEventType.TASK_FAILED,
            }:
                key = (event.task_id, event.attempt_id)
                if key not in started_attempts:
                    raise ValueError(f"{event.event_type.value} without prior TaskStarted")
        return self


class ExecutionRun(BaseModel):
    """Durable execution run envelope."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    graph_id: str
    strategy_id: str
    workspace_ref: str = ""
    backend_kind: str = "fake"
    policy_snapshot: dict[str, str] = Field(default_factory=dict)
    status: ExecutionRunStatus = ExecutionRunStatus.PENDING
    task_ids: tuple[str, ...] = Field(default_factory=tuple)
    trace_id: str = ""
    parent_run_id: str = ""
    prior_run_id: str = ""
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    engine_version: str = ENGINE_VERSION
    decomposition_version: str = DECOMPOSITION_VERSION
    schema_version: str = SCHEMA_VERSION

    @field_validator("policy_snapshot")
    @classmethod
    def _bounded_policy(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def _utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)

    @model_validator(mode="after")
    def _validate_run(self) -> ExecutionRun:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.graph_id or not self.strategy_id:
            raise ValueError("graph_id and strategy_id must be non-empty")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not precede started_at")
        if self.status in {
            ExecutionRunStatus.SUCCESS,
            ExecutionRunStatus.FAILED,
            ExecutionRunStatus.CANCELLED,
        } and self.completed_at is None:
            raise ValueError("terminal run status requires completed_at")
        return self


class ExecutionReport(BaseModel):
    """Immutable run-level outcome summary."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    run_id: str
    graph_id: str
    strategy_id: str
    status: ExecutionRunStatus
    backend_kind: str = ""
    policy_summary: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    task_results: tuple[TaskExecutionResult, ...] = Field(default_factory=tuple)
    status_counts: dict[str, int] = Field(default_factory=dict)
    artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    metric_ids: tuple[str, ...] = Field(default_factory=tuple)
    errors: tuple[ExecutionError, ...] = Field(default_factory=tuple)
    skipped_task_ids: tuple[str, ...] = Field(default_factory=tuple)
    cancelled_task_ids: tuple[str, ...] = Field(default_factory=tuple)
    attempt_count: int = 0
    resume_lineage: tuple[str, ...] = Field(default_factory=tuple)
    trace_id: str = ""
    summary: str = ""
    schema_version: str = SCHEMA_VERSION

    @field_validator("policy_summary")
    @classmethod
    def _bounded_policy(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_bounded_metadata(value)  # type: ignore[return-value]

    @field_validator("started_at", "completed_at")
    @classmethod
    def _utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)

    @model_validator(mode="after")
    def _validate_report(self) -> ExecutionReport:
        if not self.report_id or not self.run_id:
            raise ValueError("report_id and run_id must be non-empty")
        if not self.graph_id or not self.strategy_id:
            raise ValueError("graph_id and strategy_id must be non-empty")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not precede started_at")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        valid_status_keys = {item.value for item in ExecutionTaskStatus}
        if any(key not in valid_status_keys or count < 0 for key, count in self.status_counts.items()):
            raise ValueError("status_counts contains an invalid status or negative count")
        result_counts: dict[str, int] = {}
        for result in self.task_results:
            key = result.status.value
            result_counts[key] = result_counts.get(key, 0) + 1
        if any(self.status_counts.get(key, 0) < count for key, count in result_counts.items()):
            raise ValueError("status_counts understates task result statuses")
        if self.status == ExecutionRunStatus.SUCCESS and any(
            key != ExecutionTaskStatus.SUCCESS.value and count > 0
            for key, count in self.status_counts.items()
        ):
            raise ValueError("SUCCESS report cannot contain non-success task counts")
        expected_attempts = sum(len(result.attempts) for result in self.task_results)
        if self.attempt_count != expected_attempts:
            raise ValueError("attempt_count must equal sum of task result attempt history")
        for result in self.task_results:
            if result.run_id != self.run_id:
                raise ValueError("task result run_id must match report run_id")
        if self.status == ExecutionRunStatus.FAILED and not self.errors and not self.skipped_task_ids:
            raise ValueError("FAILED report requires failure evidence")
        return self
