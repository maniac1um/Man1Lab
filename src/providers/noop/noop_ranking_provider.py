from models.paper_reproduction_analysis import PaperReproductionAnalysis
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.ranking_provider import RankingProviderResult
from ports.verification_provider import VerificationProviderResult


class NoOpRankingProvider:
    def rank(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
        verification_result: VerificationProviderResult,
    ) -> RankingProviderResult:
        del analysis, collection_result, evidence_result, verification_result
        return RankingProviderResult()
