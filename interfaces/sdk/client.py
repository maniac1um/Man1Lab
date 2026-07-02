"""Man1Lab Python SDK client — delegates exclusively to the Platform Facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from application.facade import DoctorReport, ExecuteResult
    from application.lifecycle import InitReport
    from configuration.models import AppSettings
    from models.execution_strategy import ExecutionStrategy
    from models.paper_reproduction_analysis import PaperReproductionAnalysis
    from models.report import ReportModel
    from models.research_resource_discovery import ResearchResourceDiscovery


class Man1Lab:
    """Stable programmatic API for the Man1Lab platform."""

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        initialize_configuration: bool = True,
        configure_logging: bool = True,
        orchestrator: object | None = None,
        reporter: object | None = None,
    ) -> None:
        from application.facade import Man1Lab as PlatformFacade

        self._facade = PlatformFacade(
            settings=settings,
            initialize_configuration=initialize_configuration,
            configure_logging=configure_logging,
            orchestrator=orchestrator,
            reporter=reporter,
        )

    def reproduce(self, paper_path: Path | str | None = None) -> ReportModel:
        """Run the complete reproduction workflow."""
        return self._facade.reproduce(paper_path)

    def analyze(self, paper_path: Path | str) -> PaperReproductionAnalysis:
        """Run analysis (Reader) only."""
        return self._facade.analyze(paper_path)

    def discover(
        self,
        analysis: PaperReproductionAnalysis | None = None,
        *,
        paper_path: Path | str | None = None,
    ) -> ResearchResourceDiscovery:
        """Run discovery only."""
        return self._facade.discover(analysis, paper_path=paper_path)

    def plan(
        self,
        analysis: PaperReproductionAnalysis | None = None,
        discovery: ResearchResourceDiscovery | None = None,
        *,
        paper_path: Path | str | None = None,
    ) -> ExecutionStrategy:
        """Run execution planning only."""
        if paper_path is not None:
            return self._facade.plan_from_paper(paper_path)
        if analysis is not None and discovery is not None:
            return self._facade.plan(analysis, discovery)
        raise ValueError("Provide paper_path or both analysis and discovery.")

    def execute(
        self,
        execution_strategy: ExecutionStrategy | None = None,
        analysis: PaperReproductionAnalysis | None = None,
        *,
        strategy_path: Path | str | None = None,
        analysis_path: Path | str | None = None,
    ) -> ExecuteResult:
        """Execute implementation and runtime for an existing strategy."""
        if strategy_path is not None and analysis_path is not None:
            return self._facade.execute_from_paths(strategy_path, analysis_path)
        if execution_strategy is not None and analysis is not None:
            return self._facade.execute(execution_strategy, analysis)
        raise ValueError(
            "Provide execution_strategy and analysis, or strategy_path and analysis_path."
        )

    def doctor(self) -> DoctorReport:
        """Validate runtime environment and platform prerequisites."""
        return self._facade.doctor()

    def init(self, *, workspace_root: Path | str | None = None) -> InitReport:
        """Initialize a Man1Lab workspace without overwriting existing user files."""
        return self._facade.init(workspace_root=workspace_root)

    def version(self) -> str:
        """Return the platform version."""
        return self._facade.version()

    def configuration(self) -> dict[str, Any]:
        """Return effective runtime configuration."""
        return self._facade.configuration()
