import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.task import TaskModel
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import mock_command_runner
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


class PipelineIntegrationTest(unittest.TestCase):
    def test_orchestrator_runs_pdf_to_analysis_task_coder_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)

            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            captured: dict[str, object] = {}

            class CapturingReporter(Reporter):
                def run(self, history):
                    captured["history"] = history
                    return super().run(history)

            orchestrator = WorkflowOrchestrator(
                reader=Reader(document_parser=PyMuPDFParser(), prompt_builder=default_prompt_builder()),
                planner=Planner(prompt_builder=default_prompt_builder()),
                coder=Coder(workspace_manager=workspace_manager, prompt_builder=default_prompt_builder()),
                runner=Runner(
                    environment_service=EnvironmentService(
                        command_runner=mock_command_runner
                    ),
                    execution_service=ExecutionService(
                        command_runner=mock_command_runner
                    ),
                ),
                reviewer=Reviewer(prompt_builder=default_prompt_builder()),
                reporter=CapturingReporter(),
                workspace_manager=workspace_manager,
            )
            report = orchestrator.run(paper_path)

            history = captured["history"]
            self.assertIsInstance(history.analysis, PaperReproductionAnalysis)
            self.assertIsInstance(history.task, TaskModel)
            self.assertIsNotNone(history.workspace)
            self.assertIn("Diffusion Policy", history.analysis.metadata.title)
            self.assertGreater(len(history.task.steps), 0)
            self.assertTrue((history.workspace.root_path / "scripts" / "train.py").exists())
            self.assertIsNotNone(report.report_path)
            self.assertTrue(report.report_path.exists())


if __name__ == "__main__":
    unittest.main()
