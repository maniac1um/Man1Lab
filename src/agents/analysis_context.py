"""Build agent-facing context from PaperReproductionAnalysis modules."""

from __future__ import annotations

import sys

from agents.coder_quality import build_framework_binding
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.routing import TaskRoutingTable
from models.task import TaskModel, TaskStep
from models.verification import VerificationResult
from routing.task_router import TaskRouter


def build_planner_user_content(execution_strategy: ExecutionStrategy) -> str:
    """Build planner context from committed ExecutionStrategy only."""
    return (
        "Committed execution strategy for task decomposition:\n\n"
        f"Strategy:\n{execution_strategy.strategy.model_dump_json(indent=2)}\n\n"
        f"Resource bindings:\n{execution_strategy.resource_bindings.model_dump_json(indent=2)}\n\n"
        f"Reuse plan:\n{execution_strategy.reuse_plan.model_dump_json(indent=2)}\n\n"
        f"Adaptation plan:\n{execution_strategy.adaptation_plan.model_dump_json(indent=2)}\n\n"
        f"Generation plan:\n{execution_strategy.generation_plan.model_dump_json(indent=2)}\n\n"
        f"Risk assessment:\n{execution_strategy.risk_assessment.model_dump_json(indent=2)}\n\n"
        "Decompose engineering tasks that implement this strategy. "
        "Do not choose repository, greenfield, adaptation, or reuse — those are already decided."
    )


def build_planner_legacy_user_content(analysis: PaperReproductionAnalysis) -> str:
    return (
        "Reproduction analysis for planning:\n\n"
        f"Metadata:\n{analysis.metadata.model_dump_json(indent=2)}\n\n"
        f"Goal:\n{analysis.goal.model_dump_json(indent=2)}\n\n"
        f"Resources:\n{analysis.resources.model_dump_json(indent=2)}\n\n"
        f"Method:\n{analysis.method.model_dump_json(indent=2)}\n\n"
        f"Evaluation:\n{analysis.evaluation.model_dump_json(indent=2)}\n\n"
        f"Reproduction gaps:\n"
        f"{_gaps_json(analysis)}"
    )


def build_reviewer_user_content(
    analysis: PaperReproductionAnalysis,
    task: TaskModel,
    verification_result: VerificationResult,
) -> str:
    return (
        "Reproduction analysis:\n\n"
        f"Goal:\n{analysis.goal.model_dump_json(indent=2)}\n\n"
        f"Method:\n{analysis.method.model_dump_json(indent=2)}\n\n"
        f"Evaluation:\n{analysis.evaluation.model_dump_json(indent=2)}\n\n"
        f"Reproduction gaps:\n"
        f"{_gaps_json(analysis)}\n\n"
        "Task plan:\n"
        f"{task.model_dump_json(indent=2)}\n\n"
        "VerificationResult (ground truth):\n"
        f"{verification_result.model_dump_json(indent=2)}"
    )


def build_coder_shared_context(
    analysis: PaperReproductionAnalysis,
    task: TaskModel,
    routing_table: TaskRoutingTable,
) -> dict[str, object]:
    targets = routing_table.targets
    framework = analysis.method.framework
    return {
        "paper_title": analysis.metadata.title,
        "framework": framework,
        "framework_binding": build_framework_binding(framework),
        "dataset": _join_resource_names(analysis.resources.datasets),
        "model": _join_resource_names(analysis.resources.models),
        "optimizer": analysis.method.optimizer,
        "loss": analysis.method.loss,
        "training_pipeline": analysis.method.training_pipeline,
        "evaluation_metric": _join_metric_names(analysis.evaluation.metrics),
        "architecture": analysis.method.architecture,
        "data_processing": analysis.method.data_processing,
        "hyperparameters": [
            item.model_dump() for item in analysis.method.hyperparameters
        ],
        "benchmarks": list(analysis.evaluation.benchmarks),
        "reproduction_gaps": [
            item.model_dump() for item in analysis.reproduction_gaps
        ],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "repository_files": [target.relative_path for target in targets],
        "source_modules": [
            target.relative_path.removesuffix(".py").replace("/", ".")
            for target in targets
            if target.file_category == "source"
        ],
        "config_files": [
            target.relative_path
            for target in targets
            if target.file_category == "config"
        ],
        "script_files": [
            target.relative_path
            for target in targets
            if target.file_category == "script"
        ],
        "train_entrypoint": "scripts/train.py",
        "eval_entrypoint": "scripts/evaluate.py",
        "engineering_tasks": [
            {"id": step.id, "name": step.name, "description": step.description}
            for step in task.steps
        ],
        "routing_coverage": _compute_routing_coverage(task, routing_table),
    }


def _gaps_json(analysis: PaperReproductionAnalysis) -> str:
    if not analysis.reproduction_gaps:
        return "[]"
    return "[" + ", ".join(
        gap.model_dump_json() for gap in analysis.reproduction_gaps
    ) + "]"


def _join_resource_names(resources: list) -> str:
    names = [resource.name for resource in resources if resource.name]
    return ", ".join(names)


def _join_metric_names(metrics: list) -> str:
    names = [metric.name for metric in metrics if metric.name]
    return ", ".join(names)


def _compute_routing_coverage(
    task: TaskModel,
    routing_table: TaskRoutingTable,
) -> dict[str, object]:
    covered_ids: set[str] = set()
    router = TaskRouter()
    for step in task.steps:
        if router.route_step(step):
            covered_ids.add(step.id)
    unrouted = [step.id for step in task.steps if step.id not in covered_ids]
    return {
        "routed_step_ids": sorted(covered_ids),
        "unrouted_step_ids": unrouted,
    }
