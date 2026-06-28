from llm.provider import LLMProvider
from models.paper import PaperModel
from models.task import TaskModel, TaskStep


class Planner:
    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    def run(self, paper: PaperModel) -> TaskModel:
        steps = [
            TaskStep(
                id="build_model",
                name="Build model",
                description=f"Implement the {paper.model} architecture.",
            ),
            TaskStep(
                id="implement_dataset",
                name="Implement dataset",
                description=f"Load and preprocess the {paper.dataset}.",
            ),
            TaskStep(
                id="train_model",
                name="Train model",
                description=f"Run training with {paper.optimizer} and {paper.loss}.",
            ),
            TaskStep(
                id="evaluate_metrics",
                name="Evaluate metrics",
                description=f"Compute {paper.evaluation_metric}.",
            ),
        ]
        return TaskModel(paper_title=paper.title, steps=steps)
