"""In-memory reconciliation adapter for tests."""

from __future__ import annotations

from datetime import UTC, datetime

from execution.ports.reconciliation import ReconciliationPort
from models.execution_engine import (
    ExecutionError,
    ReconciliationResult,
    ReconciliationState,
    TaskExecutionResult,
)


class InMemoryReconciliationPort:
    """Deterministic reconciliation outcomes configured per attempt."""

    def __init__(
        self,
        *,
        default_state: ReconciliationState = ReconciliationState.UNKNOWN,
        states_by_attempt: dict[str, ReconciliationState] | None = None,
    ) -> None:
        self._default_state = default_state
        self._states_by_attempt = states_by_attempt or {}

    def reconcile_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        attempt_id: str,
        prior_result: TaskExecutionResult,
        backend_operation_ref: str = "",
    ) -> ReconciliationResult:
        del prior_result
        state = self._states_by_attempt.get(attempt_id, self._default_state)
        error: ExecutionError | None = None
        if state in {ReconciliationState.FAILED, ReconciliationState.LOST, ReconciliationState.UNKNOWN}:
            error = ExecutionError(
                code=f"reconciliation_{state.value}",
                message=f"reconciled as {state.value}",
                phase="reconciliation",
                causal_task_id=task_id,
                causal_attempt_id=attempt_id,
            )
        return ReconciliationResult(
            run_id=run_id,
            task_id=task_id,
            attempt_id=attempt_id,
            backend_operation_ref=backend_operation_ref,
            reconciled_state=state,
            error=error,
            recorded_at=datetime.now(UTC),
        )
