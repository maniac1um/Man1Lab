from pydantic import BaseModel, ConfigDict, Field


class PatchItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_path: str
    description: str
    strategy: str


class PatchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    requires_patch: bool
    patches: list[PatchItem] = Field(default_factory=list)
    analysis: str
