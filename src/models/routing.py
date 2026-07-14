from pydantic import BaseModel, ConfigDict, Field


class RepositoryTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    relative_path: str
    file_category: str
    task_id: str


class TaskRoutingTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    targets: list[RepositoryTarget] = Field(default_factory=list)
