"""GitHub RankingProvider — deterministic ranking from collected artifacts only."""

from __future__ import annotations

from datetime import UTC, datetime

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DimensionResult,
    DiscoveryProvider,
    EvidenceRecord,
    EvidenceType,
    ProviderInvocationStatus,
    ProviderRecord,
    RankingFactor,
    RankList,
    RankScore,
    RepositoryCandidate,
    ResourceNeed,
    VerificationRecord,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.ranking_provider import RankingProviderResult
from ports.verification_provider import VerificationProviderResult

_PROVIDER_NAME = "github_ranking"
_PROVIDER_VERSION = "1.0.0"

# Deterministic score contributions (documented weights).
_WEIGHT_VERIFICATION_PASS = 100.0
_WEIGHT_VERIFICATION_PARTIAL = 70.0
_WEIGHT_VERIFICATION_FAIL = 30.0
_WEIGHT_VERIFICATION_SKIPPED = 20.0
_WEIGHT_VERIFICATION_ERROR = 10.0
_WEIGHT_IDENTITY_MATCH = 50.0
_WEIGHT_PAPER_URL_MATCH = 40.0
_WEIGHT_NOT_ARCHIVED = 30.0
_WEIGHT_METADATA_COMPLETE = 25.0
_WEIGHT_METADATA_PARTIAL = 10.0
_WEIGHT_README_PRESENT = 20.0
_WEIGHT_LICENSE_PRESENT = 15.0
_WEIGHT_DESCRIPTION_PRESENT = 10.0
_WEIGHT_TOPICS_PRESENT = 5.0
_WEIGHT_STARS_MAX = 10.0
_WEIGHT_FORKS_MAX = 10.0
_WEIGHT_PUSH_MAX = 10.0

_ELIGIBLE_STATUSES = {VerificationStatus.PASS, VerificationStatus.PARTIAL}
_STATUS_SCORES = {
    VerificationStatus.PASS: _WEIGHT_VERIFICATION_PASS,
    VerificationStatus.PARTIAL: _WEIGHT_VERIFICATION_PARTIAL,
    VerificationStatus.FAIL: _WEIGHT_VERIFICATION_FAIL,
    VerificationStatus.SKIPPED: _WEIGHT_VERIFICATION_SKIPPED,
    VerificationStatus.ERROR: _WEIGHT_VERIFICATION_ERROR,
}


class GitHubRankingProvider:
    """Rank candidates using GitHub evidence and verification signals only — no network."""

    def rank(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
        verification_result: VerificationProviderResult,
    ) -> RankingProviderResult:
        del analysis
        now = datetime.now(UTC)
        evidence_by_candidate = _group_evidence(evidence_result.evidence_records)
        verification_by_candidate = _verification_map(verification_result.verification_records)
        candidate_index = {
            candidate.candidate_id: index
            for index, candidate in enumerate(collection_result.candidates)
        }

        rank_lists: list[RankList] = []
        for need in collection_result.resource_needs:
            candidates = [
                candidate
                for candidate in collection_result.candidates
                if need.need_id in candidate.addresses_needs
            ]
            rank_lists.append(
                _build_rank_list(
                    need,
                    candidates,
                    evidence_by_candidate,
                    verification_by_candidate,
                    candidate_index,
                    created_at=now,
                )
            )

        outcome = ProviderRecord(
            provider_name=_PROVIDER_NAME,
            provider_version=_PROVIDER_VERSION,
            invoked_at=now,
            status=ProviderInvocationStatus.SUCCESS,
            candidates_contributed=sum(len(rank_list.ordered_candidate_ids) for rank_list in rank_lists),
            evidence_contributed=0,
        )
        return RankingProviderResult(rank_lists=rank_lists, provider_outcomes=[outcome])


