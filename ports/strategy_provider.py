"""Strategy provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import StrategyDecisionResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class StrategyProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> StrategyDecisionResult:
        """Produce a strategy decision runtime result."""
