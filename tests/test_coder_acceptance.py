import tempfile
import unittest
from pathlib import Path

from agents.coder import Coder
from agents.coder_quality import (
    RepositoryAcceptanceError,
    build_framework_binding,
    decide_repository_acceptance,
    validate_generated_repository,
)
from llm.coder_mock_provider import CoderMockLLMProvider
from models.paper import PaperModel
from models.task import TaskModel, TaskStep
from workspace.manager import WorkspaceManager


def _sample_paper() -> PaperModel:
    return PaperModel(
        title="Acceptance Gate Test Paper",
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


def _training_task() -> TaskModel:
    return TaskModel(
        paper_title="Acceptance Gate Test Paper",
        steps=[
            TaskStep(id="task_1", name="Environment setup", description="Install deps."),
            TaskStep(id="task_3", name="Dataset preparation", description="Load data."),
            TaskStep(id="task_5", name="Training", description="Train the model."),
        ],
    )


class CoderAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name) / "workspace" / "tasks"
        self._workspace_manager = WorkspaceManager(root=self._root)
        self._coder = Coder(
            workspace_manager=self._workspace_manager,
            llm=CoderMockLLMProvider(),
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_accepted_repository_returns_workspace(self) -> None:
        workspace = self._coder.run(_sample_paper(), _training_task())

        self.assertTrue((workspace.root_path / "scripts" / "train.py").is_file())
        acceptance_log = (
            workspace.root_path / "logs" / "repository_acceptance.log"
        ).read_text(encoding="utf-8")
        self.assertIn("Repository acceptance gate: ACCEPTED", acceptance_log)

    def test_rejected_repository_raises_error(self) -> None:
        task = TaskModel(
            paper_title="Acceptance Gate Test Paper",
            steps=[TaskStep(id="task_4", name="Model implementation", description="Build network.")],
        )

        with self.assertRaises(RepositoryAcceptanceError) as ctx:
            self._coder.run(_sample_paper(), task)

        categories = {error["category"] for error in ctx.exception.blocking_errors}
        self.assertIn("missing_training_entrypoint", categories)

    def test_warning_only_repository_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            train_path = root / "scripts" / "train.py"
            train_path.parent.mkdir(parents=True)
            train_path.write_text(
                'import torch\n'
                'config = {}\n'
                'x = config["dataset"]\n'
                'if __name__ == "__main__":\n    pass\n',
                encoding="utf-8",
            )
            findings = validate_generated_repository(
                workspace_root=root,
                routed_paths={
                    "requirements.txt",
                    "scripts/train.py",
                    "configs/train.yaml",
                },
                python_files={
                    "scripts/train.py": train_path.read_text(encoding="utf-8"),
                },
                requirements_content="torch\n",
                framework_binding=build_framework_binding("PyTorch"),
                interface_registry={
                    "configs/train.yaml": {"top_level_keys": ["batch_size"]},
                },
            )
            blocking, warnings = decide_repository_acceptance(findings)

        self.assertEqual(blocking, [])
        self.assertTrue(any(w["code"] == "config_key_not_in_registry" for w in warnings))

    def test_blocking_error_classification_import_closure(self) -> None:
        findings = [
            {
                "severity": "error",
                "code": "import_not_in_requirements",
                "message": "missing torch",
            }
        ]
        blocking, warnings = decide_repository_acceptance(findings)

        self.assertEqual(len(blocking), 1)
        self.assertEqual(blocking[0]["category"], "import_closure_failure")
        self.assertEqual(warnings, [])

    def test_blocking_error_classification_framework_binding(self) -> None:
        findings = [
            {
                "severity": "error",
                "code": "forbidden_framework_import",
                "message": "forbidden caffe",
            }
        ]
        blocking, _ = decide_repository_acceptance(findings)

        self.assertEqual(blocking[0]["category"], "framework_binding_failure")

    def test_blocking_error_classification_broken_internal_import(self) -> None:
        findings = [
            {
                "severity": "error",
                "code": "import_not_in_registry",
                "message": "symbol mismatch",
            }
        ]
        blocking, _ = decide_repository_acceptance(findings)

        self.assertEqual(blocking[0]["category"], "broken_internal_import")


if __name__ == "__main__":
    unittest.main()
