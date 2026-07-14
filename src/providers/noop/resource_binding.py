from models.execution_planning_runtime import ResourceBindingResult, ResourceBindingSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpResourceBindingProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        strategy_result,
    ) -> ResourceBindingResult:
        del analysis, discovery
        return ResourceBindingResult(
            strategy=strategy_result.strategy,
            resource_bindings=ResourceBindingSnapshot(),
        )
