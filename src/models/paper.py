from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PaperModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    abstract: str
    method: str
    dataset: str
    model: str
    framework: str
    optimizer: str
    loss: str
    training_pipeline: str
    evaluation_metric: str
    source_path: Path | None = None
