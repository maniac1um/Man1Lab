from pydantic import BaseModel, ConfigDict, Field


class ReviewReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str
    analysis: str
    identified_issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risk_level: str
    next_action: str
