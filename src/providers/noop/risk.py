from models.execution_planning_runtime import RiskAssessmentResult, RiskAssessmentSnapshot
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpRiskProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
        generation_result,
    ) -> RiskAssessmentResult:
        del analysis, discovery
        return RiskAssessmentResult(
            strategy=generation_result.strategy,
            resource_bindings=generation_result.resource_bindings,
            reuse_plan=generation_result.reuse_plan,
            adaptation_plan=generation_result.adaptation_plan,
            generation_plan=generation_result.generation_plan,
            risk_assessment=RiskAssessmentSnapshot(),
        )
