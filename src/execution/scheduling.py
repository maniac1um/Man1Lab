"""Sequential fail-fast scheduler."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4
from execution.errors import ArtifactValidationError, ExecutionEngineError
from execution.ports.artifacts import ArtifactTrackerPort
from execution.ports.executor import ExecutorPort, TaskAttemptRequest
from execution.ports.input_resolver import InputResolverPort
from execution.ports.reconciliation import ReconciliationPort
from execution.persistence import TransitionCommitter
from execution.persistence.coordinator import SchedulerRunState, wrap_trace_builder
from execution.redaction import redact_string
from execution.report import terminal_run_status
from execution.trace import ExecutionTraceBuilder
from execution.transitions import transition_task
from models.execution_engine import (
    Attempt,
    ExecutionError,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionTrace,
    ReconciliationState,
    TaskExecutionResult,
    TaskResultSummary,
    TraceEventType,
)
@dataclass
class SchedulerResult:
    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_results: tuple[TaskExecutionResult, ...]
    trace: ExecutionTrace
    artifact_ids: tuple[str, ...] = field(default_factory=tuple)
class SequentialScheduler:
    """Deterministic single-threaded scheduler with fail-fast policy."""
    def __init__(
        self,
        executor: ExecutorPort,
        artifact_tracker: ArtifactTrackerPort,
        input_resolver: InputResolverPort,
        reconciliation: ReconciliationPort,
        attempt_logs_dir_resolver: Callable[[str, str], str] | None = None,
    ) -> None:
        self._executor = executor
        self._artifact_tracker = artifact_tracker
        self._input_resolver = input_resolver
        self._reconciliation = reconciliation
        self._attempt_logs_dir_resolver = attempt_logs_dir_resolver

    def _resolve_attempt_logs_dir(self, run_id: str, attempt_id: str) -> str:
        if self._attempt_logs_dir_resolver is None:
            return ""
        return self._attempt_logs_dir_resolver(run_id, attempt_id)

    def run(
        self,
        *,
        run: ExecutionRun,
        tasks: tuple[ExecutionTask, ...],
        trace_builder: ExecutionTraceBuilder,
        prior_results: dict[str, TaskExecutionResult] | None = None,
        cancelled: bool = False,
        transition_committer: TransitionCommitter | None = None,
    ) -> SchedulerResult:
        task_map = {task.id: task for task in tasks}
        results: dict[str, TaskExecutionResult] = dict(prior_results or {})
        run_state = SchedulerRunState(run=run, tasks=tasks, task_map=task_map, results=results)
        trace = wrap_trace_builder(
            trace_builder,
            committer=transition_committer,
            run_state=run_state,
        )
        started_at = run.started_at or datetime.now(UTC)
        current_run = run.model_copy(
            update={
                "status": ExecutionRunStatus.RUNNING,
                "started_at": started_at,
                "backend_kind": self._executor.backend_kind,
            }
        )
        run_state.run = current_run
        if not any(event.event_type == TraceEventType.RUN_STARTED for event in trace.events):
            trace.append(
                TraceEventType.RUN_STARTED,
                actor="scheduler",
                payload={"backend_kind": run.backend_kind},
            )
        if cancelled:
            return self._cancel_all(
                run=current_run,
                task_order=tasks,
                task_map=task_map,
                trace_builder=trace,
                results=results,
                run_state=run_state,
            )
        indeterminate_ids = [
            task_id
            for task_id, result in results.items()
            if result.status == ExecutionTaskStatus.RUNNING
            or task_map.get(task_id, None) is not None
            and task_map[task_id].status == ExecutionTaskStatus.RUNNING
        ]
        indeterminate_ids = list(dict.fromkeys(indeterminate_ids))
        if indeterminate_ids:
            blocked = self._reconcile_indeterminate_tasks(
                run=current_run,
                task_map=task_map,
                trace_builder=trace,
                results=results,
                indeterminate_task_ids=tuple(indeterminate_ids),
                run_state=run_state,
            )
            if blocked:
                return blocked
        preserved_terminal = {
            task_id: task.status
            for task_id, task in task_map.items()
            if task.status in {
                ExecutionTaskStatus.FAILED,
                ExecutionTaskStatus.SKIPPED,
                ExecutionTaskStatus.CANCELLED,
            }
        }
        if preserved_terminal:
            self._skip_remaining_pending(
                task_map,
                trace,
                reason="prior_terminal_state",
            )
        failed = False
        while True:
            ready_ids = self._ready_task_ids(run.run_id, task_map, results)
            if not ready_ids:
                blocked_task_id = self._fail_first_input_blocked_task(
                    run=current_run,
                    task_map=task_map,
                    trace_builder=trace,
                    results=results,
                )
                if blocked_task_id is not None:
                    failed = True
                    self._propagate_skips(task_map, blocked_task_id, trace)
                    self._skip_remaining_pending(task_map, trace, reason="fail_fast")
                break
            if failed:
                self._skip_tasks(task_map, ready_ids, trace, reason="upstream_failure")
                continue
            task_id = ready_ids[0]
            if task_map[task_id].status == ExecutionTaskStatus.SUCCESS:
                continue
            task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.READY)
            trace.append(
                TraceEventType.TASK_READY,
                task_id=task_id,
                actor="scheduler",
            )
            result = self._dispatch_task(
                run=current_run,
                task_map=task_map,
                task_id=task_id,
                trace_builder=trace,
                prior_result=results.get(task_id),
                results=results,
            )
            results[task_id] = result
            if result.status == ExecutionTaskStatus.FAILED:
                failed = True
                self._propagate_skips(task_map, task_id, trace)
                self._skip_remaining_pending(task_map, trace, reason="fail_fast")
            elif result.status == ExecutionTaskStatus.CANCELLED:
                return self._cancel_all(
                    run=current_run,
                    task_order=tasks,
                    task_map=task_map,
                    trace_builder=trace,
                    results=results,
                )
        final_tasks = tuple(task_map[task.id] for task in tasks)
        final_status = terminal_run_status(final_tasks)
        if any(task.status == ExecutionTaskStatus.RUNNING for task in final_tasks):
            final_status = ExecutionRunStatus.RECONCILIATION_REQUIRED
        completed_at = datetime.now(UTC)
        current_run = current_run.model_copy(
            update={"status": final_status, "completed_at": completed_at}
        )
        run_state.run = current_run
        if final_status == ExecutionRunStatus.SUCCESS:
            trace.append(TraceEventType.RUN_COMPLETED, actor="scheduler")
        elif final_status == ExecutionRunStatus.CANCELLED:
            trace.append(TraceEventType.RUN_CANCELLED, actor="scheduler")
        elif final_status in {
            ExecutionRunStatus.INTERRUPTED,
            ExecutionRunStatus.RECONCILIATION_REQUIRED,
        }:
            trace.append(TraceEventType.RUN_INTERRUPTED, actor="scheduler")
        else:
            trace.append(TraceEventType.RUN_FAILED, actor="scheduler")
        artifact_ids = self._artifact_ids_from_results(results, tasks)
        return SchedulerResult(
            run=current_run,
            tasks=final_tasks,
            task_results=tuple(results[task.id] for task in tasks if task.id in results),
            trace=trace.build(),
            artifact_ids=artifact_ids,
        )
    def _reconcile_indeterminate_tasks(
        self,
        *,
        run: ExecutionRun,
        task_map: dict[str, ExecutionTask],
        trace_builder: ExecutionTraceBuilder,
        results: dict[str, TaskExecutionResult],
        indeterminate_task_ids: tuple[str, ...],
        run_state: SchedulerRunState,
    ) -> SchedulerResult | None:
        for task_id in indeterminate_task_ids:
            prior = results.get(task_id)
            if prior is None or not prior.attempts:
                continue
            attempt = prior.attempts[-1]
            reconciliation = self._reconciliation.reconcile_attempt(
                run_id=run.run_id,
                task_id=task_id,
                attempt_id=attempt.attempt_id,
                prior_result=prior,
                backend_operation_ref=attempt.backend_operation_ref,
            )
            if reconciliation.reconciled_state == ReconciliationState.STILL_RUNNING:
                completed_at = datetime.now(UTC)
                interrupted_run = run.model_copy(
                    update={
                        "status": ExecutionRunStatus.INTERRUPTED,
                        "completed_at": completed_at,
                    }
                )
                run_state.run = interrupted_run
                trace_builder.append(
                    TraceEventType.RUN_INTERRUPTED,
                    actor="scheduler",
                    payload={"task_id": task_id, "reason": "still_running"},
                )
                final_tasks = tuple(task_map[task.id] for task in task_map.values())
                return SchedulerResult(
                    run=interrupted_run,
                    tasks=final_tasks,
                    task_results=tuple(results.values()),
                    trace=trace_builder.build(),
                    artifact_ids=self._artifact_ids_from_results(results, tuple(task_map.values())),
                )
            if reconciliation.reconciled_state in {
                ReconciliationState.UNKNOWN,
                ReconciliationState.LOST,
            }:
                completed_at = datetime.now(UTC)
                interrupted_run = run.model_copy(
                    update={
                        "status": ExecutionRunStatus.RECONCILIATION_REQUIRED,
                        "completed_at": completed_at,
                    }
                )
                run_state.run = interrupted_run
                trace_builder.append(
                    TraceEventType.RUN_INTERRUPTED,
                    actor="scheduler",
                    payload={
                        "task_id": task_id,
                        "reason": reconciliation.reconciled_state.value,
                    },
                )
                final_tasks = tuple(task_map[task.id] for task in task_map.values())
                return SchedulerResult(
                    run=interrupted_run,
                    tasks=final_tasks,
                    task_results=tuple(results.values()),
                    trace=trace_builder.build(),
                    artifact_ids=self._artifact_ids_from_results(
                        results,
                        tuple(task_map.values()),
                    ),
                )
            if reconciliation.reconciled_state == ReconciliationState.FAILED:
                task_map[task_id] = transition_task(
                    task_map[task_id],
                    ExecutionTaskStatus.FAILED,
                    recovery=True,
                )
                error = reconciliation.error or ExecutionError(
                    code="reconciliation_failed",
                    message="backend reported failure during reconciliation",
                    phase="reconciliation",
                    causal_task_id=task_id,
                    causal_attempt_id=attempt.attempt_id,
                )
                results[task_id] = self._build_result(
                    run=run,
                    task_id=task_id,
                    status=ExecutionTaskStatus.FAILED,
                    attempt=attempt,
                    prior_attempts=prior.attempts[:-1],
                    outcome=None,
                    artifact_ids=list(prior.artifact_ids),
                    extra_errors=(error,),
                    prior_result=prior,
                )
                trace_builder.append(
                    TraceEventType.TASK_FAILED,
                    task_id=task_id,
                    attempt_id=attempt.attempt_id,
                    actor="scheduler",
                    payload={"phase": "reconciliation"},
                )
                continue
            if reconciliation.reconciled_state == ReconciliationState.CANCELLED:
                task_map[task_id] = transition_task(
                    task_map[task_id],
                    ExecutionTaskStatus.CANCELLED,
                    recovery=True,
                )
                results[task_id] = self._build_result(
                    run=run,
                    task_id=task_id,
                    status=ExecutionTaskStatus.CANCELLED,
                    attempt=attempt,
                    prior_attempts=prior.attempts[:-1],
                    outcome=None,
                    artifact_ids=list(prior.artifact_ids),
                    task_result=TaskResultSummary(termination_reason="cancelled", cancelled=True),
                    prior_result=prior,
                )
                trace_builder.append(
                    TraceEventType.TASK_CANCELLED,
                    task_id=task_id,
                    attempt_id=attempt.attempt_id,
                    actor="scheduler",
                )
                continue
            if reconciliation.reconciled_state == ReconciliationState.SUCCEEDED:
                task = task_map[task_id]
                try:
                    validated = self._artifact_tracker.validate_required_outputs(
                        run_id=run.run_id,
                        task_id=task_id,
                        attempt_id=attempt.attempt_id,
                        declarations=task.outputs,
                    )
                    artifact_ids = [item.artifact_id for item in validated]
                except ArtifactValidationError as exc:
                    task_map[task_id] = transition_task(
                        task_map[task_id],
                        ExecutionTaskStatus.FAILED,
                        recovery=True,
                    )
                    failure = ExecutionError(
                        code="artifact_validation_failed",
                        message=str(exc),
                        phase="artifact_validation",
                        causal_task_id=task_id,
                        causal_attempt_id=attempt.attempt_id,
                    )
                    results[task_id] = self._build_result(
                        run=run,
                        task_id=task_id,
                        status=ExecutionTaskStatus.FAILED,
                        attempt=attempt,
                        prior_attempts=prior.attempts[:-1],
                        outcome=None,
                        artifact_ids=list(prior.artifact_ids),
                        extra_errors=(failure,),
                        prior_result=prior,
                    )
                    trace_builder.append(
                        TraceEventType.TASK_FAILED,
                        task_id=task_id,
                        attempt_id=attempt.attempt_id,
                        actor="artifact_tracker",
                        payload={"reason": "artifact_validation"},
                    )
                    continue
                task_map[task_id] = transition_task(
                    task_map[task_id],
                    ExecutionTaskStatus.SUCCESS,
                    recovery=True,
                )
                results[task_id] = self._build_result(
                    run=run,
                    task_id=task_id,
                    status=ExecutionTaskStatus.SUCCESS,
                    attempt=attempt,
                    prior_attempts=prior.attempts[:-1],
                    outcome=None,
                    artifact_ids=artifact_ids,
                    task_result=TaskResultSummary(termination_reason="reconciled_success"),
                    prior_result=prior,
                )
                trace_builder.append(
                    TraceEventType.TASK_COMPLETED,
                    task_id=task_id,
                    attempt_id=attempt.attempt_id,
                    actor="scheduler",
                    payload={"phase": "reconciliation"},
                )
        return None
    def _ready_task_ids(
        self,
        run_id: str,
        task_map: dict[str, ExecutionTask],
        results: dict[str, TaskExecutionResult],
    ) -> list[str]:
        ready: list[str] = []
        for task_id, task in task_map.items():
            if task.status == ExecutionTaskStatus.SUCCESS:
                continue
            if task.status != ExecutionTaskStatus.PENDING:
                continue
            if not self._dependencies_satisfied(task, task_map, results):
                continue
            resolution = self._input_resolver.resolve_inputs(
                run_id=run_id,
                task=task,
                prior_results=results,
            )
            if not resolution.ready:
                continue
            ready.append(task_id)
        return ready
    def _dependencies_satisfied(
        self,
        task: ExecutionTask,
        task_map: dict[str, ExecutionTask],
        results: dict[str, TaskExecutionResult],
    ) -> bool:
        for dep_id in task.dependencies:
            dep = task_map[dep_id]
            if dep.status != ExecutionTaskStatus.SUCCESS:
                return False
            if dep_id in results and results[dep_id].status != ExecutionTaskStatus.SUCCESS:
                return False
        return True

    def _fail_first_input_blocked_task(
        self,
        *,
        run: ExecutionRun,
        task_map: dict[str, ExecutionTask],
        trace_builder: ExecutionTraceBuilder,
        results: dict[str, TaskExecutionResult],
    ) -> str | None:
        """Record a deterministic pre-dispatch failure for an unresolved required input."""
        for task_id, task in task_map.items():
            if task.status != ExecutionTaskStatus.PENDING:
                continue
            if not self._dependencies_satisfied(task, task_map, results):
                continue
            resolution = self._input_resolver.resolve_inputs(
                run_id=run.run_id,
                task=task,
                prior_results=results,
            )
            if resolution.ready:
                continue
            reason = redact_string(resolution.blocking_reason)[:1024]
            task_map[task_id] = transition_task(task, ExecutionTaskStatus.FAILED)
            error = ExecutionError(
                code="required_input_unavailable",
                message=reason or "required task input is unavailable",
                phase="input_resolution",
                causal_task_id=task_id,
            )
            results[task_id] = TaskExecutionResult(
                result_id=f"res-{uuid4()}",
                run_id=run.run_id,
                task_id=task_id,
                status=ExecutionTaskStatus.FAILED,
                backend_kind=self._executor.backend_kind,
                task_result=TaskResultSummary(termination_reason="input_blocked"),
                errors=(error,),
            )
            trace_builder.append(
                TraceEventType.TASK_BLOCKED,
                task_id=task_id,
                actor="input_resolver",
                payload={"reason": reason or "required_input_unavailable"},
            )
            return task_id
        return None
    def _dispatch_task(
        self,
        *,
        run: ExecutionRun,
        task_map: dict[str, ExecutionTask],
        task_id: str,
        trace_builder: ExecutionTraceBuilder,
        prior_result: TaskExecutionResult | None,
        results: dict[str, TaskExecutionResult],
    ) -> TaskExecutionResult:
        task = task_map[task_id]
        prior_attempts = prior_result.attempts if prior_result else ()
        attempt_id = f"att-{uuid4()}"
        started_at = datetime.now(UTC)
        provisional_attempt = Attempt(
            attempt_id=attempt_id,
            task_id=task_id,
            backend_kind=self._executor.backend_kind,
            started_at=started_at,
            backend_operation_ref=f"{self._executor.backend_kind}-{attempt_id}",
        )
        results[task_id] = TaskExecutionResult(
            result_id=f"res-{uuid4()}",
            run_id=run.run_id,
            task_id=task_id,
            status=ExecutionTaskStatus.RUNNING,
            attempts=prior_attempts + (provisional_attempt,),
            started_at=started_at,
            backend_kind=self._executor.backend_kind,
            task_result=TaskResultSummary(
                termination_reason="running",
                backend_operation_ref=provisional_attempt.backend_operation_ref,
            ),
        )
        task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.RUNNING)
        started_event = trace_builder.append(
            TraceEventType.TASK_STARTED,
            task_id=task_id,
            attempt_id=attempt_id,
            actor="scheduler",
            payload={"backend_kind": self._executor.backend_kind},
            recorded_at=started_at,
        )
        resolution = self._input_resolver.resolve_inputs(
            run_id=run.run_id,
            task=task_map[task_id],
            prior_results=results,
        )
        request = TaskAttemptRequest(
            run_id=run.run_id,
            task=task_map[task_id],
            attempt_id=attempt_id,
            resolved_inputs=resolution.inputs,
            declared_outputs=task.outputs,
            logs_dir=self._resolve_attempt_logs_dir(run.run_id, attempt_id),
        )
        try:
            outcome = self._executor.execute_attempt(request)
        except ExecutionEngineError:
            raise
        except Exception as exc:
            completed_at = datetime.now(UTC)
            attempt = Attempt(
                attempt_id=attempt_id,
                task_id=task_id,
                backend_kind=self._executor.backend_kind,
                started_at=started_event.recorded_at,
                completed_at=completed_at,
                termination_reason="executor_exception",
            )
            failure = ExecutionError(
                code="executor_exception",
                message=redact_string(str(exc)),
                phase="execution",
                causal_task_id=task_id,
                causal_attempt_id=attempt_id,
            )
            task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.FAILED)
            result = self._build_result(
                run=run,
                task_id=task_id,
                status=ExecutionTaskStatus.FAILED,
                attempt=attempt,
                prior_attempts=prior_attempts,
                outcome=None,
                artifact_ids=[],
                extra_errors=(failure,),
                prior_result=prior_result,
            )
            results[task_id] = result
            trace_builder.append(
                TraceEventType.TASK_FAILED,
                task_id=task_id,
                attempt_id=attempt_id,
                actor="scheduler",
                payload={"reason": "executor_exception"},
                causation_event_id=started_event.event_id,
            )
            return result
        attempt = Attempt(
            attempt_id=attempt_id,
            task_id=task_id,
            backend_kind=outcome.backend_kind,
            started_at=outcome.started_at,
            completed_at=outcome.completed_at,
            termination_reason=outcome.termination_reason,
            backend_operation_ref=outcome.backend_operation_ref,
        )
        produced_ids: list[str] = []
        for candidate in outcome.artifact_candidates:
            artifact = self._artifact_tracker.register_candidate(
                run_id=run.run_id,
                task_id=task_id,
                attempt_id=attempt_id,
                candidate=candidate,
            )
            produced_ids.append(artifact.artifact_id)
            trace_builder.append(
                TraceEventType.ARTIFACT_REGISTERED,
                task_id=task_id,
                attempt_id=attempt_id,
                actor="artifact_tracker",
                payload={
                    "artifact_id": artifact.artifact_id,
                    "logical_name": artifact.logical_name,
                },
            )
        if outcome.cancelled:
            task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.CANCELLED)
            result = self._build_result(
                run=run,
                task_id=task_id,
                status=ExecutionTaskStatus.CANCELLED,
                attempt=attempt,
                prior_attempts=prior_attempts,
                outcome=outcome,
                artifact_ids=produced_ids,
                prior_result=prior_result,
            )
            results[task_id] = result
            trace_builder.append(
                TraceEventType.TASK_CANCELLED,
                task_id=task_id,
                attempt_id=attempt_id,
                causation_event_id=started_event.event_id,
            )
            return result
        if not outcome.succeeded:
            task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.FAILED)
            outcome_errors = ()
            if not outcome.errors:
                outcome_errors = (
                    ExecutionError(
                        code="execution_failed",
                        message="executor reported failure without structured error details",
                        phase="execution",
                        causal_task_id=task_id,
                        causal_attempt_id=attempt_id,
                    ),
                )
            result = self._build_result(
                run=run,
                task_id=task_id,
                status=ExecutionTaskStatus.FAILED,
                attempt=attempt,
                prior_attempts=prior_attempts,
                outcome=outcome,
                artifact_ids=produced_ids,
                prior_result=prior_result,
                extra_errors=outcome_errors,
            )
            results[task_id] = result
            trace_builder.append(
                TraceEventType.TASK_FAILED,
                task_id=task_id,
                attempt_id=attempt_id,
                actor="scheduler",
                causation_event_id=started_event.event_id,
            )
            return result
        try:
            validated = self._artifact_tracker.validate_required_outputs(
                run_id=run.run_id,
                task_id=task_id,
                attempt_id=attempt_id,
                declarations=task.outputs,
            )
            produced_ids = [artifact.artifact_id for artifact in validated]
        except ArtifactValidationError as exc:
            task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.FAILED)
            failure = ExecutionError(
                code="artifact_validation_failed",
                message=str(exc),
                phase="artifact_validation",
                causal_task_id=task_id,
                causal_attempt_id=attempt_id,
            )
            result = self._build_result(
                run=run,
                task_id=task_id,
                status=ExecutionTaskStatus.FAILED,
                attempt=attempt,
                prior_attempts=prior_attempts,
                outcome=outcome,
                artifact_ids=produced_ids,
                extra_errors=(failure,),
                prior_result=prior_result,
            )
            results[task_id] = result
            trace_builder.append(
                TraceEventType.TASK_FAILED,
                task_id=task_id,
                attempt_id=attempt_id,
                actor="artifact_tracker",
                payload={"reason": "artifact_validation"},
                causation_event_id=started_event.event_id,
            )
            return result
        task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.SUCCESS)
        result = self._build_result(
            run=run,
            task_id=task_id,
            status=ExecutionTaskStatus.SUCCESS,
            attempt=attempt,
            prior_attempts=prior_attempts,
            outcome=outcome,
            artifact_ids=produced_ids,
            prior_result=prior_result,
        )
        results[task_id] = result
        trace_builder.append(
            TraceEventType.TASK_COMPLETED,
            task_id=task_id,
            attempt_id=attempt_id,
            actor="scheduler",
            causation_event_id=started_event.event_id,
        )
        return result
    def _build_result(
        self,
        *,
        run: ExecutionRun,
        task_id: str,
        status: ExecutionTaskStatus,
        attempt: Attempt,
        prior_attempts: tuple[Attempt, ...],
        prior_result: TaskExecutionResult | None = None,
        outcome,
        artifact_ids: list[str],
        extra_errors: tuple[ExecutionError, ...] = (),
        task_result: TaskResultSummary | None = None,
    ) -> TaskExecutionResult:
        errors = tuple(prior_result.errors) + extra_errors if prior_result else extra_errors
        logs = tuple(prior_result.logs) if prior_result else ()
        metrics = tuple(prior_result.metrics) if prior_result else ()
        started_at = attempt.started_at
        completed_at = attempt.completed_at
        duration_seconds = None
        backend_kind = attempt.backend_kind
        summary = task_result
        if outcome is not None:
            errors = errors + tuple(outcome.errors)
            logs = logs + tuple(outcome.logs)
            metrics = metrics + tuple(outcome.metrics)
            started_at = outcome.started_at or started_at
            completed_at = outcome.completed_at or completed_at
            duration_seconds = outcome.duration_seconds
            backend_kind = outcome.backend_kind
            if summary is None:
                summary = TaskResultSummary(
                    termination_reason=outcome.termination_reason,
                    exit_code=outcome.exit_code,
                    backend_operation_ref=outcome.backend_operation_ref,
                    cancelled=outcome.cancelled,
                    timed_out=outcome.timed_out,
                )
        if summary is None and status == ExecutionTaskStatus.FAILED:
            summary = TaskResultSummary(termination_reason="failed")
        prior_artifact_ids = list(prior_result.artifact_ids) if prior_result else []
        combined_artifacts = list(prior_artifact_ids)
        for artifact_id in artifact_ids:
            if artifact_id and artifact_id not in combined_artifacts:
                combined_artifacts.append(artifact_id)
        return TaskExecutionResult(
            result_id=f"res-{uuid4()}",
            run_id=run.run_id,
            task_id=task_id,
            status=status,
            attempts=prior_attempts + (attempt,),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            backend_kind=backend_kind,
            task_result=summary,
            logs=logs,
            artifact_ids=tuple(combined_artifacts),
            errors=errors,
            metrics=metrics,
        )
    def _propagate_skips(
        self,
        task_map: dict[str, ExecutionTask],
        failed_task_id: str,
        trace_builder: ExecutionTraceBuilder,
    ) -> None:
        changed = True
        while changed:
            changed = False
            for task_id, task in list(task_map.items()):
                if task.status != ExecutionTaskStatus.PENDING:
                    continue
                if any(
                    task_map[dep_id].status in {ExecutionTaskStatus.FAILED, ExecutionTaskStatus.SKIPPED}
                    for dep_id in task.dependencies
                ):
                    task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.SKIPPED)
                    trace_builder.append(
                        TraceEventType.TASK_SKIPPED,
                        task_id=task_id,
                        actor="scheduler",
                        payload={"blocked_by": failed_task_id},
                    )
                    changed = True
    def _skip_remaining_pending(
        self,
        task_map: dict[str, ExecutionTask],
        trace_builder: ExecutionTraceBuilder,
        *,
        reason: str,
    ) -> None:
        for task_id, task in task_map.items():
            if task.status == ExecutionTaskStatus.PENDING:
                task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.SKIPPED)
                trace_builder.append(
                    TraceEventType.TASK_SKIPPED,
                    task_id=task_id,
                    actor="scheduler",
                    payload={"reason": reason},
                )
    def _skip_tasks(
        self,
        task_map: dict[str, ExecutionTask],
        task_ids: list[str],
        trace_builder: ExecutionTraceBuilder,
        *,
        reason: str,
    ) -> None:
        for task_id in task_ids:
            task = task_map[task_id]
            if task.status == ExecutionTaskStatus.PENDING:
                task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.SKIPPED)
                trace_builder.append(
                    TraceEventType.TASK_SKIPPED,
                    task_id=task_id,
                    actor="scheduler",
                    payload={"reason": reason},
                )
    def _cancel_all(
        self,
        *,
        run: ExecutionRun,
        task_order: tuple[ExecutionTask, ...],
        task_map: dict[str, ExecutionTask],
        trace_builder: ExecutionTraceBuilder,
        results: dict[str, TaskExecutionResult],
        run_state: SchedulerRunState,
    ) -> SchedulerResult:
        for task_id, task in task_map.items():
            if task.status in {
                ExecutionTaskStatus.PENDING,
                ExecutionTaskStatus.READY,
                ExecutionTaskStatus.RUNNING,
            }:
                task_map[task_id] = transition_task(task_map[task_id], ExecutionTaskStatus.CANCELLED)
                trace_builder.append(
                    TraceEventType.TASK_CANCELLED,
                    task_id=task_id,
                    actor="scheduler",
                )
        final_tasks = tuple(task_map[task.id] for task in task_order)
        completed_at = datetime.now(UTC)
        final_run = run.model_copy(
            update={"status": ExecutionRunStatus.CANCELLED, "completed_at": completed_at}
        )
        run_state.run = final_run
        trace_builder.append(TraceEventType.RUN_CANCELLED, actor="scheduler")
        artifact_ids = self._artifact_ids_from_results(results, task_order)
        return SchedulerResult(
            run=final_run,
            tasks=final_tasks,
            task_results=tuple(results[task.id] for task in task_order if task.id in results),
            trace=trace_builder.build(),
            artifact_ids=artifact_ids,
        )
    def _artifact_ids_from_results(
        self,
        results: dict[str, TaskExecutionResult],
        tasks: tuple[ExecutionTask, ...],
    ) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for task in tasks:
            result = results.get(task.id)
            if result is None or result.status != ExecutionTaskStatus.SUCCESS or not result.attempts:
                continue
            current_attempt_id = result.attempts[-1].attempt_id
            declarations = {item.logical_name: item for item in task.outputs}
            for artifact_id in result.artifact_ids:
                artifact = self._artifact_tracker.get_artifact(artifact_id)
                declaration = declarations.get(artifact.logical_name) if artifact is not None else None
                if (
                    artifact_id
                    and artifact_id not in seen
                    and self._artifact_tracker.artifact_still_valid(artifact_id)
                    and artifact is not None
                    and artifact.producer_run_id == result.run_id
                    and artifact.producer_task_id == task.id
                    and artifact.producer_attempt_id == current_attempt_id
                    and declaration is not None
                    and artifact.artifact_type == declaration.artifact_type
                    and artifact.scope == declaration.scope
                ):
                    seen.add(artifact_id)
                    ordered.append(artifact_id)
        return tuple(ordered)
