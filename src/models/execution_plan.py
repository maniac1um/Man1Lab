from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: list[str]
    working_directory: Path
    environment_variables: dict[str, str] = Field(default_factory=dict)
