import unittest

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
    NeedCategory,
    SCHEMA_VERSION,
    VerificationStatus,
)
from discovery.workflow import DiscoveryWorkflow
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_merge import merge_rank_lists
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService


def _analysis_with_embedded_resources() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Deep Residual Learning for Image Recognition",
            arxiv_id="1512.03385",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce ResNet training on ImageNet.",
        ),
        resources=AnalysisResources(
            datasets=[
                DatasetResource(
                    name="ImageNet",
                    link="https://image-net.org/challenges/LSVRC/2012/",
                )
            ],
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="official-release",
                    url="https://github.com/KaimingHe/deep-residual-networks",
                )
            ],
            artifacts=[
                ArtifactReference(
                    artifact_type=ArtifactType.PRETRAINED_WEIGHT,
                    name="ResNet-50 weights",
                    location="https://example.com/checkpoints/resnet50.pth",
                )
            ],
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            )
        ],
    )


def _pipeline_outputs(analysis: PaperReproductionAnalysis):
    collection = CollectionService.default().collect(analysis)
    evidence = EvidenceService.default().collect(analysis, collection)
    verification = VerificationService.default().verify(analysis, collection, evidence)
    return collection, evidence, verification


class EmbeddedRankingProviderTest(unittest.TestCase):
    def test_ranks_pass_before_skipped(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        result = EmbeddedRankingProvider().rank(analysis, collection, evidence, verification)

        repository_lists = [
            rank_list
            for rank_list in result.rank_lists
            if rank_list.resource_need.need_category == NeedCategory.CODE_REPOSITORY
        ]
        self.assertEqual(len(repository_lists), 1)
        rank_list = repository_lists[0]
        self.assertEqual(len(rank_list.ordered_candidate_ids), 1)
        self.assertIn(rank_list.ordered_candidate_ids[0], rank_list.eligible_candidate_ids)

    def test_verification_status_ordering(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, _ = _pipeline_outputs(analysis)
        need = next(
            need
            for need in collection.resource_needs
            if need.need_category == NeedCategory.CODE_REPOSITORY
        )
        base = next(
            candidate
            for candidate in collection.candidates
            if need.need_id in candidate.addresses_needs
        )
        statuses = [
            VerificationStatus.SKIPPED,
            VerificationStatus.PASS,
            VerificationStatus.FAIL,
        ]
        candidates = [
            base.model_copy(
                update={
                    "candidate_id": f"candidate-{status.value}",
                    "addresses_needs": [need.need_id],
                }
            )
            for status in statuses
        ]
        ranked_collection = CollectionProviderResult(
            candidates=candidates,
            resource_needs=[need],
        )
        verification = VerificationProviderResult(
            verification_records=[
                verification_record(candidate.candidate_id, status)
                for candidate, status in zip(candidates, statuses, strict=True)
            ]
        )
        result = EmbeddedRankingProvider().rank(
            analysis, ranked_collection, evidence, verification
        )

        rank_list = result.rank_lists[0]
        self.assertEqual(
            rank_list.ordered_candidate_ids,
            [
                "candidate-pass",
                "candidate-skipped",
                "candidate-fail",
            ],
        )
        self.assertEqual(rank_list.eligible_candidate_ids, ["candidate-pass"])

    def test_stable_order_within_equal_status(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, _ = _pipeline_outputs(analysis)
        need = next(
            need
            for need in collection.resource_needs
            if need.need_category == NeedCategory.CODE_REPOSITORY
        )
        base = next(
            candidate
            for candidate in collection.candidates
            if need.need_id in candidate.addresses_needs
        )
        candidates = [
            base.model_copy(
                update={
                    "candidate_id": f"candidate-{index}",
                    "addresses_needs": [need.need_id],
                }
            )
            for index in range(3)
        ]
        ranked_collection = CollectionProviderResult(
            candidates=candidates,
            resource_needs=[need],
        )
        verification = VerificationProviderResult(
            verification_records=[
                verification_record(candidate.candidate_id, VerificationStatus.PASS)
                for candidate in candidates
            ]
        )
        result = EmbeddedRankingProvider().rank(
            analysis, ranked_collection, evidence, verification
        )

        self.assertEqual(
            result.rank_lists[0].ordered_candidate_ids,
            ["candidate-0", "candidate-1", "candidate-2"],
        )


class RankingMergeTest(unittest.TestCase):
    def test_merge_preserves_first_rank_list_id(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        first = EmbeddedRankingProvider().rank(analysis, collection, evidence, verification)
        duplicate = first.rank_lists[0].model_copy(
            update={"ranking_factors_summary": "duplicate provider summary"}
        )
        merged = merge_rank_lists(first.rank_lists, [duplicate])
        self.assertEqual(len(merged), len(first.rank_lists))
        self.assertEqual(merged[0].rank_list_id, first.rank_lists[0].rank_list_id)
        self.assertIn("duplicate provider summary", merged[0].ranking_factors_summary)

    def test_append_only_keeps_distinct_needs(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        full = EmbeddedRankingProvider().rank(analysis, collection, evidence, verification)
        partial_need = collection.resource_needs[0]
        partial = EmbeddedRankingProvider().rank(
            analysis,
            CollectionProviderResult(
                candidates=[
                    candidate
                    for candidate in collection.candidates
                    if partial_need.need_id in candidate.addresses_needs
                ],
                resource_needs=[partial_need],
            ),
            evidence,
            verification,
        )
        merged = merge_rank_lists(partial.rank_lists, full.rank_lists)
        self.assertEqual(len(merged), len(full.rank_lists))

    def test_stable_union_preserves_order(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        first = EmbeddedRankingProvider().rank(analysis, collection, evidence, verification)
        reordered = first.rank_lists[0].model_copy(
            update={"ordered_candidate_ids": list(reversed(first.rank_lists[0].ordered_candidate_ids))}
        )
        merged = merge_rank_lists(first.rank_lists, [reordered])
        self.assertEqual(
            merged[0].ordered_candidate_ids,
            first.rank_lists[0].ordered_candidate_ids,
        )


class RankingServiceTest(unittest.TestCase):
    def test_default_provider_order(self) -> None:
        calls: list[str] = []

        class RecordingProvider:
            def __init__(self, name: str) -> None:
                self._name = name

            def rank(self, analysis, collection_result, evidence_result, verification_result):
                calls.append(self._name)
                return NoOpRankingProvider().rank(
                    analysis, collection_result, evidence_result, verification_result
                )

        service = RankingService(
            providers=[
                RecordingProvider("embedded"),
                RecordingProvider("noop"),
            ]
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="T"),
            goal=AnalysisGoal(research_goal="g"),
        )
        service.rank(
            analysis,
            CollectionProviderResult(),
            EvidenceProviderResult(),
            VerificationProviderResult(),
        )
        self.assertEqual(calls, ["embedded", "noop"])

    def test_merges_embedded_rank_lists(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        result = RankingService.default().rank(analysis, collection, evidence, verification)
        self.assertGreater(len(result.rank_lists), 0)
        self.assertTrue(any(rank_list.ordered_candidate_ids for rank_list in result.rank_lists))

    def test_noop_only_service_returns_empty(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection, evidence, verification = _pipeline_outputs(analysis)
        result = RankingService(providers=[NoOpRankingProvider()]).rank(
            analysis, collection, evidence, verification
        )
        self.assertEqual(result.rank_lists, [])


class DiscoveryWorkflowRankingIntegrationTest(unittest.TestCase):
    def test_end_to_end_embedded_ranking(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_embedded_resources())

        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertGreater(len(discovery.ranking.rank_lists), 0)
        self.assertTrue(
            any(rank_list.ordered_candidate_ids for rank_list in discovery.ranking.rank_lists)
        )

    def test_empty_ranking_when_no_candidates(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[]),
            evidence_service=EvidenceService(providers=[]),
            verification_service=VerificationService(providers=[]),
            ranking_service=RankingService.default(),
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Empty"),
            goal=AnalysisGoal(research_goal="No resources"),
        )
        discovery = workflow.run(analysis)
        self.assertEqual(discovery.ranking.rank_lists, [])


def verification_record(candidate_id: str, status: VerificationStatus):
    from datetime import UTC, datetime

    from models.research_resource_discovery import VerificationRecord

    return VerificationRecord(
        verification_id=f"verification-{candidate_id}",
        candidate_id=candidate_id,
        status=status,
        verified_at=datetime.now(UTC),
    )


if __name__ == "__main__":
    unittest.main()
