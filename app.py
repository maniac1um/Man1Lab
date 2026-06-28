import logging
import os
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


def main() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOGS_DIR / "workflow.log"),
        ],
    )

    paper_path = Path(os.getenv("PAPER_PATH", "paper.pdf"))
    if not paper_path.exists():
        raise FileNotFoundError(
            f"Paper not found: {paper_path}. Set PAPER_PATH or place paper.pdf in the project root."
        )

    llm = build_llm_provider()
    patch_planner = PatchPlanner(llm=llm)
    workspace_manager = WorkspaceManager()
    reader = Reader(pdf_service=PDFService(), llm=llm)
    planner = Planner(llm=build_planner_llm_provider())
    coder = Coder(workspace_manager=workspace_manager, llm=llm)
    runner = Runner()
    reviewer = Reviewer(llm=llm, patch_planner=patch_planner)
    reporter = Reporter()

    orchestrator = WorkflowOrchestrator(
        reader=reader,
        planner=planner,
        coder=coder,
        runner=runner,
        reviewer=reviewer,
        reporter=reporter,
        workspace_manager=workspace_manager,
        patch_planner=patch_planner,
    )

    report = orchestrator.run(paper_path)
    print(f"Workflow complete. Final status: {report.final_status}")
    print(f"Report written to: {report.report_path}")


if __name__ == "__main__":
    main()
