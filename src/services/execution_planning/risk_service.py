"""Execution Planning risk assessment service."""

from __future__ import annotations

from models.execution_planning_runtime import GenerationPlanResult, RiskAssessmentResult, RiskAssessmentSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from ports.risk_provider import RiskProvider
from providers.embedded.risk import EmbeddedRiskProvider
from providers.noop.risk import NoOpRiskProvider
from services.execution_planning.risk_merge import merge_risk_results


class RiskService:
    """Orchestrates risk providers; workflow depends on this service only."""

    def __init__(self, providers: list[RiskProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        generation_result: GenerationPlanResult,
    ) -> RiskAssessmentResult:
        merged: RiskAssessmentResult | None = None
        for provider in self._providers:
            result = provider.execute(analysis, discovery, generation_result)
            merged = merge_risk_results(merged, result) if merged is not None else result
        return merged or RiskAssessmentResult(
            strategy=generation_result.strategy,
            resource_bindings=generation_result.resource_bindings,
            reuse_plan=generation_result.reuse_plan,
            adaptation_plan=generation_result.adaptation_plan,
            generation_plan=generation_result.generation_plan,
            risk_assessment=RiskAssessmentSnapshot(),
        )

    @classmethod
    def default(cls) -> RiskService:
        return cls(providers=_default_providers())


def _default_providers() -> list[RiskProvider]:
    return [EmbeddedRiskProvider(), NoOpRiskProvider()]
