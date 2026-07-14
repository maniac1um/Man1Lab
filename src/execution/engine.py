"""Public execution engine coordinator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from execution.decomposition import DecompositionResult, decompose_execution_graph
from execution.persistence.coordinator import TransitionCommitter
from execution.ports.artifacts import ArtifactTrackerPort
from execution.ports.executor import ExecutorPort
from execution.ports.input_resolver import InputResolverPort
from execution.ports.persistence import ExecutionPersistencePort, RunSnapshot
from execution.ports.reconciliation import ReconciliationPort
from execution.report import assemble_execution_report
from execution.resume import (
    apply_resume_reuse,
    assert_resume_compatible,
    compute_graph_fingerprint,
    compute_task_fingerprint,
    evaluate_resume_tasks,
)
from execution.scheduling import SchedulerResult, SequentialScheduler
from execution.trace import ExecutionTraceBuilder
from execution.validation import validate_execution_graph
from models.execution_engine import (
    ExecutionReport,
    ExecutionRun,
    ExecutionRunStatus,
    ExecutionTask,
    TaskExecutionResult,
    TraceEventType,
)
from models.execution_graph import ExecutionGraph


@dataclass(frozen=True)
class EngineRunResult:
    run: ExecutionRun
    tasks: tuple[ExecutionTask, ...]
    task_results: tuple[TaskExecutionResult, ...]
    report: ExecutionReport
    decomposition: DecompositionResult
    scheduler: SchedulerResult
    task_fingerprint: str
    graph_fingerprint: str


class ExecutionEngine:
    """Coordinates validation, decomposition, scheduling, and reporting."""

    def __init__(
        self,
        *,
        executor: ExecutorPort,
        artifact_tracker: ArtifactTrackerPort,
        input_resolver: InputResolverPort,
        reconciliation: ReconciliationPort,
        persistence: ExecutionPersistencePort | None = None,
        attempt_logs_dir_resolver: Callable[[str, str], str] | None = None,
    ) -> None:
        self._executor = executor
        self._artifact_tracker = artifact_tracker
        self._input_resolver = input_resolver
        self._reconciliation = reconciliation
        self._persistence = persistence
        self._scheduler = SequentialScheduler(
            executor,
            artifact_tracker,
            input_resolver,
            reconciliation,
            attempt_logs_dir_resolver=attempt_logs_dir_resolver,
        )

    @property
    def persistence(self) -> ExecutionPersistencePort | None:
        return self._persistence

    def start_run(
        self,
        graph: ExecutionGraph,
        *,
        run_id: str | None = None,
        workspace_ref: str = "",
        policy_snapshot: dict[str, str] | None = None,
        cancelled: bool = False,
    ) -> EngineRunResult:
        validate_execution_graph(graph)
        run_id = run_id or f"run-{uuid4()}"
        trace_id = f"trace-{uuid4()}"
        now = datetime.now(UTC)

        decomposition = decompose_execution_graph(graph, run_id=run_id, recorded_at=now)
        trace_builder = ExecutionTraceBuilder(
            trace_id=trace_id,
            run_id=run_id,
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            created_at=now,
            initial_events=decomposition.events,
        )

        run = ExecutionRun(
            run_id=run_id,
            graph_id=graph.graph_id,
            strategy_id=graph.strategy_id,
            workspace_ref=workspace_ref,
            backend_kind=self._executor.backend_kind,
            policy_snapshot=policy_snapshot or {},
            status=ExecutionRunStatus.PENDING,
            task_ids=tuple(task.id for task in decomposition.tasks),
            trace_id=trace_id,
            created_at=now,
        )

        task_fingerprint = compute_task_fingerprint(decomposition.tasks)
        graph_fingerprint = compute_graph_fingerprint(graph)
        committer: TransitionCommitter | None = None

        if self._persistence is not None:
            initial_trace = trace_builder.build()
            snapshot = RunSnapshot(
                run=run,
                tasks=decomposition.tasks,
                task_results=(),
                trace=initial_trace,
                artifacts=(),
                report=None,
                revision=0,
                task_fingerprint=task_fingerprint,
                graph_fingerprint=graph_fingerprint,
            )
            self._persistence.create_run(snapshot)
            self._persistence.acquire_writer(run_id)
            committer = TransitionCommitter(
                store=self._persistence,
                run_id=run_id,
                artifact_supplier=self._artifact_supplier,
            )

        try:
            scheduler_result = self._scheduler.run(
                run=run,
                tasks=decomposition.tasks,
                trace_builder=trace_builder,
                cancelled=cancelled,
                transition_committer=committer,
            )
            report = assemble_execution_report(
                run=scheduler_result.run,
                tasks=scheduler_result.tasks,
                task_results=scheduler_result.task_results,
                trace=scheduler_result.trace,
                artifact_ids=scheduler_result.artifact_ids,
            )
            if self._persistence is not None and committer is not None:
                committer.commit(
                    run=scheduler_result.run,
                    tasks=scheduler_result.tasks,
                    task_results={result.task_id: result for result in scheduler_result.task_results},
                    report=report,
                )
                self._persistence.save_report(run_id, report)
        finally:
            if self._persistence is not None:
                self._persistence.release_writer(run_id)

        return EngineRunResult(
            run=scheduler_result.run,
            tasks=scheduler_result.tasks,
            task_results=scheduler_result.task_results,
            report=report,
            decomposition=decomposition,
            scheduler=scheduler_result,
            task_fingerprint=task_fingerprint,
            graph_fingerprint=graph_fingerprint,
        )

    def resume_run(
        self,
        graph: ExecutionGraph,
        existing_run: ExecutionRun,
        *,
        prior_results: dict[str, TaskExecutionResult],
        stored_task_fingerprint: str,
        stored_graph_fingerprint: str,
        trace_builder: ExecutionTraceBuilder,
    ) -> EngineRunResult:
        validate_execution_graph(graph)

        decomposition = decompose_execution_graph(
            graph,
            run_id=existing_run.run_id,
            sequence_start=len(trace_builder.events),
        )
        assert_resume_compatible(
            existing_run=existing_run,
            graph=graph,
            tasks=decomposition.tasks,
            stored_task_fingerprint=stored_task_fingerprint,
            stored_graph_fingerprint=stored_graph_fingerprint,
        )

        evaluation = evaluate_resume_tasks(
            tasks=decomposition.tasks,
            prior_results=prior_results,
            result_outputs_valid=lambda task, result: self._artifact_tracker.result_satisfies_required_outputs(
                run_id=existing_run.run_id,
                task=task,
                result=result,
            ),
        )

        resumed_tasks = apply_resume_reuse(decomposition.tasks, evaluation)
        trace_builder.append(
            TraceEventType.RUN_RESUMED,
            actor="scheduler",
            payload={
                "reused": ",".join(evaluation.reusable_task_ids),
                "indeterminate": ",".join(evaluation.indeterminate_task_ids),
            },
        )

        task_fingerprint = compute_task_fingerprint(decomposition.tasks)
        graph_fingerprint = compute_graph_fingerprint(graph)
        committer: TransitionCommitter | None = None
        run_id = existing_run.run_id

        if self._persistence is not None:
            self._persistence.acquire_writer(run_id)
            committer = TransitionCommitter(
                store=self._persistence,
                run_id=run_id,
                artifact_supplier=self._artifact_supplier,
            )

        try:
            scheduler_result = self._scheduler.run(
                run=existing_run,
                tasks=resumed_tasks,
                trace_builder=trace_builder,
                prior_results=dict(prior_results),
                transition_committer=committer,
            )
            report = assemble_execution_report(
                run=scheduler_result.run,
                tasks=scheduler_result.tasks,
                task_results=scheduler_result.task_results,
                trace=scheduler_result.trace,
                artifact_ids=scheduler_result.artifact_ids,
            )
            if self._persistence is not None and committer is not None:
                committer.commit(
                    run=scheduler_result.run,
                    tasks=scheduler_result.tasks,
                    task_results={result.task_id: result for result in scheduler_result.task_results},
                    report=report,
                )
                self._persistence.save_report(run_id, report)
        finally:
            if self._persistence is not None:
                self._persistence.release_writer(run_id)

        return EngineRunResult(
            run=scheduler_result.run,
            tasks=scheduler_result.tasks,
            task_results=scheduler_result.task_results,
            report=report,
            decomposition=decomposition,
            scheduler=scheduler_result,
            task_fingerprint=task_fingerprint,
            graph_fingerprint=graph_fingerprint,
        )

    def load_and_resume_run(self, graph: ExecutionGraph, run_id: str) -> EngineRunResult:
        """Load durable state and continue scheduling with the same run_id."""
        if self._persistence is None:
            raise ValueError("persistence port is required for load_and_resume_run")
        snapshot = self._persistence.load_snapshot(run_id)
        if hasattr(self._artifact_tracker, "hydrate_artifacts"):
            self._artifact_tracker.hydrate_artifacts(snapshot.artifacts)  # type: ignore[attr-defined]
        prior_results = {result.task_id: result for result in snapshot.task_results}
        trace_builder = ExecutionTraceBuilder(
            trace_id=snapshot.trace.trace_id,
            run_id=run_id,
            graph_id=snapshot.run.graph_id,
            strategy_id=snapshot.run.strategy_id,
            created_at=snapshot.trace.created_at,
            initial_events=snapshot.trace.events,
        )
        return self.resume_run(
            graph,
            snapshot.run,
            prior_results=prior_results,
            stored_task_fingerprint=snapshot.task_fingerprint,
            stored_graph_fingerprint=snapshot.graph_fingerprint,
            trace_builder=trace_builder,
        )

    def _artifact_supplier(self):
        if hasattr(self._artifact_tracker, "all_artifacts"):
            return self._artifact_tracker.all_artifacts()  # type: ignore[attr-defined]
        return ()
