"""Reuse provider port — no SDK, no HTTP."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import ResourceBindingResult, ReusePlanResult
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class ReuseProvider(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        binding_result: ResourceBindingResult,
    ) -> ReusePlanResult:
        """Produce a reuse planning runtime result."""