def _build_rank_list(
    need: ResourceNeed,
    candidates: list[RepositoryCandidate],
    evidence_by_candidate: dict[str, list[EvidenceRecord]],
    verification_by_candidate: dict[str, VerificationRecord],
    candidate_index: dict[str, int],
    *,
    created_at: datetime,
) -> RankList:
    scored = [
        _score_candidate(
            candidate,
            evidence_by_candidate.get(candidate.candidate_id, []),
            verification_by_candidate.get(candidate.candidate_id),
            collection_index=candidate_index.get(candidate.candidate_id, 0),
        )
        for candidate in candidates
    ]
    ordered = _order_scored_candidates(scored)
    scores = {item.candidate_id: item.rank_score for item in scored}
    eligible = [
        item.candidate_id
        for item in scored
        if item.verification_status in _ELIGIBLE_STATUSES
    ]

    return RankList(
        rank_list_id=f"rank-{need.need_id}",
        resource_need=need,
        ordered_candidate_ids=ordered,
        scores=scores,
        ranking_factors_summary=(
            "Deterministic GitHub ranking by verification status, identity/paper match, "
            "metadata completeness, README/license signals, and activity metrics."
        ),
        eligible_candidate_ids=eligible,
        created_at=created_at,
    )


def _score_candidate(
    candidate: RepositoryCandidate,
    evidence_records: list[EvidenceRecord],
    verification_record: VerificationRecord | None,
    *,
    collection_index: int,
) -> _ScoredCandidate:
    status = verification_record.status if verification_record is not None else VerificationStatus.SKIPPED
    factors: list[RankingFactor] = []
    factor_scores: dict[str, float] = {}
    total = 0.0

    verification_score = _STATUS_SCORES.get(status, _WEIGHT_VERIFICATION_SKIPPED)
    total += verification_score
    factors.append(
        RankingFactor(
            name="verification_status",
            score=verification_score,
            weight=verification_score,
            summary=f"verification status: {status.value}",
        )
    )
    factor_scores["verification_status"] = verification_score

    if _is_github_candidate(candidate):
        metadata = _github_metadata_fields(evidence_records)
        github_factors, github_scores, github_total = _github_signal_scores(
            verification_record,
            metadata,
        )
        factors.extend(github_factors)
        factor_scores.update(github_scores)
        total += github_total

    ranking_reason = "; ".join(factor.summary for factor in factors if factor.summary)
    rank_score = RankScore(
        candidate_id=candidate.candidate_id,
        total_score=total,
        factor_scores=factor_scores,
        ranking_factors=factors,
    )
    tie_break = _tie_break_key(
        verification_record,
        metadata if _is_github_candidate(candidate) else {},
        collection_index,
    )
    return _ScoredCandidate(
        candidate_id=candidate.candidate_id,
        verification_status=status,
        rank_score=rank_score,
        ranking_reason=ranking_reason,
        tie_break=tie_break,
        total_score=total,
    )


def _github_signal_scores(
    verification_record: VerificationRecord | None,
    metadata: dict[str, str | int | float | bool],
) -> tuple[list[RankingFactor], dict[str, float], float]:
    factors: list[RankingFactor] = []
    factor_scores: dict[str, float] = {}
    total = 0.0

    def add(name: str, score: float, summary: str) -> None:
        nonlocal total
        if score <= 0:
            return
        total += score
        factor_scores[name] = score
        factors.append(RankingFactor(name=name, score=score, weight=score, summary=summary))

    if _check_pass(verification_record, "repository_identity_match"):
        add("identity_match", _WEIGHT_IDENTITY_MATCH, "identity match passed")
    if _check_pass(verification_record, "paper_url_match"):
        add("paper_url_match", _WEIGHT_PAPER_URL_MATCH, "paper URL match passed")
    if not _as_bool(metadata.get("archived", False)):
        add("not_archived", _WEIGHT_NOT_ARCHIVED, "repository is not archived")

    completeness = _check_result(verification_record, "repository_metadata_completeness")
    if completeness == DimensionResult.PASS:
        add("metadata_completeness", _WEIGHT_METADATA_COMPLETE, "metadata completeness passed")
    elif completeness == DimensionResult.PARTIAL:
        add("metadata_completeness", _WEIGHT_METADATA_PARTIAL, "metadata completeness partial")

    if _check_pass(verification_record, "readme_present"):
        add("readme_present", _WEIGHT_README_PRESENT, "README evidence present")
    if _check_pass(verification_record, "repository_license_present"):
        add("license_present", _WEIGHT_LICENSE_PRESENT, "license present")
    if _check_pass(verification_record, "repository_description_present"):
        add("description_present", _WEIGHT_DESCRIPTION_PRESENT, "description present")
    if _check_pass(verification_record, "repository_topics_present"):
        add("topics_present", _WEIGHT_TOPICS_PRESENT, "topics present")

    stars = _as_float(metadata.get("stars", 0))
    stars_score = min(_WEIGHT_STARS_MAX, stars / 100.0)
    add("stars", stars_score, f"stars: {int(stars)}")

    forks = _as_float(metadata.get("forks", 0))
    forks_score = min(_WEIGHT_FORKS_MAX, forks / 50.0)
    add("forks", forks_score, f"forks: {int(forks)}")

    push_score = _push_recency_score(str(metadata.get("latest_push", "")))
    add("latest_push", push_score, f"latest push recency score: {push_score:.2f}")

    return factors, factor_scores, total


