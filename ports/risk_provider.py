"""Risk assessment provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import GenerationPlanResult, RiskAssessmentResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class RiskProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        generation_result: GenerationPlanResult,
    ) -> RiskAssessmentResult:
        """Produce a risk assessment runtime result."""
