"""Verification provider port — no SDK, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    EvidenceRecord,
    ProviderRecord,
    RepositoryCandidate,
    VerificationRecord,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult


@dataclass(frozen=True)
class VerificationProviderResult:
    verification_records: list[VerificationRecord] = field(default_factory=list)
    provider_outcomes: list[ProviderRecord] = field(default_factory=list)


class VerificationProvider(Protocol):
    def verify(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
    ) -> VerificationProviderResult:
        """Apply reproducibility-relevant checks to candidates."""
