from pydantic import BaseModel, ConfigDict, Field

VERIFICATION_PASS = "PASS"
VERIFICATION_FAIL = "FAIL"


class VerificationFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    code: str
    message: str


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository_status: str
    environment_status: str
    execution_status: str
    output_status: str
    overall_status: str
    findings: list[VerificationFinding] = Field(default_factory=list)
