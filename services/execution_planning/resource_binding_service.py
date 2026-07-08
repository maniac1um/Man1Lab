"""Execution Planning resource binding service."""

from __future__ import annotations

from models.execution_planning_runtime import ResourceBindingResult, ResourceBindingSnapshot, StrategyDecisionResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.resource_binding_provider import ResourceBindingProvider
from providers.embedded.resource_binding import EmbeddedResourceBindingProvider
from providers.noop.resource_binding import NoOpResourceBindingProvider
from services.execution_planning.resource_binding_merge import merge_resource_binding_results


class ResourceBindingService:
    """Orchestrates resource binding providers; workflow depends on this service only."""

    def __init__(self, providers: list[ResourceBindingProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        strategy_result: StrategyDecisionResult,
    ) -> ResourceBindingResult:
        merged: ResourceBindingResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery, strategy_result)
            merged = (
                merge_resource_binding_results(merged, result) if merged is not None else result
            )
        return merged or ResourceBindingResult(
            strategy=strategy_result.strategy,
            resource_bindings=ResourceBindingSnapshot(),
        )

    @classmethod
    def default(cls) -> ResourceBindingService:
        return cls(providers=_default_providers())


def _default_providers() -> list[ResourceBindingProvider]:
    return [EmbeddedResourceBindingProvider(), NoOpResourceBindingProvider()]
