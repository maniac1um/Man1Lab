"""Deterministic in-memory executor for tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from execution.ports.executor import (
    ArtifactCandidate,
    ExecutorPort,
    TaskAttemptOutcome,
    TaskAttemptRequest,
)
from models.execution_engine import ExecutionError, LogReference


@dataclass(frozen=True)
class FakeExecutorRule:
    succeed: bool = True
    termination_reason: str = "completed"
    exit_code: int | None = 0
    produce_outputs: bool = True
    error_message: str = ""
    cancelled: bool = False


class FakeExecutor:
    """Backend-neutral deterministic executor."""

    backend_kind = "fake"

    def __init__(
        self,
        *,
        default_rule: FakeExecutorRule | None = None,
        rules_by_task_id: dict[str, FakeExecutorRule] | None = None,
        rules_by_task_type: dict[str, FakeExecutorRule] | None = None,
    ) -> None:
        self._default_rule = default_rule or FakeExecutorRule()
        self._rules_by_task_id = rules_by_task_id or {}
        self._rules_by_task_type = rules_by_task_type or {}

    def execute_attempt(self, request: TaskAttemptRequest) -> TaskAttemptOutcome:
        rule = self._resolve_rule(request)
        started_at = datetime.now(UTC)
        completed_at = datetime.now(UTC)
        candidates: tuple[ArtifactCandidate, ...] = ()
        if rule.produce_outputs and rule.succeed:
            candidates = tuple(
                ArtifactCandidate(
                    logical_name=output.logical_name,
                    artifact_type=output.artifact_type,
                    location_ref=f"memory://{request.run_id}/{request.task.id}/{output.logical_name}",
                )
                for output in request.declared_outputs
            )
        errors: tuple[ExecutionError, ...] = ()
        if not rule.succeed:
            errors = (
                ExecutionError(
                    code="execution_failed",
                    message=rule.error_message or f"task {request.task.id} failed",
                    phase="execution",
                    retryable=False,
                    causal_task_id=request.task.id,
                    causal_attempt_id=request.attempt_id,
                ),
            )
        return TaskAttemptOutcome(
            termination_reason=rule.termination_reason,
            succeeded=rule.succeed and not rule.cancelled,
            exit_code=rule.exit_code,
            logs=(
                LogReference(
                    log_id=f"log-{request.attempt_id}",
                    stream="stdout",
                    location_ref=f"memory://logs/{request.attempt_id}",
                    excerpt="fake execution log",
                ),
            ),
            artifact_candidates=candidates,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=0.0,
            backend_kind=self.backend_kind,
            backend_operation_ref=f"fake-{request.attempt_id}",
            cancelled=rule.cancelled,
        )

    def _resolve_rule(self, request: TaskAttemptRequest) -> FakeExecutorRule:
        if request.task.id in self._rules_by_task_id:
            return self._rules_by_task_id[request.task.id]
        if request.task.type.value in self._rules_by_task_type:
            return self._rules_by_task_type[request.task.type.value]
        return self._default_rule
