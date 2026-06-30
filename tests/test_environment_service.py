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
from models.workspace import Workspace
from services.environment_service import (
    LOG_FILENAME,
    VENV_DIRNAME,
    CommandResult,
    EnvironmentService,
)
from services.execution_service import ExecutionService
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import mock_command_runner
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import WorkspaceManager


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[list[str], Path]] = []

    def __call__(self, command: list[str], cwd: Path) -> CommandResult:
        self.commands.append((list(command), cwd))
        return mock_command_runner(command, cwd)


def _prepared_workspace(root: Path) -> Workspace:
    workspace = Workspace(root_path=root, paper_slug="test_paper")
    root.mkdir(parents=True, exist_ok=True)
    (root / "requirements.txt").write_text("numpy>=1.24.0\n", encoding="utf-8")
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "train.py").write_text("print('train')\n", encoding="utf-8")
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return workspace


class EnvironmentServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._workspace_root = Path(self._temp_dir.name) / "workspace"
        self._recording_runner = RecordingCommandRunner()
        self._service = EnvironmentService(command_runner=self._recording_runner)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_virtual_environment_creation(self) -> None:
        workspace = _prepared_workspace(self._workspace_root)
        result = self._service.prepare(workspace)

        self.assertTrue((workspace.root_path / VENV_DIRNAME).is_dir())
        venv_commands = [
            command for command, _ in self._recording_runner.commands if "venv" in command
        ]
        self.assertEqual(len(venv_commands), 1)
        self.assertEqual(result.exit_code, 0)

    def test_requirements_installation_invoked(self) -> None:
        workspace = _prepared_workspace(self._workspace_root)
        self._service.prepare(workspace)

        pip_commands = [
            command
            for command, _ in self._recording_runner.commands
            if command and Path(command[0]).name.startswith("pip")
        ]
        self.assertEqual(len(pip_commands), 1)
        self.assertIn("install", pip_commands[0])
        self.assertIn("-r", pip_commands[0])
        self.assertTrue(
            any("requirements.txt" in part for part in pip_commands[0])
        )

    def test_log_generation(self) -> None:
        workspace = _prepared_workspace(self._workspace_root)
        self._service.prepare(workspace)

        log_path = workspace.root_path / "logs" / LOG_FILENAME
        self.assertTrue(log_path.is_file())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn("virtual environment creation", content)
        self.assertIn("dependency installation", content)
        self.assertIn("Status: SUCCESS", content)
        self.assertIn("Duration:", content)

    def test_successful_execution_result(self) -> None:
        workspace = _prepared_workspace(self._workspace_root)
        result = self._service.prepare(workspace)

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.workspace_path, workspace.root_path.resolve())
        self.assertIn("venv", result.executed_command)
        self.assertIn("pip install", result.executed_command)
        self.assertGreater(result.execution_time_seconds, 0.0)


class RunnerEnvironmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._workspace_root = Path(self._temp_dir.name) / "workspace"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_runner_returns_execution_result_for_same_workspace(self) -> None:
        workspace = _prepared_workspace(self._workspace_root)
        runner = Runner(
            environment_service=EnvironmentService(command_runner=mock_command_runner),
            execution_service=ExecutionService(command_runner=mock_command_runner),
        )

        result = runner.run(workspace)

        self.assertEqual(result.workspace_path, workspace.root_path.resolve())
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((workspace.root_path / VENV_DIRNAME).is_dir())


class EnvironmentWorkflowTest(unittest.TestCase):
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
                reader=Reader(document_parser=PyMuPDFParser()),
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


if __name__ == "__main__":
    unittest.main()
