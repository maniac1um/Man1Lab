"""Evidence-backed resource selection from ranking and verification outputs."""

from __future__ import annotations

from datetime import UTC, datetime

from discovery.confidence import compose_selection_confidence
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    AnalysisGapSnapshot,
    CandidateStatus,
    DiscoveryGap,
    DiscoveryGaps,
    DiscoveryGapType,
    EvidenceRecord,
    GapSeverity,
    NeedCategory,
    Officiality,
    RankList,
    RankingResult,
    RankScore,
    RecommendedAction,
    RepositoryCandidate,
    ResourceType,
    SelectionReason,
    SelectionRecord,
    SelectionResult,
    VerificationRecord,
    VerificationStatus,
)

_ELIGIBLE_STATUSES = {VerificationStatus.PASS, VerificationStatus.PARTIAL}
_OFFICIALITY_PRECEDENCE = {
    Officiality.OFFICIAL: 4,
    Officiality.AUTHOR_AFFILIATED: 3,
    Officiality.COMMUNITY: 2,
    Officiality.THIRD_PARTY: 1,
    Officiality.UNKNOWN: 0,
}
_TYPE_PRECEDENCE = {
    ResourceType.OFFICIAL_REPOSITORY: 3,
    ResourceType.COMMUNITY_REPOSITORY: 2,
    ResourceType.PROJECT_PAGE: 1,
}


def run_selection(
    *,
    resource_needs: list,
    ranking: RankingResult,
    candidates: list[RepositoryCandidate],
    verification_records: list[VerificationRecord],
    evidence_records: list[EvidenceRecord],
    analysis: PaperReproductionAnalysis,
) -> tuple[SelectionResult, DiscoveryGaps]:
    """Commit primary/fallback selections per resource need from ranked eligible candidates."""
    now = datetime.now(UTC)
    candidate_index = {candidate.candidate_id: candidate for candidate in candidates}
    verification_by_candidate = {record.candidate_id: record for record in verification_records}
    evidence_by_candidate = _group_evidence(evidence_records)
    rank_list_by_need = {rank_list.resource_need.need_id: rank_list for rank_list in ranking.rank_lists}

    selections: list[SelectionRecord] = []
    gaps: list[DiscoveryGap] = []

    for need in resource_needs:
        rank_list = rank_list_by_need.get(need.need_id)
        selection, gap = _select_for_need(
            need=need,
            rank_list=rank_list,
            candidate_index=candidate_index,
            verification_by_candidate=verification_by_candidate,
            evidence_by_candidate=evidence_by_candidate,
            selected_at=now,
        )
        selections.append(selection)
        if gap is not None:
            gaps.append(gap)

    gaps.extend(_derive_unmet_analysis_gaps(analysis, resource_needs, selections, gaps))
    closed, remaining = _gap_closure_lists(analysis, gaps)
    return (
        SelectionResult(selections=selections),
        DiscoveryGaps(
            gaps=gaps,
            analysis_gaps_closed=closed,
            analysis_gaps_remaining=remaining,
        ),
    )


