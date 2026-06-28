#!/usr/bin/env python3
"""M7.1 end-to-end integration runner. Does not modify pipeline APIs."""

import json
import logging
import sys
import time
from pathlib import Path

import config
from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from llm.factory import build_llm_provider, build_planner_llm_provider
from planning.patch_planner import PatchPlanner
from services.pdf_service import PDFService
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager

PAPER_PATH = Path(__file__).resolve().parent.parent / "1512.03385v1.pdf"
INTEGRATION_LOG = config.LOGS_DIR / "integration_m7_1.log"


def main() -> int:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(INTEGRATION_LOG, mode="w"),
        ],
    )

    if not PAPER_PATH.exists():
        logging.error("Paper not found: %s", PAPER_PATH)
        return 1

    captured_history = []
    failure: dict | None = None
    report = None
    start = time.perf_counter()

    class CapturingReporter(Reporter):
        def run(self, history):
            captured_history.append(history)
            return super().run(history)

    try:
        llm = build_llm_provider()
        patch_planner = PatchPlanner(llm=llm)
        workspace_manager = WorkspaceManager()
        orchestrator = WorkflowOrchestrator(
            reader=Reader(pdf_service=PDFService(), llm=llm),
            planner=Planner(llm=build_planner_llm_provider()),
            coder=Coder(workspace_manager=workspace_manager, llm=llm),
            runner=Runner(),
            reviewer=Reviewer(llm=llm, patch_planner=patch_planner),
            reporter=CapturingReporter(),
            workspace_manager=workspace_manager,
            patch_planner=patch_planner,
        )
        report = orchestrator.run(PAPER_PATH)
    except Exception as exc:
        failure = {
            "stage": _last_stage(captured_history),
            "error": type(exc).__name__,
            "message": str(exc),
        }
        logging.exception("Integration run failed")

    duration = time.perf_counter() - start
    snapshot_path = config.OUTPUTS_DIR / "integration_m7_1_snapshot.json"
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            _build_snapshot(
                paper_path=PAPER_PATH,
                history=captured_history[0] if captured_history else None,
                report=report,
                failure=failure,
                duration_seconds=duration,
            ),
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    if failure:
        print(f"Integration FAILED at stage: {failure['stage']}")
        print(f"Error: {failure['message']}")
        return 1

    print(f"Integration complete in {duration:.2f}s")
    print(f"Final status: {report.final_status}")
    print(f"Report: {report.report_path}")
    print(f"Snapshot: {snapshot_path}")
    return 0


def _last_stage(captured_history: list) -> str:
    if not captured_history:
        return "unknown"
    stages = captured_history[0].stages
    if not stages:
        return "unknown"
    return stages[-1].agent_name


def _build_snapshot(*, paper_path, history, report, failure, duration_seconds):
    data = {
        "paper_path": str(paper_path),
        "duration_seconds": duration_seconds,
        "openai_configured": bool(config.OPENAI_API_KEY),
        "failure": failure,
    }
    if history is not None:
        data["stages"] = [stage.model_dump() for stage in history.stages]
        data["paper"] = history.paper.model_dump(mode="json") if history.paper else None
        data["task"] = history.task.model_dump(mode="json") if history.task else None
        data["workspace"] = (
            {
                "root_path": str(history.workspace.root_path),
                "paper_slug": history.workspace.paper_slug,
            }
            if history.workspace
            else None
        )
        data["execution_results"] = [
            item.model_dump(mode="json") for item in history.execution_results
        ]
        data["verification_results"] = [
            item.model_dump(mode="json") for item in history.verification_results
        ]
        data["review_reports"] = [
            item.model_dump(mode="json") for item in history.review_reports
        ]
        data["patch_plans"] = [
            item.model_dump(mode="json") for item in history.patch_plans
        ]
    if report is not None:
        data["final_report"] = report.model_dump(mode="json")
    return data


if __name__ == "__main__":
    sys.exit(main())
