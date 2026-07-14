"""Immutable observed facts — objective state only, no engineering decisions."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.explainable_confidence import ConfidenceContribution, ExplainableConfidence
from models.research_resource_discovery import (
    DiscoveryGap,
    DiscoveryGapType,
    DiscoveryStatus,
    GapSeverity,
    NeedCategory,
    Officiality,
    RepositoryCandidate,
    ResearchAssetType,
    ResearchResourceDiscovery,
    ResourceType,
    SelectionRecord,
    VerificationStatus,
)


@dataclass(frozen=True)
class SelectedResourceFact:
    """A discovery selection with resolved candidate and verification state."""

    selection_id: str
    need_id: str
    need_category: NeedCategory
    candidate_id: str
    candidate: RepositoryCandidate
    verification_status: VerificationStatus | None
    selection_confidence: float = 0.0
    confidence_composition: ExplainableConfidence = field(default_factory=ExplainableConfidence)
    asset_type: ResearchAssetType | None = None
    is_primary: bool = True


@dataclass(frozen=True)
class ObservedFacts:
    """Objective observations derived from analysis and discovery."""

    discovery_status: DiscoveryStatus
    selected_repository: SelectedResourceFact | None
    selected_checkpoint: SelectedResourceFact | None
    selected_dataset: SelectedResourceFact | None
    supplementary_resources: tuple[SelectedResourceFact, ...]
    required_resource_gaps: tuple[DiscoveryGap, ...]
    blocking_discovery_gaps: tuple[DiscoveryGap, ...]
    repository_available: bool
    repository_official: bool
    repository_verified: bool
    repository_archived: bool
    checkpoint_available: bool
    dataset_available: bool
    repository_usable: bool
    selected_assets: tuple[SelectedResourceFact, ...]
    confidence_contributions: tuple[ConfidenceContribution, ...]


def build_observed_facts(
    analysis: PaperReproductionAnalysis,
    discovery: ResearchResourceDiscovery,
) -> ObservedFacts:
    del analysis
    candidate_index = {
        candidate.candidate_id: candidate for candidate in discovery.candidate_resources.candidates
    }
    asset_type_by_candidate = {
        asset.candidate_id: asset.asset_type for asset in discovery.research_assets.assets
    }
    selections = _selected_resources(discovery, candidate_index, asset_type_by_candidate)
    supplementary = _supplementary_resources(discovery, candidate_index, asset_type_by_candidate)

    selected_repository = _first_for_category(selections, NeedCategory.CODE_REPOSITORY)
    selected_checkpoint = _first_for_category(selections, NeedCategory.CHECKPOINT)
    selected_dataset = _first_for_category(selections, NeedCategory.DATASET)

    required_gaps = tuple(
        gap
        for gap in discovery.discovery_gaps.gaps
        if gap.severity in {GapSeverity.BLOCKING, GapSeverity.DEGRADED}
    )
    blocking_gaps = tuple(
        gap for gap in discovery.discovery_gaps.gaps if gap.severity == GapSeverity.BLOCKING
    )

    repository_verified = (
        selected_repository is not None
        and selected_repository.verification_status == VerificationStatus.PASS
    )
    repository_usable = (
        selected_repository is not None
        and selected_repository.verification_status
        in {VerificationStatus.PASS, VerificationStatus.PARTIAL}
    )

    return ObservedFacts(
        discovery_status=discovery.metadata.status,
        selected_repository=selected_repository,
        selected_checkpoint=selected_checkpoint,
        selected_dataset=selected_dataset,
        supplementary_resources=supplementary,
        required_resource_gaps=required_gaps,
        blocking_discovery_gaps=blocking_gaps,
        repository_available=selected_repository is not None,
        repository_official=_is_official_repository(selected_repository),
        repository_verified=repository_verified,
        repository_archived=_repository_archived(discovery, selected_repository),
        checkpoint_available=_resource_verified(selected_checkpoint),
        dataset_available=_resource_verified(selected_dataset),
        repository_usable=repository_usable,
        selected_assets=selections,
        confidence_contributions=_aggregate_confidence_contributions(discovery),
    )


def _selected_resources(
    discovery: ResearchResourceDiscovery,
    candidate_index: dict[str, RepositoryCandidate],
    asset_type_by_candidate: dict[str, ResearchAssetType],
) -> tuple[SelectedResourceFact, ...]:
    facts: list[SelectedResourceFact] = []
    composition_by_selection = {
        record.selection_id: record.confidence_composition for record in discovery.selection.selections
    }
    for selection in discovery.selection.selections:
        if not selection.primary_candidate_id:
            continue
        candidate = candidate_index.get(selection.primary_candidate_id)
        if candidate is None:
            continue
        composition = composition_by_selection.get(selection.selection_id, selection.confidence_composition)
        facts.append(
            SelectedResourceFact(
                selection_id=selection.selection_id,
                need_id=selection.resource_need.need_id,
                need_category=selection.resource_need.need_category,
                candidate_id=candidate.candidate_id,
                candidate=candidate,
                verification_status=_verification_status(discovery, candidate.candidate_id),
                selection_confidence=selection.confidence,
                confidence_composition=composition,
                asset_type=asset_type_by_candidate.get(candidate.candidate_id),
                is_primary=True,
            )
        )
    return tuple(facts)


def _supplementary_resources(
    discovery: ResearchResourceDiscovery,
    candidate_index: dict[str, RepositoryCandidate],
    asset_type_by_candidate: dict[str, ResearchAssetType],
) -> tuple[SelectedResourceFact, ...]:
    facts: list[SelectedResourceFact] = []
    for selection in discovery.selection.selections:
        composition = selection.confidence_composition
        for fallback_id in selection.fallback_candidate_ids:
            candidate = candidate_index.get(fallback_id)
            if candidate is None:
                continue
            facts.append(
                SelectedResourceFact(
                    selection_id=selection.selection_id,
                    need_id=selection.resource_need.need_id,
                    need_category=selection.resource_need.need_category,
                    candidate_id=candidate.candidate_id,
                    candidate=candidate,
                    verification_status=_verification_status(discovery, candidate.candidate_id),
                    selection_confidence=selection.confidence,
                    confidence_composition=composition,
                    asset_type=asset_type_by_candidate.get(candidate.candidate_id),
                    is_primary=False,
                )
            )
    return tuple(facts)


def _aggregate_confidence_contributions(
    discovery: ResearchResourceDiscovery,
) -> tuple[ConfidenceContribution, ...]:
    merged: dict[str, ConfidenceContribution] = {}
    for selection in discovery.selection.selections:
        if selection.primary_candidate_id is None:
            continue
        for contribution in selection.confidence_composition.contributions:
            existing = merged.get(contribution.signal)
            if existing is None or contribution.contribution > existing.contribution:
                merged[contribution.signal] = contribution
    return tuple(merged[s] for s in sorted(merged))


def _first_for_category(
    selections: tuple[SelectedResourceFact, ...],
    category: NeedCategory,
) -> SelectedResourceFact | None:
    for selection in selections:
        if selection.need_category == category:
            return selection
    return None


def _verification_status(
    discovery: ResearchResourceDiscovery,
    candidate_id: str,
) -> VerificationStatus | None:
    for record in discovery.verification.records:
        if record.candidate_id == candidate_id:
            return record.status
    return None


def _is_official_repository(selection: SelectedResourceFact | None) -> bool:
    if selection is None:
        return False
    candidate = selection.candidate
    if candidate.resource_type != ResourceType.OFFICIAL_REPOSITORY:
        return False
    return candidate.officiality in {Officiality.OFFICIAL, Officiality.AUTHOR_AFFILIATED}


def _resource_verified(selection: SelectedResourceFact | None) -> bool:
    return selection is not None and selection.verification_status == VerificationStatus.PASS


def _repository_archived(
    discovery: ResearchResourceDiscovery,
    selection: SelectedResourceFact | None,
) -> bool:
    if selection is not None and selection.candidate.status.value == "rejected":
        return True
    for gap in discovery.discovery_gaps.gaps:
        if gap.gap_type == DiscoveryGapType.REPOSITORY_ARCHIVED:
            return True
    return False
