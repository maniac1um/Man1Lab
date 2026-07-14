"""Merge policy for Execution Planning strategy stage results."""

from __future__ import annotations

from models.execution_planning_runtime import StrategyDecisionResult


def merge_strategy_results(
    existing: StrategyDecisionResult,
    incoming: StrategyDecisionResult,
) -> StrategyDecisionResult:
    if _is_empty_strategy(existing) and not _is_empty_strategy(incoming):
        return incoming
    if not _is_empty_strategy(existing):
        return existing
    return incoming


def _is_empty_strategy(result: StrategyDecisionResult) -> bool:
    return not result.strategy.deciding_factors and not result.decision_notes
