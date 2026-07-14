from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from models.execution import ExecutionResult
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from models.review import PatchPlan
from models.review_report import ReviewReport
from models.task import TaskModel
from models.verification import VerificationResult
from models.workspace import Workspace


class StageRecord(BaseModel):
    agent_name: str
    status: str
    duration_seconds: float


class WorkflowHistory(BaseModel):
    stages: list[StageRecord] = Field(default_factory=list)
    analysis: PaperReproductionAnalysis | None = None
    discovery: ResearchResourceDiscovery | None = None
    execution_strategy: ExecutionStrategy | None = None
    task: TaskModel | None = None
    workspace: Workspace | None = None
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    review_reports: list[ReviewReport] = Field(default_factory=list)
    patch_plans: list[PatchPlan] = Field(default_factory=list)


class ReportModel(BaseModel):
    reproduction_summary: str
    implementation_summary: str
    execution_history: list[ExecutionResult] = Field(default_factory=list)
    debugging_history: list[PatchPlan] = Field(default_factory=list)
    final_status: str
    report_path: Path | None = None
