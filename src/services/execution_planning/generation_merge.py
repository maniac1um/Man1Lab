"""Merge policy for Execution Planning generation stage results."""

from __future__ import annotations

from models.execution_planning_runtime import GenerationPlanResult


def merge_generation_results(
    existing: GenerationPlanResult,
    incoming: GenerationPlanResult,
) -> GenerationPlanResult:
    if _is_empty_generation(existing) and not _is_empty_generation(incoming):
        return incoming
    if not _is_empty_generation(existing):
        return existing
    return incoming


def _is_empty_generation(result: GenerationPlanResult) -> bool:
    return (
        not result.generation_plan.generation_required
        and not result.generation_plan.generation_rationale
        and not result.decision_notes
    )
