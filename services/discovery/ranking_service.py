"""Discovery ranking service."""

from __future__ import annotations

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import RankList, RankingResult
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.ranking_provider import RankingProvider, RankingProviderResult
from ports.verification_provider import VerificationProviderResult
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.github.ranking import GitHubRankingProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from services.discovery.ranking_merge import merge_rank_lists


class RankingService:
    """Orchestrates ranking providers; workflow depends on this service only."""

    def __init__(self, providers: list[RankingProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def rank(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
        verification_result: VerificationProviderResult,
    ) -> RankingResult:
        merged_lists: list[RankList] = []

        for provider in self._providers:
            result = provider.rank(
                analysis,
                collection_result,
                evidence_result,
                verification_result,
            )
            merged_lists = merge_rank_lists(merged_lists, result.rank_lists)

        return RankingResult(rank_lists=merged_lists, global_notes="")

    @classmethod
    def default(cls) -> RankingService:
        return cls(providers=_default_providers())


def _default_providers() -> list[RankingProvider]:
    return [
        EmbeddedRankingProvider(),
        GitHubRankingProvider(),
        NoOpRankingProvider(),
    ]
