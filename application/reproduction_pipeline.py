"""One-command reproduction orchestration for the application layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from application.platform_execution import ExecutionRunOutcome, MaterializationGateError, PlatformExecutionService
from application.runtime.materialization_wiring import (
    materialize_execution_graph,
    persist_materialization,
)
from execution_planning.execution_graph import build_execution_graph
from models.execution_materialization import ExecutionMaterialization, MaterializationReport, MaterializationStatus
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.report import ReportModel
from models.research_resource_discovery import ResearchResourceDiscovery
from runtime.session.decision_artifacts import persist_planning_decision_artifacts
from runtime.session.workspace_store import WorkspaceArtifactStore


@dataclass(frozen=True)
class ReproductionPipelineResult:
    """Outcome of the end-to-end reproduction pipeline."""

    report: ReportModel | None
    materialization: ExecutionMaterialization | None
    execution: ExecutionRunOutcome | None
    materialization_report: MaterializationReport | None = None
    blocked: bool = False
    diagnostics: str = ""


class ReproductionPipelineService:
    """Sequence analysis through execution without owning capability internals."""

    def __init__(
        self,
        *,
        analyze,
        discover,
        plan,
        platform_execution: PlatformExecutionService,
        workspace_root: Path,
        persist_planning_artifacts: bool = True,
    ) -> None:
        self._analyze = analyze
        self._discover = discover
        self._plan = plan
        self._platform_execution = platform_execution
        self._workspace_root = workspace_root
        self._persist_planning_artifacts = persist_planning_artifacts

    def reproduce(self, paper_path: Path | str) -> ReproductionPipelineResult:
        path = Path(paper_path)
        store = WorkspaceArtifactStore(self._workspace_root)

        analysis = self._analyze(path)
        store.save_analysis(analysis)

        discovery = self._discover(analysis)
        store.save_discovery(discovery)

        strategy = self._plan(analysis, discovery)
        store.save_strategy(strategy)

        if self._persist_planning_artifacts:
            persist_planning_decision_artifacts(store, discovery, strategy)

        abstract_graph = build_execution_graph(discovery, strategy)
        materialization = materialize_execution_graph(
            strategy=strategy,
            discovery=discovery,
            graph=abstract_graph,
            workspace_root=self._workspace_root,
        )
        persist_materialization(self._workspace_root, materialization)

        if materialization.report.status is not MaterializationStatus.READY:
            diagnostics = _format_blocked_diagnostics(materialization.report)
            return ReproductionPipelineResult(
                report=build_blocked_report(diagnostics),
                materialization=materialization,
                execution=None,
                materialization_report=materialization.report,
                blocked=True,
                diagnostics=diagnostics,
            )

        try:
            execution = self._platform_execution.run_execution(
                materialization.materialized_graph,
                materialization_report=materialization.report,
                workspace_ref=self._workspace_root.as_posix(),
            )
        except MaterializationGateError as exc:
            diagnostics = str(exc)
            return ReproductionPipelineResult(
                report=build_blocked_report(diagnostics),
                materialization=materialization,
                execution=None,
                materialization_report=exc.report,
                blocked=True,
                diagnostics=diagnostics,
            )

        report = _build_execution_report(analysis, discovery, execution)
        return ReproductionPipelineResult(
            report=report,
            materialization=materialization,
            execution=execution,
            materialization_report=materialization.report,
        )


def _format_blocked_diagnostics(report: MaterializationReport) -> str:
    lines = [f"Materialization status: {report.status.value}"]
    for issue in report.errors:
        lines.append(f"- {issue.code}: {issue.message}")
    for node in report.node_results:
        for issue in node.issues:
            lines.append(f"- [{node.node_id}] {issue.code}: {issue.message}")
    return "\n".join(lines)


def _build_execution_report(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
    execution: ExecutionRunOutcome,
) -> ReportModel:
    status = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
    return ReportModel(
        reproduction_summary=(
            f"Reproduction pipeline executed run {execution.run_id} for "
            f"{analysis.metadata.title}."
        ),
        implementation_summary="Execution Engine run from READY materialized graph.",
        final_status=status,
        report_path=Path(execution.run_directory),
    )


def build_blocked_report(diagnostics: str) -> ReportModel:
    return ReportModel(
        reproduction_summary=diagnostics,
        implementation_summary="Execution blocked at materialization readiness gate.",
        final_status="blocked",
    )
