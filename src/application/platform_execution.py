"""Application composition for the Execution Engine platform integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from application.runtime.execution_wiring import create_runtime_durable_local_engine
from execution.engine import EngineRunResult, ExecutionEngine
from models.execution_engine import (
    ExecutionReport,
    ExecutionRunStatus,
    ExecutionTask,
    ExecutionTaskStatus,
)
from models.execution_graph import ExecutionGraph
from models.execution_materialization import MaterializationReport, MaterializationStatus
from runtime.context import RuntimeContext
from runtime.execution_store.file_store import FileExecutionStore
from runtime.session.materialization_artifacts import MaterializationArtifactStore
from runtime.session.workspace_store import WorkspaceArtifactStore


class MaterializationGateError(ValueError):
    """Raised when execution cannot start because materialization is not READY."""

    def __init__(self, report: MaterializationReport, message: str | None = None) -> None:
        self.report = report
        super().__init__(message or f"materialization status is {report.status.value}")


@dataclass(frozen=True)
class ExecutionRunOutcome:
    """Outcome of starting or resuming a planned execution graph."""

    run_id: str
    status: ExecutionRunStatus
    resumed: bool
    run_directory: str
    report: ExecutionReport | None


@dataclass(frozen=True)
class ExecutionTaskStatusView:
    task_id: str
    name: str
    status: ExecutionTaskStatus


@dataclass(frozen=True)
class ExecutionStatusView:
    """Inspectable execution run status for facade and console consumers."""

    run_id: str
    status: ExecutionRunStatus
    graph_id: str
    strategy_id: str
    backend_kind: str
    tasks: tuple[ExecutionTaskStatusView, ...]
    run_directory: str
    report_path: str | None
    resumable: bool


@dataclass(frozen=True)
class ExecutionReportView:
    """Execution report with workspace-relative artifact locations."""

    run_id: str
    report: ExecutionReport
    run_directory: str
    report_path: str
    completed_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]


EngineFactory = Callable[[], ExecutionEngine]


class PlatformExecutionService:
    """Compose Runtime-owned execution dependencies for one workspace."""

    def __init__(
        self,
        context: RuntimeContext,
        workspace_root: Path,
        *,
        engine_factory: EngineFactory | None = None,
    ) -> None:
        self._context = context
        self._workspace_root = workspace_root
        self._engine_factory = engine_factory or (
            lambda: create_runtime_durable_local_engine(context, workspace_root)
        )

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def run_execution(
        self,
        graph: ExecutionGraph | None = None,
        *,
        materialization_report: MaterializationReport | None = None,
        run_id: str | None = None,
        resume: bool = True,
        workspace_ref: str | None = None,
    ) -> ExecutionRunOutcome:
        """Start or resume execution for a planned graph."""
        mat_store = MaterializationArtifactStore(self._workspace_root)
        if graph is None:
            graph = mat_store.load_materialized_graph()
            if graph is None:
                graph = WorkspaceArtifactStore(self._workspace_root).load_execution_graph()
            if graph is None:
                raise ValueError(
                    "Execution graph not found in workspace. Run plan before execute."
                )
        report = materialization_report or mat_store.load_materialization_report()
        self._enforce_materialization_ready(graph, report)
        engine = self._engine_factory()
        store = self._require_store(engine)
        resolved_workspace_ref = workspace_ref or self._workspace_root.as_posix()

        if resume:
            resumable = self._find_resumable_run(
                store,
                graph.graph_id,
                requested_run_id=run_id,
            )
            if resumable is not None:
                result = engine.load_and_resume_run(graph, resumable.run_id)
                return self._to_outcome(result, resumed=True)

        result = engine.start_run(
            graph,
            run_id=run_id,
            workspace_ref=resolved_workspace_ref,
        )
        return self._to_outcome(result, resumed=False)

    def execution_status(self, run_id: str) -> ExecutionStatusView:
        """Return durable status for one execution run."""
        store = self._store()
        snapshot = store.load_snapshot(run_id)
        run_dir = store.run_dir(run_id)
        report_path = run_dir / "report.json"
        tasks = tuple(
            ExecutionTaskStatusView(
                task_id=task.id,
                name=task.name,
                status=task.status,
            )
            for task in snapshot.tasks
        )
        return ExecutionStatusView(
            run_id=snapshot.run.run_id,
            status=snapshot.run.status,
            graph_id=snapshot.run.graph_id,
            strategy_id=snapshot.run.strategy_id,
            backend_kind=snapshot.run.backend_kind,
            tasks=tasks,
            run_directory=run_dir.as_posix(),
            report_path=report_path.as_posix() if report_path.is_file() else None,
            resumable=snapshot.run.status
            in {
                ExecutionRunStatus.RUNNING,
                ExecutionRunStatus.INTERRUPTED,
                ExecutionRunStatus.RECONCILIATION_REQUIRED,
                ExecutionRunStatus.PENDING,
            },
        )

    def execution_report(self, run_id: str) -> ExecutionReportView:
        """Return the latest execution report for one run."""
        store = self._store()
        snapshot = store.load_snapshot(run_id)
        if snapshot.report is None:
            raise ValueError(f"No execution report is available for run: {run_id}")
        run_dir = store.run_dir(run_id)
        report_path = run_dir / "report.json"
        completed = tuple(
            result.task_id
            for result in snapshot.report.task_results
            if result.status is ExecutionTaskStatus.SUCCESS
        )
        failed = tuple(
            result.task_id
            for result in snapshot.report.task_results
            if result.status is ExecutionTaskStatus.FAILED
        )
        return ExecutionReportView(
            run_id=run_id,
            report=snapshot.report,
            run_directory=run_dir.as_posix(),
            report_path=report_path.as_posix(),
            completed_task_ids=completed,
            failed_task_ids=failed,
            artifact_ids=snapshot.report.artifact_ids,
        )

    def _to_outcome(self, result: EngineRunResult, *, resumed: bool) -> ExecutionRunOutcome:
        store = self._store()
        run_dir = store.run_dir(result.run.run_id)
        return ExecutionRunOutcome(
            run_id=result.run.run_id,
            status=result.run.status,
            resumed=resumed,
            run_directory=run_dir.as_posix(),
            report=result.report,
        )

    def _store(self) -> FileExecutionStore:
        return self._context.execution_store()

    def _require_store(self, engine: ExecutionEngine) -> FileExecutionStore:
        persistence = engine.persistence
        if persistence is None or not hasattr(persistence, "run_dir"):
            raise RuntimeError("execution persistence store is not configured")
        return persistence  # type: ignore[return-value]

    @staticmethod
    def _find_resumable_run(
        store: FileExecutionStore,
        graph_id: str,
        *,
        requested_run_id: str | None = None,
    ):
        for summary in store.list_resumable_runs():
            if summary.graph_id == graph_id and (
                requested_run_id is None or summary.run_id == requested_run_id
            ):
                return summary
        return None

    @staticmethod
    def _enforce_materialization_ready(
        graph: ExecutionGraph,
        report: MaterializationReport | None,
    ) -> None:
        if report is None:
            raise MaterializationGateError(
                MaterializationReport(
                    status=MaterializationStatus.BLOCKED,
                    errors=(),
                ),
                "materialization report is required before execution",
            )
        if report.status is not MaterializationStatus.READY:
            raise MaterializationGateError(report)
        if not graph.materialization_id:
            raise MaterializationGateError(report, "materialized graph is missing materialization_id")
        graph_node_ids = {node.node_id for node in graph.nodes}
        report_node_ids = {node.node_id for node in report.node_results}
        if graph_node_ids != report_node_ids:
            raise MaterializationGateError(
                report,
                "materialization report does not match graph nodes",
            )
        if any(node.execution_spec is None for node in graph.nodes):
            raise MaterializationGateError(report, "materialized graph contains incomplete nodes")
