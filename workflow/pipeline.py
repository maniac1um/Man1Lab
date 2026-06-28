from enum import Enum

from pydantic import BaseModel, Field

from models.execution import ExecutionResult
from models.paper import PaperModel
from models.report import WorkflowHistory
from models.review import PatchPlan
from models.task import TaskModel
from models.workspace import Workspace


class PipelineStage(str, Enum):
    READER = "Reader"
    PLANNER = "Planner"
    CODER = "Coder"
    RUNNER = "Runner"
    REVIEWER = "Reviewer"
    REPORTER = "Reporter"


class PipelineContext(BaseModel):
    paper_path: str
    paper: PaperModel | None = None
    task: TaskModel | None = None
    workspace: Workspace | None = None
    execution_result: ExecutionResult | None = None
    patch_plans: list[PatchPlan] = Field(default_factory=list)
    history: WorkflowHistory = Field(default_factory=WorkflowHistory)
