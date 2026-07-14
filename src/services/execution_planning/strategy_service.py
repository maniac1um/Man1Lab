"""Execution Planning strategy service."""

from __future__ import annotations

from models.execution_planning_runtime import StrategyDecisionResult, StrategyDecisionSnapshot
from models.execution_strategy import StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.strategy_provider import StrategyProvider
from providers.embedded.strategy import EmbeddedStrategyProvider
from providers.noop.strategy import NoOpStrategyProvider
from services.execution_planning.strategy_merge import merge_strategy_results


class StrategyService:
    """Orchestrates strategy providers; workflow depends on this service only."""

    def __init__(self, providers: list[StrategyProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> StrategyDecisionResult:
        merged: StrategyDecisionResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery)
            merged = merge_strategy_results(merged, result) if merged is not None else result
        return merged or StrategyDecisionResult(
            strategy=StrategyDecisionSnapshot(primary_posture=StrategyPosture.GREENFIELD)
        )

    @classmethod
    def default(cls) -> StrategyService:
        return cls(providers=_default_providers())


def _default_providers() -> list[StrategyProvider]:
    return [EmbeddedStrategyProvider(), NoOpStrategyProvider()]
