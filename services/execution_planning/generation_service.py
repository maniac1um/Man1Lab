"""Execution Planning generation service."""

from __future__ import annotations

from models.execution_planning_runtime import (
    AdaptationPlanResult,
    GenerationPlanResult,
    GenerationPlanSnapshot,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.generation_provider import GenerationProvider
from providers.embedded.generation import EmbeddedGenerationProvider
from providers.noop.generation import NoOpGenerationProvider
from services.execution_planning.generation_merge import merge_generation_results


class GenerationService:
    """Orchestrates generation providers; workflow depends on this service only."""

    def __init__(self, providers: list[GenerationProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        adaptation_result: AdaptationPlanResult,
    ) -> GenerationPlanResult:
        merged: GenerationPlanResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery, adaptation_result)
            merged = merge_generation_results(merged, result) if merged is not None else result
        return merged or GenerationPlanResult(
            strategy=adaptation_result.strategy,
            resource_bindings=adaptation_result.resource_bindings,
            reuse_plan=adaptation_result.reuse_plan,
            adaptation_plan=adaptation_result.adaptation_plan,
            generation_plan=GenerationPlanSnapshot(),
        )

    @classmethod
    def default(cls) -> GenerationService:
        return cls(providers=_default_providers())


def _default_providers() -> list[GenerationProvider]:
    return [EmbeddedGenerationProvider(), NoOpGenerationProvider()]
