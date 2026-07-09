"""Tests for discovery selection stage."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from discovery.selection import run_selection, update_candidate_statuses_after_selection
from discovery.workflow import DiscoveryWorkflow
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    AnalysisResources,
    ArtifactReference,
    ArtifactType,
    DatasetResource,
    ExternalResource,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from models.research_resource_discovery import (
    CandidateStatus,
    CollectionSource,
    CollectionSourceType,
    DiscoveryGapType,
    DiscoveryProvider,
    EvidenceRecord,
    EvidencePolarity,
    EvidenceSource,
    EvidenceType,
    GapSeverity,
    NeedCategory,
    Officiality,
    ObservedFact,
    RankList,
    RankingResult,
    RankScore,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceNeed,
    ResourceType,
    VerificationRecord,
    VerificationStatus,
)
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.test_discovery_collection import _analysis_with_embedded_resources


def _repo_need() -> ResourceNeed:
    return ResourceNeed(
        need_id="need-repo",
        need_category=NeedCategory.CODE_REPOSITORY,
        description="Official repository",
        analysis_gap_index=0,
    )


def _repo_candidate(*, candidate_id: str = "candidate-repo") -> RepositoryCandidate:
    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.GITHUB,
            provider_native_id="KaimingHe/deep-residual-networks",
            normalized_url="https://github.com/KaimingHe/deep-residual-networks",
        ),
        provider=DiscoveryProvider.GITHUB,
        resource_type=ResourceType.OFFICIAL_REPOSITORY,
        officiality=Officiality.OFFICIAL,
        url="https://github.com/KaimingHe/deep-residual-networks",
        collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
        addresses_needs=["need-repo"],
    )


def _verification(candidate_id: str, status: VerificationStatus) -> VerificationRecord:
    return VerificationRecord(
        verification_id=f"verify-{candidate_id}",
        candidate_id=candidate_id,
        status=status,
        verified_at=datetime.now(UTC),
    )


def _rank_list(*, eligible: list[str], ordered: list[str] | None = None) -> RankList:
    need = _repo_need()
    ordered_ids = ordered or eligible
    return RankList(
        rank_list_id=f"rank-{need.need_id}",
        resource_need=need,
        ordered_candidate_ids=ordered_ids,
        eligible_candidate_ids=eligible,
        scores={
            candidate_id: RankScore(candidate_id=candidate_id, total_score=5.0 - index)
            for index, candidate_id in enumerate(ordered_ids)
        },
    )


class DiscoverySelectionPolicyTest(unittest.TestCase):
    def test_selects_top_eligible_candidate_with_confidence(self) -> None:
        candidate = _repo_candidate()
        analysis = _analysis_with_embedded_resources()
        selection, gaps = run_selection(
            resource_needs=[_repo_need()],
            ranking=RankingResult(rank_lists=[_rank_list(eligible=[candidate.candidate_id])]),
            candidates=[candidate],
            verification_records=[_verification(candidate.candidate_id, VerificationStatus.PASS)],
            evidence_records=[],
            analysis=analysis,
        )
        record = selection.selections[0]
        self.assertEqual(record.primary_candidate_id, candidate.candidate_id)
        self.assertGreater(record.confidence, 0.8)
        self.assertIn("verification_status:pass", record.selection_reason.deciding_factors)
        self.assertEqual(gaps.gaps, [])

    def test_emits_gap_when_no_eligible_candidates(self) -> None:
        candidate = _repo_candidate()
        analysis = _analysis_with_embedded_resources()
        _, gaps = run_selection(
            resource_needs=[_repo_need()],
            ranking=RankingResult(
                rank_lists=[
                    _rank_list(eligible=[], ordered=[candidate.candidate_id]),
                ]
            ),
            candidates=[candidate],
            verification_records=[_verification(candidate.candidate_id, VerificationStatus.FAIL)],
            evidence_records=[],
            analysis=analysis,
        )
        self.assertEqual(len(gaps.gaps), 1)
        self.assertEqual(gaps.gaps[0].gap_type, DiscoveryGapType.NO_VIABLE_REPOSITORY)
        self.assertIn(gaps.gaps[0].severity, {GapSeverity.BLOCKING, GapSeverity.DEGRADED})

    def test_partial_verification_still_selects(self) -> None:
        candidate = _repo_candidate()
        analysis = _analysis_with_embedded_resources()
        selection, _ = run_selection(
            resource_needs=[_repo_need()],
            ranking=RankingResult(rank_lists=[_rank_list(eligible=[candidate.candidate_id])]),
            candidates=[candidate],
            verification_records=[_verification(candidate.candidate_id, VerificationStatus.PARTIAL)],
            evidence_records=[],
            analysis=analysis,
        )
        record = selection.selections[0]
        self.assertEqual(record.primary_candidate_id, candidate.candidate_id)
        self.assertGreaterEqual(record.confidence, 0.6)

    def test_marks_candidate_status_after_selection(self) -> None:
        candidate = _repo_candidate()
        fallback = _repo_candidate(candidate_id="candidate-zzz-fallback")
        analysis = _analysis_with_embedded_resources()
        selection, _ = run_selection(
            resource_needs=[_repo_need()],
            ranking=RankingResult(
                rank_lists=[_rank_list(eligible=[candidate.candidate_id, fallback.candidate_id])]
            ),
            candidates=[candidate, fallback],
            verification_records=[
                _verification(candidate.candidate_id, VerificationStatus.PASS),
                _verification(fallback.candidate_id, VerificationStatus.PASS),
            ],
            evidence_records=[],
            analysis=analysis,
        )
        updated = update_candidate_statuses_after_selection([candidate, fallback], selection)
        statuses = {item.candidate_id: item.status for item in updated}
        self.assertEqual(statuses[candidate.candidate_id], CandidateStatus.SELECTED_PRIMARY)
        self.assertEqual(statuses[fallback.candidate_id], CandidateStatus.SELECTED_FALLBACK)


class DiscoveryWorkflowSelectionIntegrationTest(unittest.TestCase):
    def test_embedded_workflow_produces_repository_selection(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_embedded_resources())
        repo_selections = [
            item
            for item in discovery.selection.selections
            if item.resource_need.need_category == NeedCategory.CODE_REPOSITORY
        ]
        self.assertEqual(len(repo_selections), 1)
        self.assertIsNotNone(repo_selections[0].primary_candidate_id)
        self.assertGreater(repo_selections[0].confidence, 0.0)
        self.assertGreater(discovery.metadata.selection_count, 0)


if __name__ == "__main__":
    unittest.main()
