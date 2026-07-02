"""Man1Lab platform facade — the only public entry to the platform."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from adapters import build_document_parser
from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from application.lifecycle import (
    DoctorCheck,
    DoctorReport,
    InitReport,
    init_workspace,
    run_doctor_checks,
)
from application.version import PLATFORM_VERSION
from configuration.bootstrap import initialize_app_configuration
from configuration.models import AppSettings
from discovery.empty import build_empty_discovery
from discovery.workflow import DiscoveryWorkflow
from execution_planning.workflow import ExecutionPlanningWorkflow
from llm.factory import build_llm_provider, build_planner_llm_provider
from models.execution import ExecutionResult
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.report import ReportModel
from models.research_resource_discovery import ResearchResourceDiscovery
from models.task import TaskModel
from models.workspace import Workspace
from planning.patch_planner import PatchPlanner
from tracking.bootstrap import initialize_experiment_tracking
from tracking.protocol import ExperimentTracker
from tracking.workflow import TrackedWorkflowOrchestrator
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class ExecuteResult:
    """Outcome of executing a committed strategy through implementation and runtime."""

    task: TaskModel
    workspace: Workspace
    execution_result: ExecutionResult


class Man1Lab:
    """Unified platform entry — composes workflow and capabilities without business logic."""

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        initialize_configuration: bool = True,
        configure_logging: bool = True,
        orchestrator: WorkflowOrchestrator | None = None,
        reporter: Reporter | None = None,
    ) -> None:
        if initialize_configuration:
            self._settings = settings or initialize_app_configuration()
        else:
            self._settings = settings or _settings_from_config_module()

        if configure_logging:
            self._configure_logging()

        self._tracker = initialize_experiment_tracking(self._settings)
        self._workspace_manager = WorkspaceManager(
            root=self._settings.workspace_root,
            outputs_dir=self._settings.outputs_dir,
        )
        self._llm = build_llm_provider()
        self._reader, self._planner, self._coder, self._runner = self._build_agents()
        self._discovery_workflow = DiscoveryWorkflow.default()
        self._execution_planning_workflow = ExecutionPlanningWorkflow.default()
        self._orchestrator = orchestrator or self._build_orchestrator(reporter=reporter)

    def reproduce(self, paper_path: Path | str | None = None) -> ReportModel:
        """Run the complete reproduction workflow."""
        path = self._resolve_paper_path(paper_path)
        self._ensure_paper_exists(path)
        return self._orchestrator.run(path)

    def analyze(self, paper_path: Path | str) -> PaperReproductionAnalysis:
        """Run analysis (Reader) only."""
        path = Path(paper_path)
        self._ensure_paper_exists(path)
        with self._tracker.start_run(
            run_name=path.stem,
            tags={"entry": "facade", "operation": "analyze"},
        ):
            return self._reader.run(path)

    def discover(
        self,
        analysis: PaperReproductionAnalysis | None = None,
        *,
        paper_path: Path | str | None = None,
    ) -> ResearchResourceDiscovery:
        """Run discovery only."""
        resolved_analysis = analysis or self.analyze(self._require_paper_path(paper_path))
        with self._tracker.start_run(
            run_name="discovery",
            tags={"entry": "facade", "operation": "discover"},
        ):
            return self._run_discovery(resolved_analysis)

    def plan(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> ExecutionStrategy:
        """Run execution planning only."""
        with self._tracker.start_run(
            run_name="execution-planning",
            tags={"entry": "facade", "operation": "plan"},
        ):
            return self._execution_planning_workflow.run(analysis, discovery)

    def plan_from_paper(self, paper_path: Path | str) -> ExecutionStrategy:
        """Run analyze, discover, and plan for a paper path."""
        path = Path(paper_path)
        self._ensure_paper_exists(path)
        analysis = self.analyze(path)
        discovery = self.discover(analysis)
        return self.plan(analysis, discovery)

    def execute(
        self,
        execution_strategy: ExecutionStrategy,
        analysis: PaperReproductionAnalysis,
    ) -> ExecuteResult:
        """Execute implementation and runtime for an existing strategy."""
        with self._tracker.start_run(
            run_name="execute",
            tags={"entry": "facade", "operation": "execute"},
        ):
            task = self._planner.run(execution_strategy)
            workspace = self._coder.run(analysis, task)
            execution_result = self._runner.run(workspace)
            return ExecuteResult(
                task=task,
                workspace=workspace,
                execution_result=execution_result,
            )

    def execute_from_paths(
        self,
        strategy_path: Path | str,
        analysis_path: Path | str,
    ) -> ExecuteResult:
        """Execute from serialized strategy and analysis artifacts."""
        strategy = ExecutionStrategy.model_validate_json(
            Path(strategy_path).read_text(encoding="utf-8")
        )
        analysis = PaperReproductionAnalysis.model_validate_json(
            Path(analysis_path).read_text(encoding="utf-8")
        )
        return self.execute(strategy, analysis)

    def init(self, *, workspace_root: Path | str | None = None) -> InitReport:
        """Initialize a Man1Lab workspace without overwriting existing user files."""
        root = Path(workspace_root) if workspace_root is not None else None
        return init_workspace(self._settings, workspace_root=root)

    def doctor(self) -> DoctorReport:
        """Validate runtime environment and platform prerequisites."""
        return run_doctor_checks(self._settings)

    def version(self) -> str:
        """Return the platform version."""
        return PLATFORM_VERSION

    def configuration(self) -> dict[str, Any]:
        """Return effective runtime configuration."""
        return _settings_to_dict(self._settings)

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def experiment_tracker(self) -> ExperimentTracker:
        return self._tracker

    def _build_agents(self) -> tuple[Reader, Planner, Coder, Runner]:
        reader = Reader(document_parser=build_document_parser(), llm=self._llm)
        planner = Planner(llm=build_planner_llm_provider())
        coder = Coder(workspace_manager=self._workspace_manager, llm=self._llm)
        runner = Runner()
        return reader, planner, coder, runner

    def _build_orchestrator(self, *, reporter: Reporter | None = None) -> WorkflowOrchestrator:
        patch_planner = PatchPlanner(llm=self._llm)
        reviewer = Reviewer(llm=self._llm, patch_planner=patch_planner)
        return TrackedWorkflowOrchestrator(
            reader=self._reader,
            planner=self._planner,
            coder=self._coder,
            runner=self._runner,
            reviewer=reviewer,
            reporter=reporter or Reporter(),
            workspace_manager=self._workspace_manager,
            patch_planner=patch_planner,
            discovery_workflow=self._discovery_workflow,
            execution_planning_workflow=self._execution_planning_workflow,
            discovery_enabled=self._settings.discovery.enabled,
            execution_planning_enabled=self._settings.execution_planning.enabled,
            experiment_tracker=self._tracker,
        )

    def _run_discovery(self, analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
        if not self._settings.discovery.enabled:
            return build_empty_discovery(analysis)
        return self._discovery_workflow.run(analysis)

    def _configure_logging(self) -> None:
        self._settings.logs_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, self._settings.logging.level.upper(), logging.INFO),
            format=self._settings.logging.format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self._settings.logs_dir / "workflow.log"),
            ],
            force=True,
        )

    def _resolve_paper_path(self, paper_path: Path | str | None) -> Path:
        if paper_path is not None:
            return Path(paper_path)
        return self._settings.paper_path

    def _require_paper_path(self, paper_path: Path | str | None) -> Path:
        if paper_path is None:
            raise ValueError("paper_path is required when analysis is not provided.")
        return Path(paper_path)

    def _ensure_paper_exists(self, paper_path: Path) -> None:
        if not paper_path.exists():
            raise FileNotFoundError(
                f"Paper not found: {paper_path}. Set PAPER_PATH or provide paper_path."
            )


def _settings_from_config_module() -> AppSettings:
    from configuration.legacy_provider import LegacySettingsProvider

    return LegacySettingsProvider().get_settings()


def _settings_to_dict(settings: AppSettings) -> dict[str, Any]:
    data = asdict(settings)
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)
        elif hasattr(value, "__dataclass_fields__"):
            nested = asdict(value)
            data[key] = {
                nested_key: str(nested_value) if isinstance(nested_value, Path) else nested_value
                for nested_key, nested_value in nested.items()
            }
    return data
