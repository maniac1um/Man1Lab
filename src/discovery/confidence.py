"""Explainable confidence composition for discovery selection."""

from __future__ import annotations

from models.explainable_confidence import ConfidenceContribution, ExplainableConfidence
from models.research_resource_discovery import (
    EvidencePolarity,
    EvidenceRecord,
    EvidenceType,
    Officiality,
    RankScore,
    RepositoryCandidate,
    VerificationRecord,
    VerificationStatus,
)

_SIGNAL_OFFICIAL_ORGANIZATION = "official_organization"
_SIGNAL_PAPER_MATCH = "paper_match"
_SIGNAL_README_MATCH = "readme_match"
_SIGNAL_VERIFICATION = "verification"
_SIGNAL_RECENT_ACTIVITY = "recent_activity"
_SIGNAL_CHECKPOINT_AVAILABILITY = "checkpoint_availability"
_SIGNAL_RANKING_SCORE = "ranking_score"

_WEIGHTS: dict[str, float] = {
    _SIGNAL_OFFICIAL_ORGANIZATION: 0.20,
    _SIGNAL_PAPER_MATCH: 0.20,
    _SIGNAL_README_MATCH: 0.10,
    _SIGNAL_VERIFICATION: 0.25,
    _SIGNAL_RECENT_ACTIVITY: 0.05,
    _SIGNAL_CHECKPOINT_AVAILABILITY: 0.10,
    _SIGNAL_RANKING_SCORE: 0.10,
}


def compose_selection_confidence(
    *,
    candidate: RepositoryCandidate | None,
    verification_record: VerificationRecord | None,
    evidence_records: list[EvidenceRecord],
    rank_score: RankScore | None,
    need_category_value: str,
) -> ExplainableConfidence:
    """Build deterministic explainable confidence from evidence and verification."""
    contributions = [
        _official_organization_contribution(candidate),
        _paper_match_contribution(evidence_records),
        _readme_match_contribution(evidence_records),
        _verification_contribution(verification_record),
        _recent_activity_contribution(evidence_records),
        _checkpoint_availability_contribution(candidate, need_category_value),
        _ranking_score_contribution(rank_score),
    ]
    weighted = min(1.0, sum(item.contribution for item in contributions))
    legacy = _legacy_confidence_floor(verification_record, rank_score)
    overall = round(max(legacy, weighted), 2)
    return ExplainableConfidence(
        overall=overall,
        contributions=contributions,
        composition_rule="max(legacy_verification_floor, weighted_sum_capped)",
    )


def _legacy_confidence_floor(
    verification_record: VerificationRecord | None,
    rank_score: RankScore | None,
) -> float:
    """Preserve Phase 1 confidence floors for backward-compatible selection thresholds."""
    status = verification_record.status if verification_record is not None else VerificationStatus.SKIPPED
    base = {
        VerificationStatus.PASS: 0.9,
        VerificationStatus.PARTIAL: 0.65,
    }.get(status, 0.0)
    if rank_score is None:
        return round(base, 2)
    normalized = min(1.0, max(0.0, rank_score.total_score / 5.0))
    return round(min(1.0, base + 0.1 * normalized), 2)


def _official_organization_contribution(candidate: RepositoryCandidate | None) -> ConfidenceContribution:
    score = 0.0
    summary = "No candidate for officiality assessment."
    if candidate is not None:
        score = {
            Officiality.OFFICIAL: 1.0,
            Officiality.AUTHOR_AFFILIATED: 0.85,
            Officiality.COMMUNITY: 0.55,
            Officiality.THIRD_PARTY: 0.35,
            Officiality.UNKNOWN: 0.2,
        }.get(candidate.officiality, 0.2)
        summary = f"Officiality={candidate.officiality.value}"
    weight = _WEIGHTS[_SIGNAL_OFFICIAL_ORGANIZATION]
    return ConfidenceContribution(
        signal=_SIGNAL_OFFICIAL_ORGANIZATION,
        weight=weight,
        score=score,
        contribution=round(weight * score, 4),
        summary=summary,
    )


