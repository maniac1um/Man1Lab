"""Merge policy for Execution Planning adaptation stage results."""

from __future__ import annotations

from models.execution_planning_runtime import AdaptationPlanResult


def merge_adaptation_results(
    existing: AdaptationPlanResult,
    incoming: AdaptationPlanResult,
) -> AdaptationPlanResult:
    if _is_empty_adaptation(existing) and not _is_empty_adaptation(incoming):
        return incoming
    if not _is_empty_adaptation(existing):
        return existing
    return incoming


def _is_empty_adaptation(result: AdaptationPlanResult) -> bool:
    return (
        not result.adaptation_plan.adaptation_required
        and not result.adaptation_plan.adaptation_triggers
        and not result.decision_notes
    )
