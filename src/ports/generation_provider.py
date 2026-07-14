"""Generation provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import AdaptationPlanResult, GenerationPlanResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class GenerationProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        adaptation_result: AdaptationPlanResult,
    ) -> GenerationPlanResult:
        """Produce a generation planning runtime result."""