def _paper_match_contribution(evidence_records: list[EvidenceRecord]) -> ConfidenceContribution:
    supporting = [
        record
        for record in evidence_records
        if record.polarity == EvidencePolarity.SUPPORTS
        and record.evidence_type
        in {
            EvidenceType.PAPER_CITATION_MATCH,
            EvidenceType.TITLE_MATCH,
            EvidenceType.AUTHOR_MATCH,
            EvidenceType.EMBEDDED_REFERENCE,
        }
    ]
    score = min(1.0, 0.4 + 0.2 * len(supporting)) if supporting else 0.0
    weight = _WEIGHTS[_SIGNAL_PAPER_MATCH]
    return ConfidenceContribution(
        signal=_SIGNAL_PAPER_MATCH,
        weight=weight,
        score=round(score, 2),
        contribution=round(weight * score, 4),
        summary=f"{len(supporting)} supporting paper-match evidence record(s).",
    )


def _readme_match_contribution(evidence_records: list[EvidenceRecord]) -> ConfidenceContribution:
    supporting = [
        record
        for record in evidence_records
        if record.polarity == EvidencePolarity.SUPPORTS
        and record.evidence_type == EvidenceType.README_CLAIM
    ]
    score = 1.0 if supporting else 0.0
    weight = _WEIGHTS[_SIGNAL_README_MATCH]
    return ConfidenceContribution(
        signal=_SIGNAL_README_MATCH,
        weight=weight,
        score=score,
        contribution=round(weight * score, 4),
        summary="README claim supports resource." if supporting else "No README match evidence.",
    )


def _verification_contribution(verification_record: VerificationRecord | None) -> ConfidenceContribution:
    status = verification_record.status if verification_record is not None else VerificationStatus.SKIPPED
    score = {
        VerificationStatus.PASS: 1.0,
        VerificationStatus.PARTIAL: 0.65,
        VerificationStatus.FAIL: 0.0,
        VerificationStatus.SKIPPED: 0.0,
        VerificationStatus.ERROR: 0.0,
    }.get(status, 0.0)
    weight = _WEIGHTS[_SIGNAL_VERIFICATION]
    return ConfidenceContribution(
        signal=_SIGNAL_VERIFICATION,
        weight=weight,
        score=score,
        contribution=round(weight * score, 4),
        summary=f"Verification status={status.value}.",
    )


def _recent_activity_contribution(evidence_records: list[EvidenceRecord]) -> ConfidenceContribution:
    supporting = [
        record
        for record in evidence_records
        if record.evidence_type == EvidenceType.COMMIT_RECENCY
        and record.polarity != EvidencePolarity.REFUTES
    ]
    score = 0.8 if supporting else 0.3
    weight = _WEIGHTS[_SIGNAL_RECENT_ACTIVITY]
    return ConfidenceContribution(
        signal=_SIGNAL_RECENT_ACTIVITY,
        weight=weight,
        score=score,
        contribution=round(weight * score, 4),
        summary="Commit recency evidence present." if supporting else "No recency evidence.",
    )


def _checkpoint_availability_contribution(
    candidate: RepositoryCandidate | None,
    need_category_value: str,
) -> ConfidenceContribution:
    from models.research_resource_discovery import NeedCategory, ResourceType

    weight = _WEIGHTS[_SIGNAL_CHECKPOINT_AVAILABILITY]
    if need_category_value != NeedCategory.CHECKPOINT.value:
        return ConfidenceContribution(
            signal=_SIGNAL_CHECKPOINT_AVAILABILITY,
            weight=weight,
            score=0.0,
            contribution=0.0,
            summary="Not a checkpoint need.",
        )
    score = 1.0 if candidate and candidate.resource_type == ResourceType.CHECKPOINT else 0.0
    return ConfidenceContribution(
        signal=_SIGNAL_CHECKPOINT_AVAILABILITY,
        weight=weight,
        score=score,
        contribution=round(weight * score, 4),
        summary="Checkpoint asset type matched." if score else "Checkpoint asset unavailable.",
    )


def _ranking_score_contribution(rank_score: RankScore | None) -> ConfidenceContribution:
    weight = _WEIGHTS[_SIGNAL_RANKING_SCORE]
    if rank_score is None:
        return ConfidenceContribution(
            signal=_SIGNAL_RANKING_SCORE,
            weight=weight,
            score=0.0,
            contribution=0.0,
            summary="No ranking score available.",
        )
    score = min(1.0, max(0.0, rank_score.total_score / 5.0))
    return ConfidenceContribution(
        signal=_SIGNAL_RANKING_SCORE,
        weight=weight,
        score=round(score, 2),
        contribution=round(weight * score, 4),
        summary=f"Ranking total_score={rank_score.total_score:.2f}.",
    )
