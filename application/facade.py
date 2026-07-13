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
from application.platform_execution import (
    ExecutionReportView,
    ExecutionRunOutcome,
    ExecutionStatusView,
    PlatformExecutionService,
)
from application.lifecycle import (
    CleanPolicy,
    CleanupReport,
    DoctorReport,
    InitReport,
    clean_workspace,
    init_workspace,
    run_doctor_checks,
)
from application.lifecycle.init_wizard import InitWizardRequest, resolve_wizard_profile, write_api_key_to_env
from application.lifecycle.llm_doctor import run_llm_doctor_checks
from application.version import PLATFORM_VERSION
from configuration.models import AppSettings
from discovery.empty import build_empty_discovery
from discovery.workflow import DiscoveryWorkflow
from execution_planning.workflow import ExecutionPlanningWorkflow
from llm.compat import LLMManagerCompleteAdapter
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.provider import LLMProvider
from application.runtime.accessors import RuntimeInfrastructure
from application.runtime.resource_wiring import wire_runtime_resources
from prompt.builder import PromptBuilder
from providers.llm.manager import LLMManager
from providers.llm.model_management import (
    CurrentModelReport,
    ModelChangeReport,
    ModelListReport,
    ModelTestReport,
)
from providers.llm.models import RegistryValidationResult
from providers.llm.persistence import ModelImportReport
from runtime.profiling.report import RuntimeProfile
from runtime.runtime import PlatformRuntime
from runtime.session import RuntimeSession
from runtime.session.workspace_store import WorkspaceArtifactStore
from runtime.state import RuntimeState
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
class ModelSetupReport:
    successful: bool
    message: str
    profile_name: str = ""
    provider: str = ""
    model: str = ""


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
        runtime: PlatformRuntime | None = None,
        platform_execution: PlatformExecutionService | None = None,
    ) -> None:
        self._runtime = runtime or PlatformRuntime()
        if self._runtime.state is RuntimeState.NEW:
            self._runtime.startup()

        wire_runtime_resources(
            self._runtime.context.resources,
            settings=settings,
            initialize_configuration=initialize_configuration,
        )
        infrastructure = RuntimeInfrastructure(self._runtime.context.resources)
        self._settings = infrastructure.configuration()

        if configure_logging:
            self._configure_logging()

        self._tracker = initialize_experiment_tracking(self._settings)
        self._workspace_manager = WorkspaceManager(
            root=self._settings.workspace_root,
            outputs_dir=self._settings.outputs_dir,
        )
        self._prompt_builder = PromptBuilder(infrastructure.prompt_registry())
        self._llm = self._build_llm_port()
        self._reader, self._planner, self._coder, self._runner = self._build_agents()
        self._discovery_workflow = DiscoveryWorkflow.default()
        self._execution_planning_workflow = ExecutionPlanningWorkflow.default()
        self._orchestrator = orchestrator or self._build_orchestrator(reporter=reporter)
        self._platform_execution = platform_execution or PlatformExecutionService(
            self._runtime.context,
            self._settings.workspace_root,
        )

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
            store = WorkspaceArtifactStore(self.settings.workspace_root)
            cached_text = store.load_parsed_document(path)
            if store.has_analysis():
                loaded = store.load_analysis()
                if loaded is not None:
                    return loaded
            if cached_text is not None:
                return self._reader.run_analysis(path, paper_text=cached_text)
            text = self._reader.read_text(path)
            store.save_parsed_document(path, text)
            return self._reader.run_analysis(path, paper_text=text)

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

    def run_execution(
        self,
        *,
        run_id: str | None = None,
        resume: bool = True,
    ) -> ExecutionRunOutcome:
        """Execute the planned execution graph in the current workspace."""
        with self._tracker.start_run(
            run_name="run-execution",
            tags={"entry": "facade", "operation": "run_execution"},
        ):
            outcome = self._platform_execution.run_execution(
                run_id=run_id,
                resume=resume,
                workspace_ref=str(self._settings.workspace_root),
            )
            self._runtime.session.workspace.current_execution_run_id = outcome.run_id
            return outcome

    def execution_status(self, run_id: str | None = None) -> ExecutionStatusView:
        """Return durable status for the current or specified execution run."""
        resolved_run_id = run_id or self._runtime.session.workspace.current_execution_run_id
        if resolved_run_id is None:
            raise ValueError("No execution run is selected. Run execute first or pass run_id.")
        return self._platform_execution.execution_status(resolved_run_id)

    def execution_report(self, run_id: str | None = None) -> ExecutionReportView:
        """Return the execution report for the current or specified run."""
        resolved_run_id = run_id or self._runtime.session.workspace.current_execution_run_id
        if resolved_run_id is None:
            raise ValueError("No execution run is selected. Run execute first or pass run_id.")
        return self._platform_execution.execution_report(resolved_run_id)

    def init(
        self,
        *,
        workspace_root: Path | str | None = None,
    ) -> InitReport:
        """Initialize a Man1Lab workspace without overwriting existing user files."""
        root = Path(workspace_root) if workspace_root is not None else None
        return init_workspace(self._settings, workspace_root=root)

    def setup_first_model(
        self,
        request: InitWizardRequest,
        *,
        workspace_root: Path | str | None = None,
    ) -> ModelSetupReport:
        """Configure and activate the first model profile during initialization."""
        root = Path(workspace_root) if workspace_root is not None else Path.cwd()
        resolved = resolve_wizard_profile(request)
        try:
            write_api_key_to_env(root / ".env", resolved.api_key_reference, request.api_key)
        except ValueError as exc:
            return ModelSetupReport(successful=False, message=str(exc))

        add_report = self.add_model(
            profile_name=resolved.profile_name,
            provider=resolved.provider,
            model=resolved.model,
            base_url=resolved.base_url,
            api_key_reference=resolved.api_key_reference,
            temperature=resolved.temperature,
            max_tokens=resolved.max_tokens,
            description=resolved.description,
            enabled=True,
        )
        if not add_report.successful:
            return ModelSetupReport(
                successful=False,
                message=add_report.message,
                profile_name=resolved.profile_name,
                provider=resolved.provider,
                model=resolved.model,
            )

        use_report = self.use_model(resolved.profile_name)
        if not use_report.successful:
            return ModelSetupReport(
                successful=False,
                message=use_report.message,
                profile_name=resolved.profile_name,
                provider=resolved.provider,
                model=resolved.model,
            )

        self._llm = self._build_llm_port()
        return ModelSetupReport(
            successful=True,
            message="First model profile configured.",
            profile_name=resolved.profile_name,
            provider=resolved.provider,
            model=resolved.model,
        )

    def doctor(self) -> DoctorReport:
        """Validate runtime environment and platform prerequisites."""
        base_report = run_doctor_checks(self._settings)
        llm_checks = run_llm_doctor_checks(self._llm_manager)
        checks = list(base_report.checks) + llm_checks
        healthy = all(check.status != "fail" for check in checks)
        return DoctorReport(healthy=healthy, checks=checks)

    def clean(
        self,
        *,
        policy: CleanPolicy = CleanPolicy.SAFE,
        dry_run: bool = False,
        project_root: Path | str | None = None,
    ) -> CleanupReport:
        """Remove regeneratable workspace artifacts according to cleanup policy."""
        root = Path(project_root) if project_root is not None else None
        return clean_workspace(
            self._settings,
            policy=policy,
            dry_run=dry_run,
            project_root=root,
        )

    def version(self) -> str:
        """Return the platform version."""
        return PLATFORM_VERSION

    def configuration(self) -> dict[str, Any]:
        """Return effective runtime configuration."""
        return _settings_to_dict(self._settings)

    @property
    def runtime(self) -> PlatformRuntime:
        """Return the platform runtime lifecycle owner."""
        return self._runtime

    def is_runtime_ready(self) -> bool:
        """Return whether the platform runtime is ready."""
        return self._runtime.is_ready()

    def shutdown_runtime(self) -> None:
        """Shut down the platform runtime lifecycle."""
        self._runtime.shutdown()

    def session(self) -> RuntimeSession:
        """Return the runtime session for user interaction lifetime."""
        return self._runtime.session

    def is_session_active(self) -> bool:
        """Return whether the runtime session is active."""
        return self._runtime.is_session_active()

    def close_session(self) -> None:
        """Close the active runtime session."""
        self._runtime.close_session()

    @staticmethod
    def profile_startup() -> RuntimeProfile:
        """Profile platform startup and runtime initialization."""
        from application.runtime.startup_profile import profile_platform_startup

        return profile_platform_startup()

    def run_startup_profile(self) -> RuntimeProfile:
        """Profile platform startup (instance entry for console and SDK)."""
        return self.profile_startup()

    @property
    def _llm_manager(self) -> LLMManager:
        return RuntimeInfrastructure(self._runtime.context.resources).llm_manager()

    def list_models(self) -> ModelListReport:
        """List configured model profiles."""
        return self._llm_manager.list_models()

    def current_model(self) -> CurrentModelReport | None:
        """Return the active model profile."""
        return self._llm_manager.current_model()

    def use_model(self, profile_name: str) -> ModelChangeReport:
        """Switch the active model profile."""
        return self._llm_manager.use_model(profile_name)

    def add_model(
        self,
        *,
        profile_name: str,
        provider: str,
        model: str,
        base_url: str = "",
        api_key_reference: str = "OPENAI_API_KEY",
        temperature: float | None = None,
        max_tokens: int | None = None,
        description: str = "",
        enabled: bool = True,
    ) -> ModelChangeReport:
        """Add a model profile to the registry."""
        return self._llm_manager.add_model(
            profile_name=profile_name,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key_reference=api_key_reference,
            temperature=temperature,
            max_tokens=max_tokens,
            description=description,
            enabled=enabled,
        )

    def remove_model(self, profile_name: str, *, force: bool = False) -> ModelChangeReport:
        """Remove a model profile from the registry."""
        return self._llm_manager.remove_model(profile_name, force=force)

    def rename_model(self, old_name: str, new_name: str) -> ModelChangeReport:
        """Rename an existing model profile."""
        return self._llm_manager.rename_model(old_name, new_name)

    def test_model(self, profile_name: str | None = None) -> ModelTestReport:
        """Run a provider health check for a model profile."""
        return self._llm_manager.test_model(profile_name)

    def validate_models(self) -> RegistryValidationResult:
        """Validate configured model profiles."""
        return self._llm_manager.validate_models()

    def export_models(self, path: Path | str) -> Path:
        """Export portable model profile configuration."""
        return self._llm_manager.export_models(Path(path))

    def import_models(
        self,
        path: Path | str,
        *,
        replace: bool = False,
        skip_existing: bool = False,
    ) -> ModelImportReport:
        """Import portable model profile configuration."""
        return self._llm_manager.import_models(
            Path(path),
            replace=replace,
            skip_existing=skip_existing,
        )

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def experiment_tracker(self) -> ExperimentTracker:
        return self._tracker

    def _build_llm_port(self) -> LLMProvider:
        if self._llm_manager.has_active_provider():
            return LLMManagerCompleteAdapter(self._llm_manager)
        logging.warning("OPENAI_API_KEY not set; using MockLLMProvider")
        return MockLLMProvider()

    def _build_planner_llm_port(self) -> LLMProvider:
        if self._llm_manager.has_active_provider():
            return LLMManagerCompleteAdapter(self._llm_manager)
        return MockLLMProvider(MOCK_PLANNER_JSON)

    def _build_agents(self) -> tuple[Reader, Planner, Coder, Runner]:
        reader = Reader(
            document_parser=build_document_parser(),
            llm=self._llm,
            prompt_builder=self._prompt_builder,
        )
        planner = Planner(llm=self._build_planner_llm_port(), prompt_builder=self._prompt_builder)
        coder = Coder(
            workspace_manager=self._workspace_manager,
            llm=self._llm,
            prompt_builder=self._prompt_builder,
        )
        runner = Runner()
        return reader, planner, coder, runner

    def _build_orchestrator(self, *, reporter: Reporter | None = None) -> WorkflowOrchestrator:
        patch_planner = PatchPlanner(llm=self._llm, prompt_builder=self._prompt_builder)
        reviewer = Reviewer(
            llm=self._llm, patch_planner=patch_planner, prompt_builder=self._prompt_builder
        )
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
