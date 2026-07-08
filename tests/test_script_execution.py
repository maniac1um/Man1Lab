import os
import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.planner import Planner
from agents.reader import Reader
from agents.reporter import Reporter
from agents.reviewer import Reviewer
from agents.runner import Runner
from execution.execution_planner import ExecutionPlanner, TRAIN_SCRIPT
from models.workspace import Workspace
from services.environment_service import EnvironmentService, VENV_DIRNAME
from services.exceptions import ExecutionPlanError
from services.execution_service import LOG_FILENAME, ExecutionService
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import failing_train_command_runner, mock_command_runner
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


def _workspace_with_train_script(root: Path) -> Workspace:
    workspace = Workspace(root_path=root, paper_slug="test_paper")
    root.mkdir(parents=True, exist_ok=True)
    (root / "requirements.txt").write_text("numpy>=1.24.0\n", encoding="utf-8")
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "train.py").write_text(
        'def main() -> None:\n    print("Training complete.")\n',
        encoding="utf-8",
    )
    (root / "logs").mkdir(parents=True, exist_ok=True)
    venv_scripts = root / VENV_DIRNAME / ("Scripts" if os.name == "nt" else "bin")
    venv_scripts.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (venv_scripts / python_name).write_text("", encoding="utf-8")
    return workspace


class ExecutionPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._workspace_root = Path(self._temp_dir.name) / "workspace"
        self._planner = ExecutionPlanner()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_successful_execution_plan_generation(self) -> None:
        workspace = _workspace_with_train_script(self._workspace_root)
        plan = self._planner.plan(workspace)

        scripts_dir = "Scripts" if os.name == "nt" else "bin"
        python_name = "python.exe" if os.name == "nt" else "python"
        expected_python = workspace.root_path / VENV_DIRNAME / scripts_dir / python_name
        self.assertEqual(plan.command, [str(expected_python), TRAIN_SCRIPT])
        self.assertEqual(plan.working_directory, workspace.root_path.resolve())
        self.assertEqual(
            plan.environment_variables["VIRTUAL_ENV"],
            str(workspace.root_path / VENV_DIRNAME),
        )

    def test_missing_train_py_raises(self) -> None:
        workspace = Workspace(root_path=self._workspace_root, paper_slug="test_paper")
        self._workspace_root.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(ExecutionPlanError):
            self._planner.plan(workspace)


class ExecutionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._workspace_root = Path(self._temp_dir.name) / "workspace"
        self._planner = ExecutionPlanner()
        self._service = ExecutionService(command_runner=mock_command_runner)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_successful_script_execution(self) -> None:
        workspace = _workspace_with_train_script(self._workspace_root)
        plan = self._planner.plan(workspace)

        result = self._service.execute(plan, workspace)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Training complete.", result.stdout)
        self.assertEqual(result.executed_command, " ".join(plan.command))
        self.assertEqual(result.workspace_path, workspace.root_path.resolve())

    def test_execution_failure(self) -> None:
        workspace = _workspace_with_train_script(self._workspace_root)
        plan = self._planner.plan(workspace)
        service = ExecutionService(command_runner=failing_train_command_runner)

        result = service.execute(plan, workspace)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("training failed", result.stderr)

    def test_execution_log_generation(self) -> None:
        workspace = _workspace_with_train_script(self._workspace_root)
        plan = self._planner.plan(workspace)
        self._service.execute(plan, workspace)

        log_path = workspace.root_path / "logs" / LOG_FILENAME
        self.assertTrue(log_path.is_file())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn("Command:", content)
        self.assertIn("Duration:", content)
        self.assertIn("Exit code:", content)
        self.assertIn("Stdout:", content)
        self.assertIn("Training complete.", content)


class ScriptExecutionWorkflowTest(unittest.TestCase):
    def test_workflow_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)

            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
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
                reporter=Reporter(),
                workspace_manager=workspace_manager,
            )

            report = orchestrator.run(paper_path)

            self.assertTrue(report.final_status)
            self.assertIsNotNone(report.report_path)


if __name__ == "__main__":
    unittest.main()
