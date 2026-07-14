"""Deterministic ranking using verification status only."""

from __future__ import annotations

from datetime import UTC, datetime

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    ProviderInvocationStatus,
    ProviderRecord,
    RankingFactor,
    RankList,
    RankScore,
    RepositoryCandidate,
    VerificationRecord,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.ranking_provider import RankingProviderResult
from ports.verification_provider import VerificationProviderResult

_PROVIDER_NAME = "embedded_ranking"
_PROVIDER_VERSION = "1.0.0"

_STATUS_PRECEDENCE = {
    VerificationStatus.PASS: 5,
    VerificationStatus.PARTIAL: 4,
    VerificationStatus.SKIPPED: 3,
    VerificationStatus.FAIL: 2,
    VerificationStatus.ERROR: 1,
}

_ELIGIBLE_STATUSES = {
    VerificationStatus.PASS,
    VerificationStatus.PARTIAL,
}


class EmbeddedRankingProvider:
    """Rank candidates by verification status — no network, no heuristics."""

    def rank(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
        verification_result: VerificationProviderResult,
    ) -> RankingProviderResult:
        del analysis, evidence_result
        now = datetime.now(UTC)
        status_by_candidate = _verification_status_map(verification_result.verification_records)
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
            ordered = _order_candidates(candidates, status_by_candidate, candidate_index)
            scores = {
                candidate_id: _score_for_candidate(candidate_id, status_by_candidate)
                for candidate_id in ordered
            }
            eligible = [
                candidate_id
                for candidate_id in ordered
                if status_by_candidate.get(candidate_id, VerificationStatus.SKIPPED)
                in _ELIGIBLE_STATUSES
            ]
            rank_lists.append(
                RankList(
                    rank_list_id=f"rank-{need.need_id}",
                    resource_need=need,
                    ordered_candidate_ids=ordered,
                    scores=scores,
                    ranking_factors_summary=(
                        "Deterministic ranking by verification status "
                        "(pass > partial > skipped > fail > error)."
                    ),
                    eligible_candidate_ids=eligible,
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


def _verification_status_map(records: list[VerificationRecord]) -> dict[str, VerificationStatus]:
    return {record.candidate_id: record.status for record in records}


def _order_candidates(
    candidates: list[RepositoryCandidate],
    status_by_candidate: dict[str, VerificationStatus],
    candidate_index: dict[str, int],
) -> list[str]:
    indexed = list(enumerate(candidates))
    indexed.sort(
        key=lambda item: (
            -_STATUS_PRECEDENCE.get(
                status_by_candidate.get(item[1].candidate_id, VerificationStatus.SKIPPED),
                _STATUS_PRECEDENCE[VerificationStatus.SKIPPED],
            ),
            candidate_index.get(item[1].candidate_id, item[0]),
        )
    )
    return [candidate.candidate_id for _, candidate in indexed]


def _score_for_candidate(
    candidate_id: str,
    status_by_candidate: dict[str, VerificationStatus],
) -> RankScore:
    status = status_by_candidate.get(candidate_id, VerificationStatus.SKIPPED)
    score_value = float(_STATUS_PRECEDENCE[status])
    return RankScore(
        candidate_id=candidate_id,
        total_score=score_value,
        factor_scores={"verification_status": score_value},
        ranking_factors=[
            RankingFactor(
                name="verification_status",
                score=score_value,
                weight=1.0,
                summary=f"verification status: {status.value}",
            )
        ],
    )
