"""Evidence provider port — no SDK, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import EvidenceRecord, ProviderRecord, RepositoryCandidate
from ports.collection_provider import CollectionProviderResult


@dataclass(frozen=True)
class EvidenceProviderResult:
    evidence_records: list[EvidenceRecord] = field(default_factory=list)
    provider_outcomes: list[ProviderRecord] = field(default_factory=list)


class EvidenceProvider(Protocol):
    def collect(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        candidates: list[RepositoryCandidate],
    ) -> EvidenceProviderResult:
        """Collect observable evidence for candidates."""
