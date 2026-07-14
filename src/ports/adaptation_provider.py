"""Adaptation provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import AdaptationPlanResult, ReusePlanResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class AdaptationProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        reuse_result: ReusePlanResult,
    ) -> AdaptationPlanResult:
        """Produce an adaptation planning runtime result."""
