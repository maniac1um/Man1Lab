from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
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
    DiscoveryGaps,
    DiscoveryMetadata,
    DiscoveryProvenance,
    DiscoveryStatistics,
    DiscoveryStatus,
    EvidenceCollection,
    EvidenceRecord,
    EvidenceSource,
    InvocationReason,
    ObservedFact,
    PaperRelation,
    ProviderRecord,
    RankingResult,
    RepositoryCandidate,
    ResearchResourceDiscovery,
    ResourceIdentity,
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
from discovery.selection import run_selection, update_candidate_statuses_after_selection
from discovery.assets import build_research_assets
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
        research_assets = build_research_assets(candidates, selection)
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
            research_assets=research_assets,
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
        selection, discovery_gaps = run_selection(
            resource_needs=collection.resource_needs,
            ranking=ranking,
            candidates=collection.candidates,
            verification_records=verification.verification_records,
            evidence_records=evidence.evidence_records,
            analysis=analysis,
        )
        collection = replace(
            collection,
            candidates=update_candidate_statuses_after_selection(collection.candidates, selection),
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
    if not by_type:
        return {}
    return {"by_resource_type": by_type.get("official_repository", [])}


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
