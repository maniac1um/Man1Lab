from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from models.paper_reproduction_analysis import (
    SCHEMA_VERSION as ANALYSIS_SCHEMA_VERSION,
    PaperReproductionAnalysis,
)
from models.research_resource_discovery import (
    SCHEMA_VERSION,
    AnalysisGapSnapshot,
    AnalysisReference,
    CandidateResources,
    CollectionSource,
    DiscoveryGap,
    DiscoveryGaps,
    DiscoveryGapType,
    DiscoveryMetadata,
    DiscoveryProvenance,
    DiscoveryStatistics,
    DiscoveryStatus,
    EvidenceCollection,
    EvidenceRecord,
    EvidenceSource,
    GapSeverity,
    InvocationReason,
    ObservedFact,
    PaperRelation,
    ProviderRecord,
    RankingResult,
    RecommendedAction,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceIdentity,
    ResourceNeed,
    SelectionReason,
    SelectionRecord,
    SelectionResult,
    VerificationCollection,
    VerificationDimension,
    VerificationRecord,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from validation.research_resource_discovery import build_research_resource_discovery


class ResearchResourceDiscoveryBuilder:
    """Assembles canonical ResearchResourceDiscovery from stage outputs only."""

    @staticmethod
    def build(
        *,
        analysis: PaperReproductionAnalysis,
        collection: CollectionProviderResult,
        evidence: EvidenceProviderResult,
        verification: VerificationProviderResult,
        ranking: RankingResult,
        selection: SelectionResult,
        discovery_gaps: DiscoveryGaps,
        discovery_run_id: str | None = None,
        pipeline_version: str = "1.2.0",
        invocation_reason: InvocationReason = InvocationReason.GAP_TRIGGERED,
        stage_timestamps: dict[str, datetime] | None = None,
    ) -> ResearchResourceDiscovery:
        now = datetime.now(UTC)
        discovery_id = str(uuid.uuid4())
        run_id = discovery_run_id or discovery_id
        timestamps = stage_timestamps or {}

        candidates = list(collection.candidates)
        evidence_records = list(evidence.evidence_records)
        verification_records = list(verification.verification_records)
        provider_outcomes = (
            list(collection.provider_outcomes)
            + list(evidence.provider_outcomes)
            + list(verification.provider_outcomes)
        )

        analysis_reference = _build_analysis_reference(analysis)
        candidate_resources = CandidateResources(
            candidates=candidates,
            indexes=_index_candidates(candidates),
        )
        evidence_collection = EvidenceCollection(
            records=evidence_records,
            indexes=_index_evidence(evidence_records),
        )
        verification_collection = VerificationCollection(
            records=verification_records,
            indexes=_index_verification(verification_records),
        )

        selection_count = sum(
            1 for item in selection.selections if item.primary_candidate_id is not None
        )
        unresolved_gap_count = len(discovery_gaps.gaps)
        status = _resolve_status(
            candidate_count=len(candidates),
            selection_count=selection_count,
            unresolved_gap_count=unresolved_gap_count,
        )

        metadata = DiscoveryMetadata(
            discovery_id=discovery_id,
            created_at=now,
            status=status,
            summary=_build_summary(status, len(candidates), selection_count, unresolved_gap_count),
            reproduction_scope=analysis.goal.scope.value,
            invocation_reason=invocation_reason,
            candidate_count=len(candidates),
            selection_count=selection_count,
            unresolved_gap_count=unresolved_gap_count,
        )
        provenance = DiscoveryProvenance(
            discovery_run_id=run_id,
            pipeline_version=pipeline_version,
            stage_timestamps=timestamps,
            providers_used=provider_outcomes,
            degradation_notes=[],
        )
        statistics = DiscoveryStatistics(
            candidate_count=len(candidates),
            selection_count=selection_count,
            unresolved_gap_count=unresolved_gap_count,
            evidence_count=len(evidence_records),
            verification_count=len(verification_records),
        )

        artifact = ResearchResourceDiscovery(
            metadata=metadata,
            provenance=provenance,
            analysis_reference=analysis_reference,
            candidate_resources=candidate_resources,
            evidence=evidence_collection,
            verification=verification_collection,
            ranking=ranking,
            selection=selection,
            discovery_gaps=discovery_gaps,
            statistics=statistics,
            schema_version=SCHEMA_VERSION,
        )
        return build_research_resource_discovery(artifact.model_dump(mode="json"))


class DiscoveryWorkflow:
    """Discovery coordinator — five fixed stages, then builder assembly."""

    def __init__(
        self,
        collection_service: CollectionService,
        evidence_service: EvidenceService,
        verification_service: VerificationService,
        ranking_service: RankingService,
    ) -> None:
        self._collection_service = collection_service
        self._evidence_service = evidence_service
        self._verification_service = verification_service
        self._ranking_service = ranking_service

    def run(self, analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
        timestamps: dict[str, datetime] = {}

        timestamps["candidate_collection"] = datetime.now(UTC)
        collection = self._collection_service.collect(analysis)

        timestamps["evidence_collection"] = datetime.now(UTC)
        evidence = self._evidence_service.collect(analysis, collection)

        timestamps["verification"] = datetime.now(UTC)
        verification = self._verification_service.verify(analysis, collection, evidence)

        timestamps["ranking"] = datetime.now(UTC)
        ranking = self._ranking_service.rank(analysis, collection, evidence, verification)

        timestamps["selection"] = datetime.now(UTC)
        selection, discovery_gaps = _run_selection_stage(
            collection.resource_needs,
            ranking,
            analysis,
        )

        timestamps["assembly"] = datetime.now(UTC)
        return ResearchResourceDiscoveryBuilder.build(
            analysis=analysis,
            collection=collection,
            evidence=evidence,
            verification=verification,
            ranking=ranking,
            selection=selection,
            discovery_gaps=discovery_gaps,
            stage_timestamps=timestamps,
        )

    @classmethod
    def default(cls) -> DiscoveryWorkflow:
        return cls(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )


def _run_selection_stage(
    resource_needs: list[ResourceNeed],
    ranking: RankingResult,
    analysis: PaperReproductionAnalysis,
) -> tuple[SelectionResult, DiscoveryGaps]:
    selections = [
        SelectionRecord(
            selection_id=f"selection-{need.need_id}",
            resource_need=need,
            primary_candidate_id=None,
            fallback_candidate_ids=[],
            selection_reason=SelectionReason(
                summary="Skeleton selection — no eligible candidates.",
            ),
            confidence=0.0,
            selected_at=datetime.now(UTC),
            rank_list_id=f"rank-{need.need_id}",
            verification_snapshot={},
        )
        for need in resource_needs
    ]
    gaps = _derive_discovery_gaps(analysis, resource_needs)
    closed, remaining = _gap_closure_lists(analysis, gaps)
    discovery_gaps = DiscoveryGaps(
        gaps=gaps,
        analysis_gaps_closed=closed,
        analysis_gaps_remaining=remaining,
    )
    del ranking
    return SelectionResult(selections=selections), discovery_gaps


def _derive_discovery_gaps(
    analysis: PaperReproductionAnalysis,
    resource_needs: list[ResourceNeed],
) -> list[DiscoveryGap]:
    if resource_needs:
        return []

    gaps: list[DiscoveryGap] = []
    for index, gap in enumerate(analysis.reproduction_gaps):
        gaps.append(
            DiscoveryGap(
                gap_id=f"gap-{index}",
                gap_type=_map_analysis_gap_to_discovery_gap(gap.category.value),
                severity=GapSeverity.BLOCKING,
                resource_need_id=None,
                description=f"Discovery skeleton could not resolve: {gap.description}",
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
                description="Skeleton discovery produced no resource needs or candidates.",
                recommended_action=RecommendedAction.RETRY_DISCOVERY,
            )
        )
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


def _build_analysis_reference(analysis: PaperReproductionAnalysis) -> AnalysisReference:
    return AnalysisReference(
        analysis_schema_version=analysis.schema_version or ANALYSIS_SCHEMA_VERSION,
        paper_title=analysis.metadata.title,
        arxiv_id=analysis.metadata.arxiv_id,
        source_path=str(analysis.metadata.source_path) if analysis.metadata.source_path else None,
        analysis_content_hash=_analysis_content_hash(analysis),
        analysis_gaps_addressed=[
            gap.category.value for gap in analysis.reproduction_gaps
        ],
        analysis_gaps_snapshot=[
            AnalysisGapSnapshot(category=gap.category.value, description=gap.description)
            for gap in analysis.reproduction_gaps
        ],
    )


def _analysis_content_hash(analysis: PaperReproductionAnalysis) -> str:
    payload = analysis.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _index_candidates(candidates: list[RepositoryCandidate]) -> dict[str, list[str]]:
    by_type: dict[str, list[str]] = {}
    for candidate in candidates:
        key = candidate.resource_type.value
        by_type.setdefault(key, []).append(candidate.candidate_id)
    return {"by_resource_type": by_type.get("official_repository", [])} if by_type else {}


def _index_evidence(records: list[EvidenceRecord]) -> dict[str, list[str]]:
    by_candidate: dict[str, list[str]] = {}
    for record in records:
        by_candidate.setdefault(record.candidate_id, []).append(record.evidence_id)
    return {"by_candidate_id": list(by_candidate.keys())} if by_candidate else {}


def _index_verification(records: list[VerificationRecord]) -> dict[str, list[str]]:
    by_candidate = [record.candidate_id for record in records]
    return {"by_candidate_id": by_candidate} if by_candidate else {}


def _resolve_status(
    *,
    candidate_count: int,
    selection_count: int,
    unresolved_gap_count: int,
) -> DiscoveryStatus:
    if candidate_count == 0 and selection_count == 0:
        return DiscoveryStatus.PARTIAL
    if unresolved_gap_count > 0:
        return DiscoveryStatus.PARTIAL
    return DiscoveryStatus.COMPLETE


def _build_summary(
    status: DiscoveryStatus,
    candidate_count: int,
    selection_count: int,
    unresolved_gap_count: int,
) -> str:
    return (
        f"Discovery {status.value}: {candidate_count} candidates, "
        f"{selection_count} selections, {unresolved_gap_count} unresolved gaps."
    )