def _select_for_need(
    *,
    need,
    rank_list: RankList | None,
    candidate_index: dict[str, RepositoryCandidate],
    verification_by_candidate: dict[str, VerificationRecord],
    evidence_by_candidate: dict[str, list[EvidenceRecord]],
    selected_at: datetime,
) -> tuple[SelectionRecord, DiscoveryGap | None]:
    rank_list_id = rank_list.rank_list_id if rank_list is not None else f"rank-{need.need_id}"
    if rank_list is None or not rank_list.ordered_candidate_ids:
        return (
            _empty_selection(
                need=need,
                rank_list_id=rank_list_id,
                selected_at=selected_at,
                summary="No ranked candidates available for this resource need.",
                policy="no_candidates",
                rejected_ids=[],
            ),
            _gap_for_unresolved_need(
                need=need,
                gap_type=_gap_type_for_need(need.need_category),
                description=f"No candidates collected for {need.need_category.value} need.",
                examined=[],
            ),
        )

    eligible = _order_eligible(
        rank_list.eligible_candidate_ids,
        candidate_index,
        verification_by_candidate,
        rank_list.ordered_candidate_ids,
    )
    if not eligible:
        examined = list(rank_list.ordered_candidate_ids)
        return (
            _empty_selection(
                need=need,
                rank_list_id=rank_list_id,
                selected_at=selected_at,
                summary="No verification-eligible candidates for this resource need.",
                policy="verification_gate",
                rejected_ids=examined,
            ),
            _gap_for_unresolved_need(
                need=need,
                gap_type=DiscoveryGapType.NO_VIABLE_REPOSITORY
                if need.need_category == NeedCategory.CODE_REPOSITORY
                else _gap_type_for_need(need.need_category),
                description=(
                    f"Candidates examined for {need.need_category.value} but none passed "
                    "verification eligibility (pass or partial required)."
                ),
                examined=examined,
            ),
        )

    primary_id = eligible[0]
    fallback_ids = eligible[1:]
    verification_record = verification_by_candidate.get(primary_id)
    status = verification_record.status if verification_record is not None else VerificationStatus.SKIPPED
    rank_score = rank_list.scores.get(primary_id)
    candidate = candidate_index.get(primary_id)
    evidence_ids = _supporting_evidence_ids(primary_id, evidence_by_candidate)
    candidate_evidence = evidence_by_candidate.get(primary_id, [])
    confidence_composition = compose_selection_confidence(
        candidate=candidate,
        verification_record=verification_record,
        evidence_records=candidate_evidence,
        rank_score=rank_score,
        need_category_value=need.need_category.value,
    )
    confidence = confidence_composition.overall
    rejected = [
        candidate_id
        for candidate_id in rank_list.ordered_candidate_ids
        if candidate_id not in {primary_id, *fallback_ids}
    ]

    snapshot = _verification_snapshot(eligible, verification_by_candidate)
    summary = _selection_summary(
        need=need,
        primary_id=primary_id,
        candidate_index=candidate_index,
        status=status,
        fallback_count=len(fallback_ids),
    )
    factors = _deciding_factors(status, candidate_index.get(primary_id), rank_list)

    selection = SelectionRecord(
        selection_id=f"selection-{need.need_id}",
        resource_need=need,
        primary_candidate_id=primary_id,
        fallback_candidate_ids=fallback_ids,
        selection_reason=SelectionReason(
            summary=summary,
            deciding_factors=factors,
            evidence_ids=evidence_ids,
            rejected_candidate_ids=rejected,
            policy_applied=_selection_policy(candidate_index.get(primary_id)),
        ),
        confidence=confidence,
        confidence_composition=confidence_composition,
        selected_at=selected_at,
        rank_list_id=rank_list_id,
        verification_snapshot=snapshot,
    )
    return selection, None


def _empty_selection(
    *,
    need,
    rank_list_id: str,
    selected_at: datetime,
    summary: str,
    policy: str,
    rejected_ids: list[str],
) -> SelectionRecord:
    return SelectionRecord(
        selection_id=f"selection-{need.need_id}",
        resource_need=need,
        primary_candidate_id=None,
        fallback_candidate_ids=[],
        selection_reason=SelectionReason(
            summary=summary,
            deciding_factors=["no_eligible_candidate"],
            rejected_candidate_ids=rejected_ids,
            policy_applied=policy,
        ),
        confidence=0.0,
        selected_at=selected_at,
        rank_list_id=rank_list_id,
        verification_snapshot={},
    )


def _order_eligible(
    eligible_ids: list[str],
    candidate_index: dict[str, RepositoryCandidate],
    verification_by_candidate: dict[str, VerificationRecord],
    rank_order: list[str],
) -> list[str]:
    rank_index = {candidate_id: index for index, candidate_id in enumerate(rank_order)}

    def sort_key(candidate_id: str) -> tuple[int, int, int, int]:
        record = verification_by_candidate.get(candidate_id)
        status = record.status if record is not None else VerificationStatus.SKIPPED
        status_rank = {
            VerificationStatus.PASS: 2,
            VerificationStatus.PARTIAL: 1,
        }.get(status, 0)
        candidate = candidate_index.get(candidate_id)
        officiality_rank = _OFFICIALITY_PRECEDENCE.get(
            candidate.officiality if candidate is not None else Officiality.UNKNOWN,
            0,
        )
        type_rank = _TYPE_PRECEDENCE.get(
            candidate.resource_type if candidate is not None else ResourceType.CUSTOM,
            0,
        )
        return (
            -status_rank,
            -officiality_rank,
            -type_rank,
            rank_index.get(candidate_id, len(rank_order)),
        )

    return sorted(eligible_ids, key=sort_key)


