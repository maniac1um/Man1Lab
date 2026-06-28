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
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.openai_provider import OpenAIProvider
from services.pdf_service import PDFService
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager


def build_llm_provider():
    if config.OPENAI_API_KEY:
        return OpenAIProvider()
    logging.warning("OPENAI_API_KEY not set; using MockLLMProvider")
    return MockLLMProvider()


def build_planner_llm_provider():
    if config.OPENAI_API_KEY:
        return OpenAIProvider()
    return MockLLMProvider(MOCK_PLANNER_JSON)


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

    workspace_manager = WorkspaceManager()
    reader = Reader(pdf_service=PDFService(), llm=build_llm_provider())
    planner = Planner(llm=build_planner_llm_provider())
    coder = Coder(workspace_manager=workspace_manager)
    runner = Runner()
    reviewer = Reviewer()
    reporter = Reporter()

    orchestrator = WorkflowOrchestrator(
        reader=reader,
        planner=planner,
        coder=coder,
        runner=runner,
        reviewer=reviewer,
        reporter=reporter,
        workspace_manager=workspace_manager,
    )

    report = orchestrator.run(paper_path)
    print(f"Workflow complete. Final status: {report.final_status}")
    print(f"Report written to: {report.report_path}")


if __name__ == "__main__":
    main()
