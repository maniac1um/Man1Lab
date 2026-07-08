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
from models.execution import ExecutionResult
from models.verification import VERIFICATION_FAIL, VERIFICATION_PASS
from models.workspace import Workspace
from services.environment_service import EnvironmentService, LOG_FILENAME as ENV_LOG
from services.environment_service import VENV_DIRNAME
from services.execution_service import LOG_FILENAME as EXEC_LOG, ExecutionService
from llm.mock_provider import MOCK_REVIEWER_FAIL_JSON, MockLLMProvider
from adapters.pymupdf_parser import PyMuPDFParser
from services.verification_service import VerificationService
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import failing_train_command_runner, mock_command_runner
from workflow.orchestrator import WorkflowOrchestrator
from workspace.manager import REPOSITORY_SUBDIRS, WorkspaceManager
from tests.support.prompt import default_prompt_builder


def _write_environment_log(workspace_path: Path, *, success: bool) -> None:
    logs_dir = workspace_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    status = "SUCCESS" if success else "FAILED"
    (logs_dir / ENV_LOG).write_text(
        f"Environment preparation started\nStatus: {status}\n",
        encoding="utf-8",
    )


def _write_execution_log(workspace_path: Path) -> None:
    logs_dir = workspace_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / EXEC_LOG).write_text(
        "Script execution started\nStatus: SUCCESS\n",
        encoding="utf-8",
    )


def _create_venv(workspace_path: Path) -> None:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    venv_scripts = workspace_path / VENV_DIRNAME / scripts_dir
    venv_scripts.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (venv_scripts / python_name).write_text("", encoding="utf-8")


def _valid_workspace(root: Path) -> Workspace:
    workspace = Workspace(root_path=root, paper_slug="test_paper")
    root.mkdir(parents=True, exist_ok=True)
    for subdir in REPOSITORY_SUBDIRS:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Test Paper\n", encoding="utf-8")
    (root / "requirements.txt").write_text("numpy>=1.24.0\n", encoding="utf-8")
    (root / "scripts" / "train.py").write_text(
        'def main() -> None:\n    print("Training complete.")\n',
        encoding="utf-8",
    )
    _create_venv(root)
    _write_environment_log(root, success=True)
    _write_execution_log(root)
    return workspace


def _successful_execution_result(workspace: Workspace) -> ExecutionResult:
    return ExecutionResult(
        exit_code=0,
        stdout="Training complete.\n",
        stderr="",
        executed_command=f"{workspace.root_path / VENV_DIRNAME / 'bin' / 'python'} scripts/train.py",
        execution_time_seconds=0.1,
        workspace_path=workspace.root_path.resolve(),
    )


class VerificationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace"
        self._service = VerificationService()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_successful_verification(self) -> None:
        workspace = _valid_workspace(self._root)
        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.overall_status, VERIFICATION_PASS)
        self.assertEqual(result.repository_status, VERIFICATION_PASS)
        self.assertEqual(result.environment_status, VERIFICATION_PASS)
        self.assertEqual(result.execution_status, VERIFICATION_PASS)
        self.assertEqual(result.output_status, VERIFICATION_PASS)
        self.assertEqual(result.findings, [])

    def test_missing_repository_files(self) -> None:
        workspace = _valid_workspace(self._root)
        (self._root / "README.md").unlink()

        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.repository_status, VERIFICATION_FAIL)
        self.assertEqual(result.overall_status, VERIFICATION_FAIL)
        self.assertTrue(
            any(finding.code == "missing_file" for finding in result.findings)
        )

    def test_missing_virtual_environment(self) -> None:
        workspace = _valid_workspace(self._root)
        import shutil

        shutil.rmtree(self._root / VENV_DIRNAME)

        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.environment_status, VERIFICATION_FAIL)
        self.assertTrue(
            any(
                finding.code == "missing_virtual_environment"
                for finding in result.findings
            )
        )

    def test_execution_failure(self) -> None:
        workspace = _valid_workspace(self._root)
        execution_result = ExecutionResult(
            exit_code=1,
            stdout="",
            stderr="training failed\n",
            executed_command="python scripts/train.py",
            execution_time_seconds=0.1,
            workspace_path=workspace.root_path.resolve(),
        )

        result = self._service.verify(workspace, execution_result)

        self.assertEqual(result.execution_status, VERIFICATION_FAIL)
        self.assertTrue(
            any(finding.code == "nonzero_exit_code" for finding in result.findings)
        )

    def test_missing_execution_log(self) -> None:
        workspace = _valid_workspace(self._root)
        (self._root / "logs" / EXEC_LOG).unlink()

        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.execution_status, VERIFICATION_FAIL)
        self.assertTrue(
            any(finding.code == "missing_execution_log" for finding in result.findings)
        )

    def test_missing_outputs_directory(self) -> None:
        workspace = _valid_workspace(self._root)
        import shutil

        shutil.rmtree(self._root / "outputs")

        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.output_status, VERIFICATION_FAIL)
        self.assertTrue(
            any(
                finding.code == "missing_outputs_directory"
                for finding in result.findings
            )
        )

    def test_overall_verification_status_fails_when_any_category_fails(self) -> None:
        workspace = _valid_workspace(self._root)
        (self._root / "requirements.txt").unlink()

        result = self._service.verify(workspace, _successful_execution_result(workspace))

        self.assertEqual(result.repository_status, VERIFICATION_FAIL)
        self.assertEqual(result.overall_status, VERIFICATION_FAIL)


class VerificationWorkflowTest(unittest.TestCase):
    def test_workflow_execution_includes_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)

            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            captured_history: list = []

            class CapturingReporter(Reporter):
                def run(self, history):
                    captured_history.append(history)
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

            self.assertEqual(len(captured_history), 1)
            history = captured_history[0]
            self.assertEqual(len(history.verification_results), 1)
            self.assertEqual(
                history.verification_results[0].overall_status,
                VERIFICATION_PASS,
            )
            self.assertEqual(len(history.review_reports), 1)
            self.assertEqual(history.review_reports[0].risk_level, "LOW")
            self.assertEqual(len(history.patch_plans), 1)
            self.assertFalse(history.patch_plans[0].requires_patch)
            self.assertTrue(report.report_path.exists())

    def test_workflow_verification_fails_on_execution_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            paper_path = temp_path / "paper.pdf"
            create_sample_paper_pdf(paper_path)

            workspace_manager = WorkspaceManager(
                root=temp_path / "workspace/tasks",
                outputs_dir=temp_path / "outputs",
            )
            captured_history: list = []

            class CapturingReporter(Reporter):
                def run(self, history):
                    captured_history.append(history)
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
                        command_runner=failing_train_command_runner
                    ),
                ),
                reviewer=Reviewer(
                    prompt_builder=default_prompt_builder(),
                    llm=MockLLMProvider(MOCK_REVIEWER_FAIL_JSON),
                ),
                reporter=CapturingReporter(),
                workspace_manager=workspace_manager,
            )

            orchestrator.run(paper_path)

            self.assertEqual(
                captured_history[0].verification_results[0].overall_status,
                VERIFICATION_FAIL,
            )
            self.assertEqual(len(captured_history[0].review_reports), 1)
            self.assertEqual(
                captured_history[0].review_reports[0].risk_level,
                "HIGH",
            )
            self.assertEqual(len(captured_history[0].patch_plans), 1)


if __name__ == "__main__":
    unittest.main()
