import tempfile
import unittest
from pathlib import Path

from adapters.pymupdf_parser import PyMuPDFParser
from agents.coder import Coder
from models.task import TaskModel, TaskStep
from routing.task_router import TaskRouter
from agents.runner import Runner
from services.environment_service import EnvironmentService
from services.execution_service import ExecutionService
from tests.fixtures import create_sample_paper_pdf
from tests.runner_mocks import mock_command_runner
from workspace.manager import WorkspaceManager
from tests.support.prompt import default_prompt_builder


def _step(task_id: str, name: str, description: str = "") -> TaskStep:
    return TaskStep(id=task_id, name=name, description=description)


class TaskRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self._router = TaskRouter()

    def test_routes_environment_task(self) -> None:
        step = _step("task_1", "Environment setup", "Configure Python environment.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "requirements.txt")
        self.assertEqual(targets[0].file_category, "dependencies")
        self.assertEqual(targets[0].task_id, "task_1")

    def test_routes_dependency_installation_to_environment(self) -> None:
        step = _step("task_2", "Dependency installation", "Install PyTorch.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "requirements.txt")

    def test_routes_dataset_task(self) -> None:
        step = _step("task_3", "Dataset preparation", "Load benchmark data.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 2)
        self.assertEqual(
            [target.relative_path for target in targets],
            ["src/dataset.py", "configs/dataset.yaml"],
        )
        self.assertEqual(targets[0].file_category, "source")
        self.assertEqual(targets[1].file_category, "config")
        self.assertEqual(targets[0].task_id, "task_3")
        self.assertEqual(targets[1].task_id, "task_3")

    def test_routes_model_implementation_task(self) -> None:
        step = _step("task_4", "Model implementation", "Implement the network.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "src/model.py")
        self.assertEqual(targets[0].file_category, "source")

    def test_routes_training_task(self) -> None:
        step = _step("task_5", "Training", "Train the model.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 2)
        self.assertEqual(
            [target.relative_path for target in targets],
            ["scripts/train.py", "configs/train.yaml"],
        )
        self.assertEqual(targets[0].file_category, "script")
        self.assertEqual(targets[1].file_category, "config")

    def test_routes_evaluation_task(self) -> None:
        step = _step("task_6", "Evaluation", "Evaluate task success rate.")
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "scripts/evaluate.py")
        self.assertEqual(targets[0].file_category, "script")
        self.assertEqual(targets[0].task_id, "task_6")

    def test_routing_is_deterministic(self) -> None:
        step = _step("task_5", "Training", "Train the model.")
        first = self._router.route_step(step)
        second = self._router.route_step(step)

        self.assertEqual(first, second)

    def test_route_task_combines_all_steps(self) -> None:
        task = TaskModel(
            paper_title="Test Paper",
            steps=[
                _step("task_1", "Environment setup"),
                _step("task_3", "Dataset preparation"),
                _step("task_5", "Training"),
                _step("task_6", "Evaluation"),
            ],
        )
        routing_table = self._router.route_task(task)

        paths = [target.relative_path for target in routing_table.targets]
        self.assertEqual(
            paths,
            [
                "requirements.txt",
                "src/dataset.py",
                "configs/dataset.yaml",
                "scripts/train.py",
                "configs/train.yaml",
                "scripts/evaluate.py",
            ],
        )

    def test_routes_residual_block_task(self) -> None:
        step = _step(
            "model_blocks",
            "Implement Residual Building Block",
            "Implement the core residual building block.",
        )
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "src/model.py")

    def test_route_task_deduplicates_duplicate_paths(self) -> None:
        task = TaskModel(
            paper_title="Test Paper",
            steps=[
                _step("task_3a", "Dataset preparation", "Load CIFAR."),
                _step("task_3b", "Dataset preparation", "Load ImageNet."),
                _step("task_5a", "Training", "Train on CIFAR."),
                _step("task_5b", "Training", "Train on ImageNet."),
            ],
        )
        routing_table = self._router.route_task(task)

        paths = [target.relative_path for target in routing_table.targets]
        self.assertEqual(
            paths,
            [
                "src/dataset.py",
                "configs/dataset.yaml",
                "scripts/train.py",
                "configs/train.yaml",
            ],
        )
        self.assertEqual(len(paths), len(set(paths)))

    def test_environment_setup_not_misclassified_as_evaluation(self) -> None:
        step = _step(
            "1",
            "Environment setup",
            "Install PyTorch, timm, and other dependencies for training and evaluation.",
        )
        targets = self._router.route_step(step)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].relative_path, "requirements.txt")

    def test_unknown_task_returns_empty_targets(self) -> None:
        step = _step("task_x", "Literature review", "Summarize related work.")
        targets = self._router.route_step(step)

        self.assertEqual(targets, [])


class CoderRoutingIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._workspace_manager = WorkspaceManager(root=self._root)
        self._coder = Coder(workspace_manager=self._workspace_manager, prompt_builder=default_prompt_builder())

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_coder_stores_routing_table_and_populates_routed_files(self) -> None:
        from tests.fixtures import sample_reproduction_analysis

        analysis = sample_reproduction_analysis()
        task = TaskModel(
            paper_title="Routing Test Paper",
            steps=[
                _step("task_1", "Environment setup"),
                _step("task_3", "Dataset preparation"),
                _step("task_5", "Training", "Train the model."),
            ],
        )

        workspace = self._coder.run(analysis, task)
        routing_table = self._workspace_manager.get_routing_table(workspace)

        self.assertIsNotNone(routing_table)
        paths = [target.relative_path for target in routing_table.targets]
        self.assertEqual(
            paths,
            [
                "requirements.txt",
                "src/dataset.py",
                "configs/dataset.yaml",
                "scripts/train.py",
                "configs/train.yaml",
            ],
        )
        self.assertTrue((workspace.root_path / "src" / "dataset.py").is_file())
        self.assertTrue((workspace.root_path / "configs" / "dataset.yaml").is_file())


class TaskRoutingWorkflowTest(unittest.TestCase):
    def test_workflow_execution(self) -> None:
        from agents.planner import Planner
        from agents.reader import Reader
        from agents.reporter import Reporter
        from agents.reviewer import Reviewer
        from agents.runner import Runner
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
