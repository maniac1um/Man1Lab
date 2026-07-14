"""Deterministic verification using embedded evidence only."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DimensionResult,
    EvidenceRecord,
    EvidenceType,
    ProviderInvocationStatus,
    ProviderRecord,
    RepositoryCandidate,
    VerificationDimension,
    VerificationDimensionName,
    VerificationRecord,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "embedded_verification"
_PROVIDER_VERSION = "1.0.0"


class EmbeddedVerificationProvider:
    """Verify candidates using only existing embedded evidence — no network."""

    def verify(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
    ) -> VerificationProviderResult:
        del analysis
        now = datetime.now(UTC)
        evidence_by_candidate = _group_evidence(evidence_result.evidence_records)

        records: list[VerificationRecord] = []
        for candidate in collection_result.candidates:
            records.append(
                _verify_candidate(
                    candidate,
                    evidence_by_candidate.get(candidate.candidate_id, []),
                    verified_at=now,
                )
            )

        outcome = ProviderRecord(
            provider_name=_PROVIDER_NAME,
            provider_version=_PROVIDER_VERSION,
            invoked_at=now,
            status=ProviderInvocationStatus.SUCCESS,
            candidates_contributed=len(records),
            evidence_contributed=0,
        )
        return VerificationProviderResult(
            verification_records=records,
            provider_outcomes=[outcome],
        )


def _group_evidence(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    grouped: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        grouped.setdefault(record.candidate_id, []).append(record)
    return grouped


def _verify_candidate(
    candidate: RepositoryCandidate,
    evidence_records: list[EvidenceRecord],
    *,
    verified_at: datetime,
) -> VerificationRecord:
    embedded = [
        record
        for record in evidence_records
        if record.evidence_type == EvidenceType.EMBEDDED_REFERENCE
    ]

    if not embedded:
        return VerificationRecord(
            verification_id=_verification_id(candidate.candidate_id),
            candidate_id=candidate.candidate_id,
            status=VerificationStatus.SKIPPED,
            dimensions=[
                VerificationDimension(
                    dimension=VerificationDimensionName.PAPER_MATCH,
                    result=DimensionResult.INSUFFICIENT_EVIDENCE,
                    summary="No embedded paper evidence available for verification.",
                    details={
                        "verification_reason": "missing_embedded_evidence",
                        "confidence": "0.0",
                    },
                )
            ],
            blocking_failures=["no embedded paper evidence"],
            verified_at=verified_at,
            verifier_version=_PROVIDER_VERSION,
        )

    url_consistent = all(_urls_match(candidate, record) for record in embedded)
    evidence_ids = [record.evidence_id for record in embedded]
    source_queries = [
        str(record.observed_fact.fields.get("source_query", "")) for record in embedded
    ]
    paper_complete = all(query for query in source_queries)

    if url_consistent and paper_complete:
        status = VerificationStatus.PASS
        paper_result = DimensionResult.PASS
        identity_result = DimensionResult.PASS
        reason = "resource explicitly referenced by paper"
        confidence = "1.0"
        blocking_failures: list[str] = []
    elif url_consistent:
        status = VerificationStatus.PARTIAL
        paper_result = DimensionResult.PARTIAL
        identity_result = DimensionResult.PARTIAL
        reason = "embedded evidence present but paper reference incomplete"
        confidence = "0.5"
        blocking_failures = ["embedded evidence missing source_query"]
    else:
        status = VerificationStatus.FAIL
        paper_result = DimensionResult.FAIL
        identity_result = DimensionResult.FAIL
        reason = "embedded evidence URL inconsistent with candidate URL"
        confidence = "0.0"
        blocking_failures = ["embedded URL mismatch"]

    return VerificationRecord(
        verification_id=_verification_id(candidate.candidate_id),
        candidate_id=candidate.candidate_id,
        status=status,
        dimensions=[
            VerificationDimension(
                dimension=VerificationDimensionName.PAPER_MATCH,
                result=paper_result,
                summary=reason,
                evidence_ids=evidence_ids,
                details={
                    "verification_reason": reason,
                    "confidence": confidence,
                },
            ),
            VerificationDimension(
                dimension=VerificationDimensionName.IDENTITY_MATCH,
                result=identity_result,
                summary="Candidate backed by embedded paper evidence."
                if url_consistent
                else "Candidate URL does not match embedded evidence.",
                evidence_ids=evidence_ids,
                details={
                    "verification_reason": reason,
                    "confidence": confidence,
                },
            ),
        ],
        blocking_failures=blocking_failures,
        verified_at=verified_at,
        verifier_version=_PROVIDER_VERSION,
    )


def _urls_match(candidate: RepositoryCandidate, evidence: EvidenceRecord) -> bool:
    candidate_url = normalize_url(candidate.url)
    evidence_url = normalize_url(str(evidence.observed_fact.fields.get("url", "")))
    if not candidate_url or not evidence_url:
        return False
    return candidate_url == evidence_url


def _verification_id(candidate_id: str) -> str:
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    return f"verification-{digest}"
