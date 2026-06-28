import unittest

from models.task import TaskModel
from validation.exceptions import TaskValidationError
from validation.task import build_task_model, normalize_task_dict, validate_task_dict

_VALID_DATA = {
    "paper_title": "Diffusion Policy",
    "tasks": [
        {
            "id": "Task_1",
            "name": "Environment setup",
            "description": "Create project structure.",
            "depends_on": [],
        },
        {
            "id": "task_2",
            "name": "Training",
            "description": "Train the model.",
            "depends_on": ["Task_1"],
        },
    ],
}


class TaskValidationTest(unittest.TestCase):
    def test_build_task_model_success(self) -> None:
        task_model = build_task_model(_VALID_DATA)
        self.assertIsInstance(task_model, TaskModel)
        self.assertEqual(task_model.paper_title, "Diffusion Policy")
        self.assertEqual(len(task_model.steps), 2)
        self.assertEqual(task_model.steps[0].id, "task_1")
        self.assertEqual(task_model.steps[0].status, "PENDING")

    def test_duplicate_task_ids_raise(self) -> None:
        data = {
            "paper_title": "Paper",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Step A",
                    "description": "Do A.",
                    "depends_on": [],
                },
                {
                    "id": "TASK_1",
                    "name": "Step B",
                    "description": "Do B.",
                    "depends_on": [],
                },
            ],
        }
        with self.assertRaises(TaskValidationError):
            build_task_model(data)

    def test_missing_required_field_raises(self) -> None:
        data = {
            "paper_title": "Paper",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Step A",
                    "description": "Do A.",
                },
            ],
        }
        with self.assertRaises(TaskValidationError):
            validate_task_dict(data)

    def test_invalid_depends_on_reference_raises(self) -> None:
        data = {
            "paper_title": "Paper",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Step A",
                    "description": "Do A.",
                    "depends_on": ["missing_task"],
                },
            ],
        }
        with self.assertRaises(TaskValidationError):
            build_task_model(data)

    def test_normalization(self) -> None:
        normalized = normalize_task_dict(_VALID_DATA)
        self.assertEqual(normalized["tasks"][0]["id"], "task_1")
        self.assertEqual(normalized["tasks"][1]["depends_on"], ["task_1"])


if __name__ == "__main__":
    unittest.main()
