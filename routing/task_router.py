from models.routing import RepositoryTarget, TaskRoutingTable
from models.task import TaskModel, TaskStep

_ENVIRONMENT_KEYWORDS = ("environment", "dependency", "dependencies", "setup")
_DATASET_KEYWORDS = ("dataset",)
_MODEL_SIGNAL_KEYWORDS = (
    "model",
    "architecture",
    "architectures",
    "network",
    "networks",
    "block",
    "blocks",
    "residual",
    "resnet",
    "backbone",
)
_MODEL_ACTION_KEYWORDS = (
    "implement",
    "implementation",
    "define",
    "build",
    "construct",
    "create",
)
_TRAINING_KEYWORDS = ("train", "training")
_EVALUATION_KEYWORDS = ("evaluat", "evaluation")


class TaskRouter:
    def route_step(self, step: TaskStep) -> list[RepositoryTarget]:
        task_type = self._classify_step(step)
        return self._targets_for_type(task_type, step.id)

    def route_task(self, task: TaskModel) -> TaskRoutingTable:
        targets_by_path: dict[str, RepositoryTarget] = {}
        for step in task.steps:
            for target in self.route_step(step):
                if target.relative_path not in targets_by_path:
                    targets_by_path[target.relative_path] = target
        return TaskRoutingTable(targets=list(targets_by_path.values()))

    @staticmethod
    def unrouted_step_ids(task: TaskModel, routing_table: TaskRoutingTable) -> list[str]:
        routed_ids = {target.task_id for target in routing_table.targets}
        covered_ids: set[str] = set()
        for step in task.steps:
            step_targets = TaskRouter().route_step(step)
            if step_targets:
                covered_ids.add(step.id)
        return [step.id for step in task.steps if step.id not in covered_ids]

    @staticmethod
    def _step_text(step: TaskStep) -> str:
        return f"{step.name} {step.description}".lower()

    @classmethod
    def _classify_step(cls, step: TaskStep) -> str:
        text = cls._step_text(step)
        name = step.name.lower()

        if any(keyword in name for keyword in _ENVIRONMENT_KEYWORDS):
            return "environment"
        if any(keyword in text for keyword in _EVALUATION_KEYWORDS):
            return "evaluation"
        if any(keyword in text for keyword in _TRAINING_KEYWORDS):
            return "training"
        if any(keyword in text for keyword in _DATASET_KEYWORDS):
            return "dataset"
        if any(keyword in text for keyword in _MODEL_SIGNAL_KEYWORDS) and any(
            keyword in text for keyword in _MODEL_ACTION_KEYWORDS
        ):
            return "model"
        return "unknown"

    @staticmethod
    def _targets_for_type(task_type: str, task_id: str) -> list[RepositoryTarget]:
        if task_type == "environment":
            return [
                RepositoryTarget(
                    relative_path="requirements.txt",
                    file_category="dependencies",
                    task_id=task_id,
                )
            ]
        if task_type == "dataset":
            return [
                RepositoryTarget(
                    relative_path="src/dataset.py",
                    file_category="source",
                    task_id=task_id,
                ),
                RepositoryTarget(
                    relative_path="configs/dataset.yaml",
                    file_category="config",
                    task_id=task_id,
                ),
            ]
        if task_type == "model":
            return [
                RepositoryTarget(
                    relative_path="src/model.py",
                    file_category="source",
                    task_id=task_id,
                )
            ]
        if task_type == "training":
            return [
                RepositoryTarget(
                    relative_path="scripts/train.py",
                    file_category="script",
                    task_id=task_id,
                ),
                RepositoryTarget(
                    relative_path="configs/train.yaml",
                    file_category="config",
                    task_id=task_id,
                ),
            ]
        if task_type == "evaluation":
            return [
                RepositoryTarget(
                    relative_path="scripts/evaluate.py",
                    file_category="script",
                    task_id=task_id,
                )
            ]
        return []
