"""Merge policy for Execution Planning reuse stage results."""

from __future__ import annotations

from models.execution_planning_runtime import ReusePlanResult
from models.execution_strategy import ReuseMode


def merge_reuse_results(existing: ReusePlanResult, incoming: ReusePlanResult) -> ReusePlanResult:
    if _is_empty_reuse(existing) and not _is_empty_reuse(incoming):
        return incoming
    if not _is_empty_reuse(existing):
        return existing
    return incoming


def _is_empty_reuse(result: ReusePlanResult) -> bool:
    return (
        result.reuse_plan.reuse_mode == ReuseMode.NOT_APPLICABLE
        and not result.reuse_plan.reuse_assumptions
        and not result.decision_notes
    )
