from pydantic import BaseModel, ConfigDict, Field


class PatchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    requires_patch: bool
    priority: str
    targets: list[str] = Field(default_factory=list)
    reason: str
    strategy: str
