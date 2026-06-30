import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from models.task import TaskModel, TaskStep
from tests.fixtures import sample_reproduction_analysis
from workspace.manager import REPOSITORY_SUBDIRS, WorkspaceManager


def _sample_analysis():
    return sample_reproduction_analysis()


def _sample_task() -> TaskModel:
    return TaskModel(
        paper_title="Diffusion Policy: Visuomotor Policy Learning",
        steps=[
            TaskStep(
                id="task_1",
                name="Environment setup",
                description="Create project structure.",
            ),
            TaskStep(
                id="task_2",
                name="Training",
                description="Train the model.",
            ),
        ],
    )


class CoderWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._workspace_manager = WorkspaceManager(root=self._root)
        self._coder = Coder(workspace_manager=self._workspace_manager)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_creates_workspace_directory(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())

        expected_path = self._root / "diffusion_policy_visuomotor_policy_learning"
        self.assertEqual(workspace.root_path, expected_path)
        self.assertTrue(workspace.root_path.is_dir())

    def test_required_folders_exist(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())

        for subdir in REPOSITORY_SUBDIRS:
            self.assertTrue((workspace.root_path / subdir).is_dir())

    def test_readme_generated(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())
        readme_path = workspace.root_path / "README.md"

        self.assertTrue(readme_path.is_file())
        content = readme_path.read_text(encoding="utf-8")
        self.assertIn("Diffusion Policy: Visuomotor Policy Learning", content)
        self.assertIn("## Engineering Tasks", content)
        self.assertIn("task_1", content)
        self.assertIn("PyTorch", content)
        self.assertIn("Source code generation:** complete", content)
        self.assertIn("scripts/train.py", content)
        self.assertNotIn("have not been generated yet", content)

    def test_requirements_txt_generated(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())
        requirements_path = workspace.root_path / "requirements.txt"

        self.assertTrue(requirements_path.is_file())
        content = requirements_path.read_text(encoding="utf-8")
        self.assertIn("torch", content)
        self.assertIn("PyYAML", content)

    def test_returns_workspace_object(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())

        self.assertEqual(workspace.paper_slug, "diffusion_policy_visuomotor_policy_learning")
        self.assertEqual(workspace.root_path.parent, self._root)

    def test_routed_files_populated(self) -> None:
        workspace = self._coder.run(_sample_analysis(), _sample_task())

        self.assertTrue((workspace.root_path / "requirements.txt").is_file())
        self.assertTrue((workspace.root_path / "scripts" / "train.py").is_file())
        self.assertTrue((workspace.root_path / "configs" / "train.yaml").is_file())
        self.assertEqual(list((workspace.root_path / "src").iterdir()), [])


class WorkspaceManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._manager = WorkspaceManager(root=self._root)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_initialize_repository_writes_stub_files(self) -> None:
        workspace = self._manager.create_workspace("test_paper")
        self._manager.initialize_repository(
            workspace,
            "Test Paper",
            TaskModel(paper_title="Test Paper", steps=[]),
        )

        self.assertTrue((workspace.root_path / "README.md").is_file())
        self.assertTrue((workspace.root_path / "requirements.txt").is_file())


if __name__ == "__main__":
    unittest.main()
