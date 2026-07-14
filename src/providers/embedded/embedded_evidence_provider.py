"""Generate deterministic evidence from analysis-embedded references only."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from models.paper_reproduction_analysis import (
    ArtifactReference,
    DatasetResource,
    ExternalResource,
    PaperReproductionAnalysis,
)
from models.research_resource_discovery import (
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    ProviderInvocationStatus,
    ProviderRecord,
    RepositoryCandidate,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "embedded_evidence"
_PROVIDER_VERSION = "1.0.0"


class EmbeddedEvidenceProvider:
    """Create evidence records only for URLs explicitly present in analysis."""

    def collect(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        candidates: list[RepositoryCandidate],
    ) -> EvidenceProviderResult:
        del collection_result
        now = datetime.now(UTC)
        analysis_urls = _analysis_url_index(analysis)

        records: list[EvidenceRecord] = []
        for candidate in candidates:
            normalized = normalize_url(candidate.url)
            if not normalized or normalized not in analysis_urls:
                continue
            source_query = analysis_urls[normalized]
            records.append(
                _build_evidence_record(
                    candidate=candidate,
                    source_query=source_query,
                    collected_at=now,
                )
            )

        outcome = ProviderRecord(
            provider_name=_PROVIDER_NAME,
            provider_version=_PROVIDER_VERSION,
            invoked_at=now,
            status=ProviderInvocationStatus.SUCCESS,
            candidates_contributed=0,
            evidence_contributed=len(records),
        )
        return EvidenceProviderResult(
            evidence_records=records,
            provider_outcomes=[outcome],
        )


def _analysis_url_index(analysis: PaperReproductionAnalysis) -> dict[str, str]:
    """Map normalized URL to analysis field path (source_query)."""
    index: dict[str, str] = {}

    for resource in analysis.resources.external_resources:
        _index_url(index, resource.url, f"resources.external_resources:{resource.name}")

    for dataset in analysis.resources.datasets:
        _index_url(index, dataset.link, f"resources.datasets:{dataset.name}")

    for artifact in analysis.resources.artifacts:
        _index_url(index, artifact.location, f"resources.artifacts:{artifact.name}")

    return index


def _index_url(index: dict[str, str], url: str, source_query: str) -> None:
    text = url.strip()
    if not text.startswith("http://") and not text.startswith("https://"):
        return
    normalized = normalize_url(text)
    if normalized:
        index[normalized] = source_query


def _build_evidence_record(
    *,
    candidate: RepositoryCandidate,
    source_query: str,
    collected_at: datetime,
) -> EvidenceRecord:
    evidence_id = _evidence_id(candidate.candidate_id, source_query)
    return EvidenceRecord(
        evidence_id=evidence_id,
        candidate_id=candidate.candidate_id,
        evidence_type=EvidenceType.EMBEDDED_REFERENCE,
        evidence_source=EvidenceSource(
            source_kind=EvidenceSourceKind.PAPER_TEXT,
            provider_name=_PROVIDER_NAME,
            uri=candidate.url,
            fetch_status=FetchStatus.SUCCESS,
        ),
        observed_fact=ObservedFact(
            fields={
                "source": "paper",
                "url": candidate.url,
                "source_query": source_query,
            }
        ),
        polarity=EvidencePolarity.SUPPORTS,
        confidence=1.0,
        collected_at=collected_at,
        raw_reference=source_query,
    )


def _evidence_id(candidate_id: str, source_query: str) -> str:
    digest = hashlib.sha256(f"{candidate_id}:{source_query}".encode("utf-8")).hexdigest()[:16]
    return f"evidence-{digest}"
