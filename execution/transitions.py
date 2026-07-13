"""Unified task status transition API."""

from __future__ import annotations

from execution.errors import InvalidTransitionError
from models.execution_engine import ExecutionTask, ExecutionTaskStatus

_ALLOWED_TRANSITIONS: dict[ExecutionTaskStatus, frozenset[ExecutionTaskStatus]] = {
    ExecutionTaskStatus.PENDING: frozenset(
        {
            ExecutionTaskStatus.READY,
            ExecutionTaskStatus.FAILED,
            ExecutionTaskStatus.SKIPPED,
            ExecutionTaskStatus.CANCELLED,
        }
    ),
    ExecutionTaskStatus.READY: frozenset(
        {
            ExecutionTaskStatus.RUNNING,
            ExecutionTaskStatus.FAILED,
            ExecutionTaskStatus.SKIPPED,
            ExecutionTaskStatus.CANCELLED,
        }
    ),
    ExecutionTaskStatus.RUNNING: frozenset(
        {ExecutionTaskStatus.SUCCESS, ExecutionTaskStatus.FAILED, ExecutionTaskStatus.CANCELLED}
    ),
    ExecutionTaskStatus.SUCCESS: frozenset(),
    ExecutionTaskStatus.FAILED: frozenset(),
    ExecutionTaskStatus.SKIPPED: frozenset(),
    ExecutionTaskStatus.CANCELLED: frozenset(),
}

_RECOVERY_TRANSITIONS: dict[ExecutionTaskStatus, frozenset[ExecutionTaskStatus]] = {
    ExecutionTaskStatus.PENDING: frozenset(
        {
            ExecutionTaskStatus.RUNNING,
            ExecutionTaskStatus.SUCCESS,
            ExecutionTaskStatus.FAILED,
            ExecutionTaskStatus.SKIPPED,
            ExecutionTaskStatus.CANCELLED,
        }
    ),
    ExecutionTaskStatus.RUNNING: frozenset(
        {
            ExecutionTaskStatus.SUCCESS,
            ExecutionTaskStatus.FAILED,
            ExecutionTaskStatus.CANCELLED,
            ExecutionTaskStatus.RUNNING,
        }
    ),
}


def allowed_transitions(
    current: ExecutionTaskStatus,
    *,
    recovery: bool = False,
) -> frozenset[ExecutionTaskStatus]:
    if recovery:
        recovery_set = _RECOVERY_TRANSITIONS.get(current, frozenset())
        return _ALLOWED_TRANSITIONS.get(current, frozenset()) | recovery_set
    return _ALLOWED_TRANSITIONS.get(current, frozenset())


def transition_task(
    task: ExecutionTask,
    new_status: ExecutionTaskStatus,
    *,
    recovery: bool = False,
) -> ExecutionTask:
    """Return a new task with validated status transition."""
    if task.status == new_status:
        return task
    allowed = allowed_transitions(task.status, recovery=recovery)
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"illegal transition for task {task.id}: {task.status.value} -> {new_status.value}"
        )
    return task.model_copy(update={"status": new_status})