def _selection_confidence(
    status: VerificationStatus,
    rank_score: RankScore | None,
) -> float:
    base = {
        VerificationStatus.PASS: 0.9,
        VerificationStatus.PARTIAL: 0.65,
    }.get(status, 0.0)
    if rank_score is None:
        return round(base, 2)
    normalized = min(1.0, max(0.0, rank_score.total_score / 5.0))
    return round(min(1.0, base + 0.1 * normalized), 2)


def _verification_snapshot(
    candidate_ids: list[str],
    verification_by_candidate: dict[str, VerificationRecord],
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for candidate_id in candidate_ids:
        record = verification_by_candidate.get(candidate_id)
        if record is not None:
            snapshot[candidate_id] = record.status.value
    return snapshot


def _selection_summary(
    *,
    need,
    primary_id: str,
    candidate_index: dict[str, RepositoryCandidate],
    status: VerificationStatus,
    fallback_count: int,
) -> str:
    candidate = candidate_index.get(primary_id)
    title = candidate.title if candidate is not None else primary_id
    return (
        f"Selected {title} as primary for {need.need_category.value} "
        f"(verification={status.value}, fallbacks={fallback_count})."
    )


def _deciding_factors(
    status: VerificationStatus,
    candidate: RepositoryCandidate | None,
    rank_list: RankList,
) -> list[str]:
    factors = [
        f"verification_status:{status.value}",
        f"rank_list:{rank_list.rank_list_id}",
    ]
    if candidate is not None:
        factors.append(f"resource_type:{candidate.resource_type.value}")
        factors.append(f"officiality:{candidate.officiality.value}")
    return factors


def _selection_policy(candidate: RepositoryCandidate | None) -> str:
    if candidate is None:
        return "ranked_eligible"
    if candidate.resource_type == ResourceType.OFFICIAL_REPOSITORY:
        return "prefer_official"
    if candidate.resource_type == ResourceType.COMMUNITY_REPOSITORY:
        return "prefer_community_verified"
    return "ranked_eligible"


def _supporting_evidence_ids(
    candidate_id: str,
    evidence_by_candidate: dict[str, list[EvidenceRecord]],
) -> list[str]:
    return [record.evidence_id for record in evidence_by_candidate.get(candidate_id, [])]


def _group_evidence(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    grouped: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        grouped.setdefault(record.candidate_id, []).append(record)
    return grouped


def _gap_for_unresolved_need(
    *,
    need,
    gap_type: DiscoveryGapType,
    description: str,
    examined: list[str],
) -> DiscoveryGap:
    blocking = bool(need.required_for_scope) or gap_type in {
        DiscoveryGapType.NO_VIABLE_REPOSITORY,
        DiscoveryGapType.NO_OFFICIAL_REPOSITORY,
    }
    severity = GapSeverity.BLOCKING if blocking else GapSeverity.DEGRADED
    return DiscoveryGap(
        gap_id=f"gap-{need.need_id}",
        gap_type=gap_type,
        severity=severity,
        resource_need_id=need.need_id,
        description=description,
        related_analysis_gap_index=need.analysis_gap_index,
        candidate_ids_examined=examined,
        recommended_action=_recommended_action_for_gap(gap_type),
    )


def _gap_type_for_need(category: NeedCategory) -> DiscoveryGapType:
    mapping = {
        NeedCategory.CODE_REPOSITORY: DiscoveryGapType.NO_OFFICIAL_REPOSITORY,
        NeedCategory.CHECKPOINT: DiscoveryGapType.CHECKPOINT_MISSING,
        NeedCategory.CONFIG: DiscoveryGapType.CONFIG_MISSING,
        NeedCategory.DATASET: DiscoveryGapType.DATASET_UNAVAILABLE,
    }
    return mapping.get(category, DiscoveryGapType.OTHER)


def _recommended_action_for_gap(gap_type: DiscoveryGapType) -> RecommendedAction:
    mapping = {
        DiscoveryGapType.NO_OFFICIAL_REPOSITORY: RecommendedAction.MANUAL_INPUT,
        DiscoveryGapType.NO_VIABLE_REPOSITORY: RecommendedAction.MANUAL_INPUT,
        DiscoveryGapType.CHECKPOINT_MISSING: RecommendedAction.PROCEED_WITH_PARTIAL,
        DiscoveryGapType.CONFIG_MISSING: RecommendedAction.GENERATE_FROM_SCRATCH,
        DiscoveryGapType.DATASET_UNAVAILABLE: RecommendedAction.MANUAL_INPUT,
    }
    return mapping.get(gap_type, RecommendedAction.MANUAL_INPUT)


def _derive_unmet_analysis_gaps(
    analysis: PaperReproductionAnalysis,
    resource_needs: list,
    selections: list[SelectionRecord],
    existing_gaps: list[DiscoveryGap],
) -> list[DiscoveryGap]:
    if resource_needs:
        return []

    gaps: list[DiscoveryGap] = []
    for index, gap in enumerate(analysis.reproduction_gaps):
        gaps.append(
            DiscoveryGap(
                gap_id=f"gap-analysis-{index}",
                gap_type=_map_analysis_gap_to_discovery_gap(gap.category.value),
                severity=GapSeverity.BLOCKING,
                resource_need_id=None,
                description=f"Discovery could not resolve analysis gap: {gap.description}",
                related_analysis_gap_index=index,
                candidate_ids_examined=[],
                recommended_action=RecommendedAction.MANUAL_INPUT,
            )
        )
    if not gaps and not analysis.reproduction_gaps:
        gaps.append(
            DiscoveryGap(
                gap_id="gap-empty",
                gap_type=DiscoveryGapType.PROVIDER_UNAVAILABLE,
                severity=GapSeverity.INFORMATIONAL,
                description="Discovery produced no resource needs or candidates.",
                recommended_action=RecommendedAction.RETRY_DISCOVERY,
            )
        )
    del selections, existing_gaps
    return gaps


def _map_analysis_gap_to_discovery_gap(category: str) -> DiscoveryGapType:
    mapping = {
        "repository": DiscoveryGapType.NO_OFFICIAL_REPOSITORY,
        "checkpoint": DiscoveryGapType.CHECKPOINT_MISSING,
        "config": DiscoveryGapType.CONFIG_MISSING,
        "dataset_link": DiscoveryGapType.DATASET_UNAVAILABLE,
    }
    return mapping.get(category, DiscoveryGapType.OTHER)


def _gap_closure_lists(
    analysis: PaperReproductionAnalysis,
    discovery_gaps: list[DiscoveryGap],
) -> tuple[list[str], list[str]]:
    unresolved_indexes = {
        gap.related_analysis_gap_index
        for gap in discovery_gaps
        if gap.related_analysis_gap_index is not None
        and gap.severity in {GapSeverity.BLOCKING, GapSeverity.DEGRADED}
    }
    closed: list[str] = []
    remaining: list[str] = []
    for index, gap in enumerate(analysis.reproduction_gaps):
        category = gap.category.value
        if index in unresolved_indexes:
            remaining.append(category)
        else:
            closed.append(category)
    return closed, remaining


def update_candidate_statuses_after_selection(
    candidates: list[RepositoryCandidate],
    selection: SelectionResult,
) -> list[RepositoryCandidate]:
    """Return candidates with selection status markers (append-only — same count)."""
    primary_ids = {
        record.primary_candidate_id
        for record in selection.selections
        if record.primary_candidate_id is not None
    }
    fallback_ids = {
        candidate_id
        for record in selection.selections
        for candidate_id in record.fallback_candidate_ids
    }
    updated: list[RepositoryCandidate] = []
    for candidate in candidates:
        if candidate.candidate_id in primary_ids:
            updated.append(candidate.model_copy(update={"status": CandidateStatus.SELECTED_PRIMARY}))
        elif candidate.candidate_id in fallback_ids:
            updated.append(candidate.model_copy(update={"status": CandidateStatus.SELECTED_FALLBACK}))
        else:
            updated.append(candidate)
    return updated
