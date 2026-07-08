from models.execution_planning_runtime import GenerationPlanResult, GenerationPlanSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpGenerationProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        adaptation_result,
    ) -> GenerationPlanResult:
        del analysis, discovery
        return GenerationPlanResult(
            strategy=adaptation_result.strategy,
            resource_bindings=adaptation_result.resource_bindings,
            reuse_plan=adaptation_result.reuse_plan,
            adaptation_plan=adaptation_result.adaptation_plan,
            generation_plan=GenerationPlanSnapshot(),
        )
