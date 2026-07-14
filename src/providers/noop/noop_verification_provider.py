from models.paper_reproduction_analysis import PaperReproductionAnalysis
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult


class NoOpVerificationProvider:
    def verify(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
    ) -> VerificationProviderResult:
        del analysis, collection_result, evidence_result
        return VerificationProviderResult()
