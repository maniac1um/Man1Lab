from models.execution_planning_runtime import AdaptationPlanResult, AdaptationPlanSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpAdaptationProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        reuse_result,
    ) -> AdaptationPlanResult:
        del analysis, discovery
        return AdaptationPlanResult(
            strategy=reuse_result.strategy,
            resource_bindings=reuse_result.resource_bindings,
            reuse_plan=reuse_result.reuse_plan,
            adaptation_plan=AdaptationPlanSnapshot(),
        )
