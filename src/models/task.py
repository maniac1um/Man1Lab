from pydantic import BaseModel, ConfigDict, Field


class TaskStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    status: str = "PENDING"


class TaskModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_title: str
    steps: list[TaskStep] = Field(default_factory=list)
