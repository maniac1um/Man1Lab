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
    SCHEMA_VERSION,
    VerificationStatus,
)
from discovery.workflow import DiscoveryWorkflow
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.verification_merge import merge_verification
from services.discovery.verification_service import VerificationService
from services.discovery.ranking_service import RankingService


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


class EmbeddedVerificationProviderTest(unittest.TestCase):
    def test_passes_candidates_with_embedded_evidence(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        evidence = EvidenceService.default().collect(analysis, collection)
        result = EmbeddedVerificationProvider().verify(analysis, collection, evidence)

        self.assertEqual(len(result.verification_records), 3)
        passed = [
            record
            for record in result.verification_records
            if record.status == VerificationStatus.PASS
        ]
        self.assertEqual(len(passed), 3)
        dimension = passed[0].dimensions[0]
        self.assertEqual(dimension.details["verification_reason"], "resource explicitly referenced by paper")
        self.assertEqual(dimension.details["confidence"], "1.0")

    def test_skips_candidates_without_embedded_evidence(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        result = EmbeddedVerificationProvider().verify(
            analysis,
            collection,
            EvidenceProviderResult(),
        )
        self.assertEqual(len(result.verification_records), 3)
        self.assertTrue(
            all(record.status == VerificationStatus.SKIPPED for record in result.verification_records)
        )


class VerificationMergeTest(unittest.TestCase):
    def test_merge_preserves_first_verification_id(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        evidence = EvidenceService.default().collect(analysis, collection)
        first = EmbeddedVerificationProvider().verify(analysis, collection, evidence)
        duplicate = first.verification_records[0].model_copy(
            update={"verification_id": "duplicate-id"}
        )
        merged = merge_verification(first.verification_records, [duplicate])
        self.assertEqual(len(merged), len(first.verification_records))
        self.assertEqual(merged[0].verification_id, first.verification_records[0].verification_id)

    def test_append_only_keeps_distinct_candidates(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        evidence = EvidenceService.default().collect(analysis, collection)
        full = EmbeddedVerificationProvider().verify(analysis, collection, evidence)
        partial = EmbeddedVerificationProvider().verify(
            analysis,
            CollectionProviderResult(candidates=collection.candidates[:1]),
            EvidenceProviderResult(evidence_records=evidence.evidence_records[:1]),
        )
        merged = merge_verification(partial.verification_records, full.verification_records)
        self.assertEqual(len(merged), 3)


class VerificationServiceTest(unittest.TestCase):
    def test_default_provider_order(self) -> None:
        calls: list[str] = []

        class RecordingProvider:
            def __init__(self, name: str) -> None:
                self._name = name

            def verify(self, analysis, collection_result, evidence_result):
                calls.append(self._name)
                return NoOpVerificationProvider().verify(
                    analysis, collection_result, evidence_result
                )

        service = VerificationService(
            providers=[
                RecordingProvider("embedded"),
                RecordingProvider("noop"),
            ]
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="T"),
            goal=AnalysisGoal(research_goal="g"),
        )
        service.verify(analysis, CollectionProviderResult(), EvidenceProviderResult())
        self.assertEqual(calls, ["embedded", "noop"])

    def test_merges_embedded_verification_records(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        evidence = EvidenceService.default().collect(analysis, collection)
        result = VerificationService.default().verify(analysis, collection, evidence)
        self.assertEqual(len(result.verification_records), 3)
        self.assertEqual(len(result.provider_outcomes), 2)
        self.assertEqual(result.provider_outcomes[0].provider_name, "embedded_verification")
        self.assertEqual(result.provider_outcomes[1].provider_name, "github_verification")


class DiscoveryWorkflowVerificationIntegrationTest(unittest.TestCase):
    def test_end_to_end_embedded_verification(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_embedded_resources())

        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(len(discovery.verification.records), 3)
        self.assertEqual(discovery.verification.records[0].status, VerificationStatus.PASS)

    def test_empty_verification_when_no_candidates(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[]),
            evidence_service=EvidenceService(providers=[]),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Empty"),
            goal=AnalysisGoal(research_goal="No resources"),
        )
        discovery = workflow.run(analysis)
        self.assertEqual(discovery.verification.records, [])

    def test_noop_only_service_returns_empty(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        evidence = EvidenceService.default().collect(analysis, collection)
        result = VerificationService(providers=[NoOpVerificationProvider()]).verify(
            analysis, collection, evidence
        )
        self.assertEqual(result.verification_records, [])


if __name__ == "__main__":
    unittest.main()
