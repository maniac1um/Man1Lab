"""No-op discovery providers for skeleton workflow execution."""

from ports.collection_provider import CollectionProvider, CollectionProviderResult
from ports.evidence_provider import EvidenceProvider, EvidenceProviderResult
from ports.verification_provider import VerificationProvider, VerificationProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider

__all__ = [
    "EmbeddedEvidenceProvider",
    "EmbeddedResourceProvider",
    "EmbeddedVerificationProvider",
    "EmbeddedRankingProvider",
    "NoOpCollectionProvider",
    "NoOpEvidenceProvider",
    "NoOpVerificationProvider",
    "NoOpRankingProvider",
]
