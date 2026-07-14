"""Execution Planning adaptation service."""

from __future__ import annotations

from models.execution_planning_runtime import AdaptationPlanResult, AdaptationPlanSnapshot, ReusePlanResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.adaptation_provider import AdaptationProvider
from providers.embedded.adaptation import EmbeddedAdaptationProvider
from providers.noop.adaptation import NoOpAdaptationProvider
from services.execution_planning.adaptation_merge import merge_adaptation_results


class AdaptationService:
    """Orchestrates adaptation providers; workflow depends on this service only."""

    def __init__(self, providers: list[AdaptationProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        reuse_result: ReusePlanResult,
    ) -> AdaptationPlanResult:
        merged: AdaptationPlanResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery, reuse_result)
            merged = merge_adaptation_results(merged, result) if merged is not None else result
        return merged or AdaptationPlanResult(
            strategy=reuse_result.strategy,
            resource_bindings=reuse_result.resource_bindings,
            reuse_plan=reuse_result.reuse_plan,
            adaptation_plan=AdaptationPlanSnapshot(),
        )

    @classmethod
    def default(cls) -> AdaptationService:
        return cls(providers=_default_providers())


def _default_providers() -> list[AdaptationProvider]:
    return [EmbeddedAdaptationProvider(), NoOpAdaptationProvider()]
