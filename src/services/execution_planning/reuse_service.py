"""Execution Planning reuse service."""

from __future__ import annotations

from models.execution_planning_runtime import ResourceBindingResult, ReusePlanResult, ReusePlanSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.reuse_provider import ReuseProvider
from providers.embedded.reuse import EmbeddedReuseProvider
from providers.noop.reuse import NoOpReuseProvider
from services.execution_planning.reuse_merge import merge_reuse_results


class ReuseService:
    """Orchestrates reuse providers; workflow depends on this service only."""

    def __init__(self, providers: list[ReuseProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        binding_result: ResourceBindingResult,
    ) -> ReusePlanResult:
        merged: ReusePlanResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery, binding_result)
            merged = merge_reuse_results(merged, result) if merged is not None else result
        return merged or ReusePlanResult(
            strategy=binding_result.strategy,
            resource_bindings=binding_result.resource_bindings,
            reuse_plan=ReusePlanSnapshot(),
        )

    @classmethod
    def default(cls) -> ReuseService:
        return cls(providers=_default_providers())


def _default_providers() -> list[ReuseProvider]:
    return [EmbeddedReuseProvider(), NoOpReuseProvider()]
