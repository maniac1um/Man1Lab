from models.task import TaskModel, TaskStep
from validation.exceptions import TaskValidationError

_TASK_FIELDS = ("id", "name", "description", "depends_on")


def normalize_task_dict(data: dict) -> dict:
    paper_title = _require_non_empty_string(data, "paper_title")
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise TaskValidationError("Invalid field: tasks must be a list")

    normalized_tasks = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TaskValidationError(f"Invalid task at index {index}")
        normalized_tasks.append(
            {
                "id": _require_non_empty_string(task, "id").lower(),
                "name": _require_non_empty_string(task, "name"),
                "description": _require_non_empty_string(task, "description"),
                "depends_on": _normalize_depends_on(task, index),
            }
        )

    return {"paper_title": paper_title, "tasks": normalized_tasks}


def validate_task_dict(data: dict) -> None:
    if "paper_title" not in data:
        raise TaskValidationError("Missing required field: paper_title")
    if "tasks" not in data:
        raise TaskValidationError("Missing required field: tasks")

    _require_non_empty_string(data, "paper_title")
    tasks = data["tasks"]
    if not isinstance(tasks, list):
        raise TaskValidationError("Invalid field: tasks must be a list")

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TaskValidationError(f"Invalid task at index {index}")
        for field in _TASK_FIELDS:
            if field not in task:
                raise TaskValidationError(
                    f"Missing required field: {field} in task at index {index}"
                )
        _require_non_empty_string(task, "id")
        _require_non_empty_string(task, "name")
        _require_non_empty_string(task, "description")
        _normalize_depends_on(task, index)


def validate_task_graph(normalized: dict) -> None:
    task_ids = [task["id"] for task in normalized["tasks"]]
    if len(task_ids) != len(set(task_ids)):
        raise TaskValidationError("Duplicate task id")

    id_set = set(task_ids)
    for task in normalized["tasks"]:
        for dependency in task["depends_on"]:
            if dependency not in id_set:
                raise TaskValidationError(
                    f"Invalid depends_on reference: {dependency}"
                )


def build_task_model(data: dict) -> TaskModel:
    validate_task_dict(data)
    normalized = normalize_task_dict(data)
    validate_task_graph(normalized)
    steps = [
        TaskStep(
            id=task["id"],
            name=task["name"],
            description=task["description"],
        )
        for task in normalized["tasks"]
    ]
    return TaskModel(paper_title=normalized["paper_title"], steps=steps)


def _require_non_empty_string(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise TaskValidationError(f"Invalid required field: {field}")
    return value.strip()


def _normalize_depends_on(task: dict, index: int) -> list[str]:
    depends_on = task.get("depends_on")
    if not isinstance(depends_on, list):
        raise TaskValidationError(
            f"Invalid field: depends_on must be a list in task at index {index}"
        )
    normalized: list[str] = []
    for dependency in depends_on:
        if not isinstance(dependency, str) or not dependency.strip():
            raise TaskValidationError(
                f"Invalid depends_on entry in task at index {index}"
            )
        normalized.append(dependency.strip().lower())
    return normalized
