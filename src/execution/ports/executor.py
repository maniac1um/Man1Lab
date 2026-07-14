"""Executor port contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from execution.ports.input_resolver import InputResolverPort, ResolvedInput
from models.execution_engine import (
    ExecutionError,
    ExecutionTask,
    LogReference,
    Metric,
    OutputDeclaration,
)


@dataclass(frozen=True)
class ArtifactCandidate:
    logical_name: str
    artifact_type: str
    location_ref: str = ""
    size_bytes: int | None = None
    integrity_digest: str = ""


@dataclass(frozen=True)
class TaskAttemptRequest:
    run_id: str
    task: ExecutionTask
    attempt_id: str
    resolved_inputs: tuple[ResolvedInput, ...] = ()
    declared_outputs: tuple[OutputDeclaration, ...] = ()
    logs_dir: str = ""


@dataclass(frozen=True)
class TaskAttemptOutcome:
    termination_reason: str
    succeeded: bool
    exit_code: int | None = None
    logs: tuple[LogReference, ...] = ()
    artifact_candidates: tuple[ArtifactCandidate, ...] = ()
    errors: tuple[ExecutionError, ...] = ()
    metrics: tuple[Metric, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    backend_kind: str = "fake"
    backend_operation_ref: str = ""
    backend_metadata: dict[str, str] = field(default_factory=dict)
    cancelled: bool = False
    timed_out: bool = False


class ExecutorPort(Protocol):
    """Backend-neutral executor contract."""

    backend_kind: str

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        """Execute exactly one task attempt and return a backend-neutral outcome."""
