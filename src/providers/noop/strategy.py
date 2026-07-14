from models.execution_planning_runtime import StrategyDecisionResult, StrategyDecisionSnapshot
from models.execution_strategy import StrategyPosture
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery


class NoOpStrategyProvider:
    def execute(
        self,
        analysis: PaperReproductionAnalysis,
        discovery: ResearchResourceDiscovery,
    ) -> StrategyDecisionResult:
        del analysis, discovery
        return StrategyDecisionResult(
            strategy=StrategyDecisionSnapshot(primary_posture=StrategyPosture.GREENFIELD)
        )
