"""Discovery evidence service."""

from __future__ import annotations

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import EvidenceRecord
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProvider, EvidenceProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.github.evidence import GitHubEvidenceProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from services.discovery.evidence_merge import merge_evidence


class EvidenceService:
    """Orchestrates evidence providers; workflow depends on this service only."""

    def __init__(self, providers: list[EvidenceProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def collect(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
    ) -> EvidenceProviderResult:
        merged_records: list[EvidenceRecord] = []
        provider_outcomes = []

        for provider in self._providers:
            result = provider.collect(
                analysis,
                collection_result,
                collection_result.candidates,
            )
            provider_outcomes.extend(result.provider_outcomes)
            merged_records = merge_evidence(merged_records, result.evidence_records)

        return EvidenceProviderResult(
            evidence_records=merged_records,
            provider_outcomes=provider_outcomes,
        )

    @classmethod
    def default(cls) -> EvidenceService:
        return cls(providers=_default_providers())


def _default_providers() -> list[EvidenceProvider]:
    return [
        EmbeddedEvidenceProvider(),
        GitHubEvidenceProvider(),
        NoOpEvidenceProvider(),
    ]
