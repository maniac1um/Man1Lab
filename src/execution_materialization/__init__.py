"""Planning-to-execution materialization capability."""

from execution_materialization.materializer import ExecutionMaterializer
from execution_materialization.task_factory import merge_metadata, project_spec_to_metadata
from execution_materialization.templates import TaskTemplateRegistry
from execution_materialization.validation import ExecutionReadinessValidator

__all__ = [
    "ExecutionMaterializer",
    "ExecutionReadinessValidator",
    "TaskTemplateRegistry",
    "merge_metadata",
    "project_spec_to_metadata",
]
