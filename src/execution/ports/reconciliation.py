"""Reconciliation port for indeterminate RUNNING tasks on resume."""

from __future__ import annotations

from typing import Protocol

from models.execution_engine import ReconciliationResult, TaskExecutionResult


class ReconciliationPort(Protocol):
    """Reconciles backend state for interrupted RUNNING attempts."""

    def reconcile_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        attempt_id: str,
        prior_result: TaskExecutionResult,
        backend_operation_ref: str = "",
    ) -> ReconciliationResult:
        """Return reconciled state for one indeterminate attempt."""
