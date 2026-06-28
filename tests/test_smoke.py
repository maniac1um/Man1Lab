import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from services.pdf_service import PDFService
from tests.fixtures import create_sample_paper_pdf
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager


class SmokeTest(unittest.TestCase):
    def test_orchestrator_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)

            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            reader = Reader(pdf_service=PDFService())

            orchestrator = WorkflowOrchestrator(
                reader=reader,
                planner=Planner(),
                coder=Coder(workspace_manager=workspace_manager),
                runner=Runner(),
                reviewer=Reviewer(),
                reporter=Reporter(),
                workspace_manager=workspace_manager,
            )

            report = orchestrator.run(paper_path)

            self.assertTrue(report.final_status)
            self.assertIsNotNone(report.report_path)
            self.assertTrue(report.report_path.exists())


if __name__ == "__main__":
    unittest.main()
