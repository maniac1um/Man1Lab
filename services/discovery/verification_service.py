"""Discovery verification service."""

from __future__ import annotations

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import VerificationRecord
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProvider, VerificationProviderResult
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.github.verification import GitHubVerificationProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.verification_merge import merge_verification


class VerificationService:
    """Orchestrates verification providers; workflow depends on this service only."""

    def __init__(self, providers: list[VerificationProvider] | None = None) -> None:
        self._providers = list(providers) if providers is not None else _default_providers()

    def verify(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
    ) -> VerificationProviderResult:
        merged_records: list[VerificationRecord] = []
        provider_outcomes = []

        for provider in self._providers:
            result = provider.verify(analysis, collection_result, evidence_result)
            provider_outcomes.extend(result.provider_outcomes)
            merged_records = merge_verification(merged_records, result.verification_records)

        return VerificationProviderResult(
            verification_records=merged_records,
            provider_outcomes=provider_outcomes,
        )

    @classmethod
    def default(cls) -> VerificationService:
        return cls(providers=_default_providers())


def _default_providers() -> list[VerificationProvider]:
    return [
        EmbeddedVerificationProvider(),
        GitHubVerificationProvider(),
        NoOpVerificationProvider(),
    ]
