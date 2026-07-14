"""Resource binding provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import ResourceBindingResult, StrategyDecisionResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class ResourceBindingProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        strategy_result: StrategyDecisionResult,
    ) -> ResourceBindingResult:
        """Produce a resource binding runtime result."""
