import time
from pathlib import Path

import config
from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from models.report import ReportModel, StageRecord, WorkflowHistory
from planning.patch_planner import PatchPlanner
from services.verification_service import VerificationService
from workflow.pipeline import PipelineContext, PipelineStage
from workspace.manager import WorkspaceManager


class WorkflowOrchestrator:
    def __init__(
        self,
        reader: Reader,
        planner: Planner,
        coder: Coder,
        runner: Runner,
        reviewer: Reviewer,
        reporter: Reporter,
        workspace_manager: WorkspaceManager,
        verification_service: VerificationService | None = None,
        patch_planner: PatchPlanner | None = None,
    ) -> None:
        self._reader = reader
        self._planner = planner
        self._coder = coder
        self._runner = runner
        self._reviewer = reviewer
        self._reporter = reporter
        self._workspace_manager = workspace_manager
        self._verification_service = verification_service or VerificationService()
        self._patch_planner = patch_planner or PatchPlanner()

    def run(self, paper_path: Path) -> ReportModel:
        context = PipelineContext(paper_path=str(paper_path))
        history = context.history

        history.paper = self._run_stage(
            PipelineStage.READER,
            history,
            lambda: self._reader.run(paper_path),
        )
        history.task = self._run_stage(
            PipelineStage.PLANNER,
            history,
            lambda: self._planner.run(history.paper),
        )
        history.workspace = self._run_stage(
            PipelineStage.CODER,
            history,
            lambda: self._coder.run(history.paper, history.task),
        )
        execution_result = self._run_stage(
            PipelineStage.RUNNER,
            history,
            lambda: self._runner.run(history.workspace),
        )
        history.execution_results.append(execution_result)

        for _ in range(config.MAX_REVIEW_ITERATIONS):
            verification_result = self._verification_service.verify(
                history.workspace,
                execution_result,
            )
            history.verification_results.append(verification_result)

            review_report = self._run_stage(
                PipelineStage.REVIEWER,
                history,
                lambda: self._reviewer.run(
                    history.paper,
                    history.task,
                    verification_result,
                ),
            )
            history.review_reports.append(review_report)

            patch_plan = self._run_stage(
                PipelineStage.PATCH_PLANNER,
                history,
                lambda: self._patch_planner.plan(review_report),
            )
            history.patch_plans.append(patch_plan)

            if not patch_plan.requires_patch:
                break

            if patch_plan.requires_patch:
                # Workflow iteration deferred to a later integration milestone.
                pass
            break

        report = self._run_stage(
            PipelineStage.REPORTER,
            history,
            lambda: self._reporter.run(history),
        )
        report_path = self._workspace_manager.write_report(report)
        return report.model_copy(update={"report_path": report_path})

    def _run_stage(self, stage: PipelineStage, history: WorkflowHistory, action):
        agent_name = stage.value
        print(f"[{agent_name}] START")
        start = time.perf_counter()
        status = "SUCCESS"
        try:
            result = action()
        except Exception:
            status = "FAILED"
            duration = time.perf_counter() - start
            history.stages.append(
                StageRecord(
                    agent_name=agent_name,
                    status=status,
                    duration_seconds=duration,
                )
            )
            print(f"[{agent_name}] {status} ({duration:.2f}s)")
            raise

        duration = time.perf_counter() - start
        history.stages.append(
            StageRecord(
                agent_name=agent_name,
                status=status,
                duration_seconds=duration,
            )
        )
        print(f"[{agent_name}] {status} ({duration:.2f}s)")
        return result
