from enum import Enum

from pydantic import BaseModel, Field

from models.execution import ExecutionResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.report import WorkflowHistory
from models.review import PatchPlan
from models.task import TaskModel
from models.workspace import Workspace


class PipelineStage(str, Enum):
    READER = "Reader"
    DISCOVERY = "Discovery"
    EXECUTION_PLANNING = "ExecutionPlanning"
    PLANNER = "Planner"
    CODER = "Coder"
    RUNNER = "Runner"
    REVIEWER = "Reviewer"
    PATCH_PLANNER = "PatchPlanner"
    REPORTER = "Reporter"


class PipelineContext(BaseModel):
    paper_path: str
    analysis: PaperReproductionAnalysis | None = None
    task: TaskModel | None = None
    workspace: Workspace | None = None
    execution_result: ExecutionResult | None = None
    patch_plans: list[PatchPlan] = Field(default_factory=list)
    history: WorkflowHistory = Field(default_factory=WorkflowHistory)
