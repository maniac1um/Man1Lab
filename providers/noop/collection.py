from models.paper_reproduction_analysis import PaperReproductionAnalysis
from ports.collection_provider import CollectionProvider, CollectionProviderResult


class NoOpCollectionProvider:
    def collect(self, analysis: PaperReproductionAnalysis) -> CollectionProviderResult:
        del analysis
        return CollectionProviderResult()
