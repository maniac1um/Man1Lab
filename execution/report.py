"""Pure assembly of canonical execution reports."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from models.execution_engine import (
    ExecutionError,
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionTrace,
    MetricIdentity,
    TaskExecutionResult,
)


def _collect_artifact_ids(task_results: tuple[TaskExecutionResult, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for result in task_results:
        for artifact_id in result.artifact_ids:
            if artifact_id and artifact_id not in seen:
                seen.add(artifact_id)
                ordered.append(artifact_id)
    return tuple(ordered)


def _collect_metric_ids(task_results: tuple[TaskExecutionResult, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for result in task_results:
        for metric in result.metrics:
            identity = MetricIdentity(name=metric.name, unit=metric.unit, split=metric.split)
            key = identity.identity_key()
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return tuple(ordered)


def assemble_execution_report(
    *,
    run: ExecutionRun,
    tasks: tuple[ExecutionTask, ...],
    task_results: tuple[TaskExecutionResult, ...],
    trace: ExecutionTrace,
    artifact_ids: tuple[str, ...] | None = None,
    summary: str = "",
) -> ExecutionReport:
    """Build an immutable run report from final task results and artifact manifest."""
    status_counts: dict[str, int] = {}
    for task in tasks:
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

    skipped_task_ids = tuple(task.id for task in tasks if task.status == ExecutionTaskStatus.SKIPPED)
    cancelled_task_ids = tuple(
        task.id for task in tasks if task.status == ExecutionTaskStatus.CANCELLED
    )
    errors: list[ExecutionError] = []
    for result in task_results:
        errors.extend(result.errors)

    duration_seconds: float | None = None
    if run.started_at is not None and run.completed_at is not None:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    attempt_count = sum(len(result.attempts) for result in task_results)
    lineage = tuple(item for item in (run.prior_run_id, run.parent_run_id) if item)
    artifact_ids = artifact_ids if artifact_ids is not None else _collect_artifact_ids(task_results)
    metric_ids = _collect_metric_ids(task_results)

    if not summary:
        summary = (
            f"Run {run.run_id} finished with status {run.status.value}; "
            f"{status_counts.get(ExecutionTaskStatus.SUCCESS.value, 0)} tasks succeeded."
        )

    return ExecutionReport(
        report_id=f"report-{uuid4()}",
        run_id=run.run_id,
        graph_id=run.graph_id,
        strategy_id=run.strategy_id,
        status=run.status,
        backend_kind=run.backend_kind,
        policy_summary=dict(run.policy_snapshot),
        started_at=run.started_at,
        completed_at=run.completed_at or datetime.now(UTC),
        duration_seconds=duration_seconds,
        task_results=task_results,
        status_counts=status_counts,
        artifact_ids=artifact_ids,
        metric_ids=metric_ids,
        errors=tuple(errors),
        skipped_task_ids=skipped_task_ids,
        cancelled_task_ids=cancelled_task_ids,
        attempt_count=attempt_count,
        resume_lineage=lineage,
        trace_id=trace.trace_id,
        summary=summary,
    )


def terminal_run_status(tasks: tuple[ExecutionTask, ...]) -> ExecutionRunStatus:
    """Derive run status from task terminal states."""
    if any(task.status == ExecutionTaskStatus.RUNNING for task in tasks):
        return ExecutionRunStatus.RUNNING
    if any(task.status == ExecutionTaskStatus.CANCELLED for task in tasks):
        return ExecutionRunStatus.CANCELLED
    if any(task.status == ExecutionTaskStatus.FAILED for task in tasks):
        return ExecutionRunStatus.FAILED
    if tasks and all(task.status == ExecutionTaskStatus.SUCCESS for task in tasks):
        return ExecutionRunStatus.SUCCESS
    if any(task.status == ExecutionTaskStatus.SKIPPED for task in tasks):
        return ExecutionRunStatus.FAILED
    return ExecutionRunStatus.FAILED

