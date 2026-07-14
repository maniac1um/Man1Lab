"""Collection provider port — no SDK, no HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ProviderRecord, RepositoryCandidate, ResourceNeed


@dataclass(frozen=True)
class CollectionProviderResult:
    candidates: list[RepositoryCandidate] = field(default_factory=list)
    resource_needs: list[ResourceNeed] = field(default_factory=list)
    provider_outcomes: list[ProviderRecord] = field(default_factory=list)


class CollectionProvider(Protocol):
    def collect(self, analysis: PaperReproductionAnalysis) -> CollectionProviderResult:
        """Enumerate plausible resource candidates from analysis seeds."""
