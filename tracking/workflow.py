"""Workflow tracking wrapper — instruments orchestrator without changing topology."""

from __future__ import annotations

from pathlib import Path

import config
from models.report import ReportModel, WorkflowHistory
from tracking.protocol import ExperimentTracker
from workflow.orchestrator import WorkflowOrchestrator
from workflow.pipeline import PipelineStage


class TrackedWorkflowOrchestrator(WorkflowOrchestrator):
    """Delegates to WorkflowOrchestrator; records one parent run and nested stage runs."""

    def __init__(
        self,
        *args,
        experiment_tracker: ExperimentTracker,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._experiment_tracker = experiment_tracker
        self._stage_count = 0

    def run(self, paper_path: Path) -> ReportModel:
        tracker = self._experiment_tracker
        self._stage_count = 0

        with tracker.start_run(
            run_name=paper_path.stem,
            tags={"paper_path": str(paper_path), "component": "man1lab"},
        ):
            tracker.log_param("paper_path", str(paper_path))
            if config.PARSER_BACKEND is not None:
                tracker.log_param("parser_backend", str(config.PARSER_BACKEND))

            report = super().run(paper_path)

            tracker.set_tag("final_status", report.final_status)
            tracker.log_metric("stage_count", float(self._stage_count))
            if report.report_path and report.report_path.exists():
                tracker.log_artifact(report.report_path)
            return report

    def _run_stage(self, stage: PipelineStage, history: WorkflowHistory, action):
        self._stage_count += 1
        tracker = self._experiment_tracker
        with tracker.start_nested_run(
            name=stage.value,
            tags={"stage": stage.value},
        ):
            result = super()._run_stage(stage, history, action)
            if history.stages:
                last = history.stages[-1]
                tracker.log_metric("duration_seconds", last.duration_seconds)
                tracker.set_tag("status", last.status)
            return result
