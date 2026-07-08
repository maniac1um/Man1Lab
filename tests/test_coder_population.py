import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.coder_quality import RepositoryAcceptanceError
from llm.coder_mock_provider import MOCK_FILE_CONTENT, CoderMockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from models.task import TaskModel, TaskStep
from agents.runner import Runner
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from adapters.pymupdf_parser import PyMuPDFParser
from tests.fixtures import create_sample_paper_pdf, sample_reproduction_analysis
from tests.runner_mocks import mock_command_runner
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


def _sample_analysis():
    return sample_reproduction_analysis()


_ANALYSIS_SLUG = "diffusion_policy_visuomotor_policy_learning"


def _step(task_id: str, name: str, description: str = "") -> TaskStep:
    return TaskStep(id=task_id, name=name, description=description)


class RecordingLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self._delegate = CoderMockLLMProvider()

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        self.calls.append(messages)
        return self._delegate.complete(messages, temperature=temperature)


class CoderPopulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._workspace_manager = WorkspaceManager(root=self._root)
        self._recording_llm = RecordingLLMProvider()
        self._coder = Coder(workspace_manager=self._workspace_manager, prompt_builder=default_prompt_builder(), llm=self._recording_llm,
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_one_llm_invocation_per_repository_target(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_1", "Environment setup"),
                _step("task_3", "Dataset preparation"),
            ],
        )

        with self.assertRaises(RepositoryAcceptanceError):
            self._coder.run(_sample_analysis(), task)

        self.assertEqual(len(self._recording_llm.calls), 2)

    def test_generated_content_written_through_workspace_manager(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation", "Implement network.")],
        )

        with self.assertRaises(RepositoryAcceptanceError):
            self._coder.run(_sample_analysis(), task)

        content = (
            self._root / _ANALYSIS_SLUG / "src" / "model.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(content, MOCK_FILE_CONTENT["src/model.py"])

    def test_correct_target_file_population(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_1", "Environment setup"),
                _step("task_5", "Training", "Train the model."),
                _step("task_6", "Evaluation", "Evaluate results."),
            ],
        )

        workspace = self._coder.run(_sample_analysis(), task)

        self.assertTrue((workspace.root_path / "requirements.txt").is_file())
        self.assertTrue((workspace.root_path / "scripts/train.py").is_file())
        self.assertTrue((workspace.root_path / "configs/train.yaml").is_file())
        self.assertTrue((workspace.root_path / "scripts/evaluate.py").is_file())
        self.assertFalse((workspace.root_path / "src" / "dataset.py").exists())

    def test_deterministic_repository_population(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_3", "Dataset preparation", "Load data."),
                _step("task_5", "Training", "Train the model."),
            ],
        )

        workspace_one = self._coder.run(_sample_analysis(), task)
        workspace_two = self._coder.run(_sample_analysis(), task)

        dataset_one = self._workspace_manager.read_file(workspace_one, "src/dataset.py")
        dataset_two = self._workspace_manager.read_file(workspace_two, "src/dataset.py")
        config_one = self._workspace_manager.read_file(workspace_one, "configs/dataset.yaml")
        config_two = self._workspace_manager.read_file(workspace_two, "configs/dataset.yaml")

        self.assertEqual(dataset_one, dataset_two)
        self.assertEqual(config_one, config_two)

    def test_rejects_repository_without_training_entrypoint(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation", "Implement network.")],
        )

        with self.assertRaises(RepositoryAcceptanceError):
            self._coder.run(_sample_analysis(), task)

        slug = _ANALYSIS_SLUG
        workspace_root = self._root / slug
        self.assertTrue((workspace_root / "src" / "model.py").is_file())
        self.assertFalse((workspace_root / "scripts" / "train.py").exists())

    def test_shared_generation_context_included_in_prompts(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation", "Implement network.")],
        )

        with self.assertRaises(RepositoryAcceptanceError):
            self._coder.run(_sample_analysis(), task)

        user_prompt = self._recording_llm.calls[0][1].content
        self.assertIn("Shared generation context:", user_prompt)
        self.assertIn('"framework": "PyTorch"', user_prompt)
        self.assertIn('"dataset": "Robomimic."', user_prompt)

    def test_repository_contract_included_in_prompts(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation", "Implement network.")],
        )

        with self.assertRaises(RepositoryAcceptanceError):
            self._coder.run(_sample_analysis(), task)

        user_prompt = self._recording_llm.calls[0][1].content
        self.assertIn("Repository contract (interface roles):", user_prompt)
        self.assertIn("module_roles", user_prompt)

    def test_interface_registry_in_train_prompt_after_upstream_files(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_3", "Dataset preparation", "Load data."),
                _step("task_5", "Training", "Train the model."),
            ],
        )

        self._coder.run(_sample_analysis(), task)

        train_prompt = self._recording_llm.calls[-1][1].content
        self.assertIn("Interface registry", train_prompt)
        self.assertIn("load_dataloaders", train_prompt)
        self.assertIn("dataset", train_prompt)

    def test_train_script_imports_registry_symbols(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_3", "Dataset preparation", "Load data."),
                _step("task_5", "Training", "Train the model."),
            ],
        )

        workspace = self._coder.run(_sample_analysis(), task)
        train_py = self._workspace_manager.read_file(workspace, "scripts/train.py")

        self.assertIn("from src.dataset import load_dataloaders", train_py)
        self.assertIn('config["dataset"]', train_py)
        self.assertIn('if __name__ == "__main__":', train_py)

    def test_generation_order_sources_before_scripts_without_requirements_llm(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_5", "Training", "Train the model."),
                _step("task_1", "Environment setup"),
            ],
        )

        workspace = self._coder.run(_sample_analysis(), task)

        target_paths = [
            CoderMockLLMProvider._extract_target_path(call)
            for call in self._recording_llm.calls
        ]
        self.assertEqual(
            target_paths,
            [
                "configs/train.yaml",
                "scripts/train.py",
            ],
        )
        requirements = self._workspace_manager.read_file(workspace, "requirements.txt")
        self.assertIn("torch", requirements)
        self.assertIn("PyYAML", requirements)

    def test_readme_reflects_populated_repository(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[
                _step("task_3", "Dataset preparation", "Load data."),
                _step("task_5", "Training", "Train the model."),
            ],
        )

        workspace = self._coder.run(_sample_analysis(), task)
        readme = self._workspace_manager.read_file(workspace, "README.md")

        self.assertIn("## Generated Files", readme)
        self.assertIn("`src/dataset.py`", readme)
        self.assertIn("`configs/dataset.yaml`", readme)
        self.assertIn("Source code generation:** complete", readme)
        self.assertNotIn("have not been generated yet", readme)


class CoderPopulationWorkflowTest(unittest.TestCase):
    def test_workflow_execution(self) -> None:
        from agents.planner import Planner
        from agents.reader import Reader
        from agents.reporter import Reporter
        from agents.reviewer import Reviewer
        from agents.runner import Runner
        from adapters.pymupdf_parser import PyMuPDFParser
        from workflow.orchestrator import WorkflowOrchestrator

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
