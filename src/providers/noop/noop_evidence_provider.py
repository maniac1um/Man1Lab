from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import RepositoryCandidate
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult


class NoOpEvidenceProvider:
    def collect(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        candidates: list[RepositoryCandidate],
    ) -> EvidenceProviderResult:
        del analysis, collection_result, candidates
        return EvidenceProviderResult()
