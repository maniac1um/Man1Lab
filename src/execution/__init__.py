"""Execution Engine capability root.

Legacy local command planning: ``execution.execution_planner.ExecutionPlanner``.
Canonical execution models: ``models.execution_engine``.
Legacy command results: ``models.execution.ExecutionResult``.
"""

from execution.decomposition import DecompositionResult, decompose_execution_graph, task_id_for_node
from execution.engine import EngineRunResult, ExecutionEngine
from execution.errors import (
    ArtifactValidationError,
    ExecutionEngineError,
    GraphValidationError,
    InvalidTransitionError,
    ResumeRejectedError,
    TaskDagValidationError,
    UnsupportedStageError,
)
from execution.report import assemble_execution_report
from execution.resume import (
    ResumeEvaluation,
    apply_resume_reuse,
    assert_resume_compatible,
    compute_graph_fingerprint,
    compute_task_fingerprint,
    evaluate_resume_tasks,
)
from execution.scheduling import SchedulerResult, SequentialScheduler
from execution.trace import ExecutionTraceBuilder
from execution.validation import task_type_for_stage, validate_execution_graph, validate_task_dag

__all__ = [
    "ArtifactValidationError",
    "DecompositionResult",
    "EngineRunResult",
    "ExecutionEngine",
    "ExecutionEngineError",
    "ExecutionTraceBuilder",
    "GraphValidationError",
    "InvalidTransitionError",
    "ResumeEvaluation",
    "ResumeRejectedError",
    "SchedulerResult",
    "SequentialScheduler",
    "TaskDagValidationError",
    "UnsupportedStageError",
    "apply_resume_reuse",
    "assemble_execution_report",
    "assert_resume_compatible",
    "compute_graph_fingerprint",
    "compute_task_fingerprint",
    "decompose_execution_graph",
    "evaluate_resume_tasks",
    "task_id_for_node",
    "task_type_for_stage",
    "validate_execution_graph",
    "validate_task_dag",
]
