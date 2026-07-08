from models.execution_planning_runtime import ReusePlanResult, ReusePlanSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpReuseProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        binding_result,
    ) -> ReusePlanResult:
        del analysis, discovery
        return ReusePlanResult(
            strategy=binding_result.strategy,
            resource_bindings=binding_result.resource_bindings,
            reuse_plan=ReusePlanSnapshot(),
        )
