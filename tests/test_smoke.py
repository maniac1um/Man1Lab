import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import mock_command_runner
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
            reader = Reader(document_parser=PyMuPDFParser())

            orchestrator = WorkflowOrchestrator(
                reader=reader,
                planner=Planner(),
                coder=Coder(workspace_manager=workspace_manager),
                runner=Runner(
                    environment_service=EnvironmentService(
                        command_runner=mock_command_runner
                    ),
                    execution_service=ExecutionService(
                        command_runner=mock_command_runner
                    ),
                ),
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
