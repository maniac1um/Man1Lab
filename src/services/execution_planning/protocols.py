"""Execution Planning service contracts — protocols only, no implementations."""

from __future__ import annotations

from typing import Protocol

from models.execution_planning_runtime import (
    AdaptationPlanResult,
    GenerationPlanResult,
    ResourceBindingResult,
    ReusePlanResult,
    RiskAssessmentResult,
    StrategyDecisionResult,
)
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class StrategyService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> StrategyDecisionResult: ...


class ResourceBindingService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        strategy_result: StrategyDecisionResult,
    ) -> ResourceBindingResult: ...


class ReuseService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        binding_result: ResourceBindingResult,
    ) -> ReusePlanResult: ...


class AdaptationService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        reuse_result: ReusePlanResult,
    ) -> AdaptationPlanResult: ...


class GenerationService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        adaptation_result: AdaptationPlanResult,
    ) -> GenerationPlanResult: ...


class RiskService(Protocol):
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        generation_result: GenerationPlanResult,
    ) -> RiskAssessmentResult: ...
