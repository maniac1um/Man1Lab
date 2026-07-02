"""Ranking provider port — no SDK, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ProviderRecord, RankList
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult


@dataclass(frozen=True)
class RankingProviderResult:
    rank_lists: list[RankList] = field(default_factory=list)
    provider_outcomes: list[ProviderRecord] = field(default_factory=list)


class RankingProvider(Protocol):
    def rank(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
        verification_result: VerificationProviderResult,
    ) -> RankingProviderResult:
        """Order candidates within each resource need by reproduction suitability."""
