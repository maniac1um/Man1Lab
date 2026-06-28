import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from llm.coder_mock_provider import MOCK_FILE_CONTENT, CoderMockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from models.paper import PaperModel
from models.task import TaskModel, TaskStep
from tests.fixtures import create_sample_paper_pdf
from workspace.manager import WorkspaceManager


def _sample_paper() -> PaperModel:
    return PaperModel(
        title="Population Test Paper",
        abstract="Abstract.",
        method="Method.",
        dataset="Dataset.",
        model="Model.",
        framework="PyTorch",
        optimizer="AdamW",
        loss="Loss.",
        training_pipeline="Pipeline.",
        evaluation_metric="Metric.",
    )


def _step(task_id: str, name: str, description: str = "") -> TaskStep:
    return TaskStep(id=task_id, name=name, description=description)


class RecordingLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        self.calls.append(messages)
        target_path = CoderMockLLMProvider._extract_target_path(messages)
        return MOCK_FILE_CONTENT.get(target_path, f"# Generated: {target_path}\n")


class CoderPopulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._workspace_manager = WorkspaceManager(root=self._root)
        self._recording_llm = RecordingLLMProvider()
        self._coder = Coder(
            workspace_manager=self._workspace_manager,
            llm=self._recording_llm,
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

        self._coder.run(_sample_paper(), task)

        self.assertEqual(len(self._recording_llm.calls), 3)

    def test_generated_content_written_through_workspace_manager(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation", "Implement network.")],
        )

        workspace = self._coder.run(_sample_paper(), task)
        content = self._workspace_manager.read_file(workspace, "src/model.py")

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

        workspace = self._coder.run(_sample_paper(), task)

        self.assertTrue((workspace.root_path / "requirements.txt").is_file())
        self.assertTrue((workspace.root_path / "scripts/train.py").is_file())
        self.assertTrue((workspace.root_path / "configs/train.yaml").is_file())
        self.assertTrue((workspace.root_path / "scripts/evaluate.py").is_file())
        self.assertFalse((workspace.root_path / "src" / "dataset.py").exists())

    def test_deterministic_repository_population(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_3", "Dataset preparation", "Load data.")],
        )

        workspace_one = self._coder.run(_sample_paper(), task)
        workspace_two = self._coder.run(_sample_paper(), task)

        dataset_one = self._workspace_manager.read_file(workspace_one, "src/dataset.py")
        dataset_two = self._workspace_manager.read_file(workspace_two, "src/dataset.py")
        config_one = self._workspace_manager.read_file(workspace_one, "configs/dataset.yaml")
        config_two = self._workspace_manager.read_file(workspace_two, "configs/dataset.yaml")

        self.assertEqual(dataset_one, dataset_two)
        self.assertEqual(config_one, config_two)

    def test_only_routed_files_are_created(self) -> None:
        task = TaskModel(
            paper_title="Population Test Paper",
            steps=[_step("task_4", "Model implementation")],
        )

        workspace = self._coder.run(_sample_paper(), task)

        self.assertTrue((workspace.root_path / "src" / "model.py").is_file())
        self.assertEqual(list((workspace.root_path / "src").iterdir()), [workspace.root_path / "src" / "model.py"])
        self.assertEqual(list((workspace.root_path / "scripts").iterdir()), [])
        self.assertEqual(list((workspace.root_path / "configs").iterdir()), [])


class CoderPopulationWorkflowTest(unittest.TestCase):
    def test_workflow_execution(self) -> None:
        from agents.planner import Planner
        from agents.reader import Reader
        from agents.reporter import Reporter
        from agents.reviewer import Reviewer
        from agents.runner import Runner
        from services.pdf_service import PDFService
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
                reader=Reader(pdf_service=PDFService()),
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


if __name__ == "__main__":
    unittest.main()