def _order_scored_candidates(scored: list[_ScoredCandidate]) -> list[str]:
    eligible = [item for item in scored if item.verification_status in _ELIGIBLE_STATUSES]
    ineligible = [item for item in scored if item.verification_status not in _ELIGIBLE_STATUSES]
    eligible.sort(key=lambda item: (-item.total_score, item.tie_break))
    ineligible.sort(key=lambda item: (-item.total_score, item.tie_break))
    return [item.candidate_id for item in eligible + ineligible]


def _tie_break_key(
    verification_record: VerificationRecord | None,
    metadata: dict[str, str | int | float | bool],
    collection_index: int,
) -> tuple:
    identity = 1 if _check_pass(verification_record, "repository_identity_match") else 0
    paper = 1 if _check_pass(verification_record, "paper_url_match") else 0
    stars = _as_float(metadata.get("stars", 0))
    push = str(metadata.get("latest_push", ""))
    return (-identity, -paper, -stars, push, collection_index)


def _check_pass(verification_record: VerificationRecord | None, check_name: str) -> bool:
    return _check_result(verification_record, check_name) == DimensionResult.PASS


def _check_result(
    verification_record: VerificationRecord | None,
    check_name: str,
) -> DimensionResult | None:
    if verification_record is None:
        return None
    for dimension in verification_record.dimensions:
        if dimension.details.get("check") == check_name:
            return dimension.result
    return None


def _github_metadata_fields(evidence_records: list[EvidenceRecord]) -> dict[str, str | int | float | bool]:
    for record in evidence_records:
        if (
            record.evidence_type == EvidenceType.METADATA_EXTRACT
            and record.evidence_source.provider_name == "github"
        ):
            return dict(record.observed_fact.fields)
    return {}


def _is_github_candidate(candidate: RepositoryCandidate) -> bool:
    return (
        candidate.provider == DiscoveryProvider.GITHUB
        or candidate.identity.provider == DiscoveryProvider.GITHUB
    )


def _group_evidence(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    grouped: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        grouped.setdefault(record.candidate_id, []).append(record)
    return grouped


def _verification_map(records: list[VerificationRecord]) -> dict[str, VerificationRecord]:
    return {record.candidate_id: record for record in records}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _push_recency_score(latest_push: str) -> float:
    if not latest_push:
        return 0.0
    try:
        parsed = datetime.fromisoformat(latest_push.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        years = (parsed - datetime(2010, 1, 1, tzinfo=UTC)).days / 365.25
        return min(_WEIGHT_PUSH_MAX, max(0.0, years))
    except ValueError:
        return 0.0


class _ScoredCandidate:
    __slots__ = (
        "candidate_id",
        "verification_status",
        "rank_score",
        "ranking_reason",
        "tie_break",
        "total_score",
    )

    def __init__(
        self,
        *,
        candidate_id: str,
        verification_status: VerificationStatus,
        rank_score: RankScore,
        ranking_reason: str,
        tie_break: tuple,
        total_score: float,
    ) -> None:
        self.candidate_id = candidate_id
        self.verification_status = verification_status
        self.rank_score = rank_score
        self.ranking_reason = ranking_reason
        self.tie_break = tie_break
        self.total_score = total_score
