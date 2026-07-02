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
    EvidenceSourceKind,
    EvidenceType,
    SCHEMA_VERSION,
)
from discovery.workflow import DiscoveryWorkflow
from ports.collection_provider import CollectionProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_merge import merge_evidence
from services.discovery.evidence_service import EvidenceService
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
                ),
                ExternalResource(
                    resource_type="project_page",
                    name="project-home",
                    url="https://github.com/KaimingHe/deep-residual-networks",
                ),
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


class EmbeddedEvidenceProviderTest(unittest.TestCase):
    def test_generates_embedded_reference_evidence(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        result = EmbeddedEvidenceProvider().collect(analysis, collection, collection.candidates)

        self.assertEqual(len(result.evidence_records), 3)
        record = result.evidence_records[0]
        self.assertEqual(record.evidence_type, EvidenceType.EMBEDDED_REFERENCE)
        self.assertEqual(record.confidence, 1.0)
        self.assertEqual(record.evidence_source.source_kind, EvidenceSourceKind.PAPER_TEXT)
        self.assertEqual(record.observed_fact.fields["source"], "paper")

    def test_skips_candidates_without_analysis_url(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = EmbeddedResourceProvider().collect(analysis)
        foreign_candidate = collection.candidates[0].model_copy(
            update={"candidate_id": "foreign", "url": "https://unknown.example/repo"}
        )
        result = EmbeddedEvidenceProvider().collect(
            analysis,
            collection,
            [foreign_candidate],
        )
        self.assertEqual(result.evidence_records, [])

    def test_deduplicated_candidates_share_one_evidence_per_source_query(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        result = EmbeddedEvidenceProvider().collect(analysis, collection, collection.candidates)
        self.assertEqual(len(result.evidence_records), 3)


class EvidenceMergeTest(unittest.TestCase):
    def test_merge_preserves_first_evidence_id(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        first = EmbeddedEvidenceProvider().collect(analysis, collection, collection.candidates)
        duplicate = first.evidence_records[0].model_copy(
            update={
                "evidence_id": "duplicate-id",
                "raw_reference": "duplicate",
            }
        )
        merged = merge_evidence(first.evidence_records, [duplicate])
        self.assertEqual(len(merged), len(first.evidence_records))
        self.assertEqual(merged[0].evidence_id, first.evidence_records[0].evidence_id)
        references = [record.raw_reference or "" for record in merged]
        self.assertTrue(any("merged duplicate" in reference for reference in references))

    def test_append_only_never_discards_unique_records(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        batch_a = EmbeddedEvidenceProvider().collect(
            analysis, collection, collection.candidates[:1]
        )
        batch_b = EmbeddedEvidenceProvider().collect(
            analysis, collection, collection.candidates[1:2]
        )
        merged = merge_evidence(batch_a.evidence_records, batch_b.evidence_records)
        self.assertEqual(len(merged), 2)


class EvidenceServiceTest(unittest.TestCase):
    def test_default_provider_order(self) -> None:
        calls: list[str] = []

        class RecordingProvider:
            def __init__(self, name: str) -> None:
                self._name = name

            def collect(self, analysis, collection_result, candidates):
                calls.append(self._name)
                return NoOpEvidenceProvider().collect(analysis, collection_result, candidates)

        service = EvidenceService(
            providers=[
                RecordingProvider("embedded"),
                RecordingProvider("noop"),
            ]
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="T"),
            goal=AnalysisGoal(research_goal="g"),
        )
        service.collect(analysis, CollectionProviderResult())
        self.assertEqual(calls, ["embedded", "noop"])

    def test_merges_provider_results(self) -> None:
        analysis = _analysis_with_embedded_resources()
        collection = CollectionService.default().collect(analysis)
        result = EvidenceService.default().collect(analysis, collection)
        self.assertEqual(len(result.evidence_records), 3)
        self.assertEqual(len(result.provider_outcomes), 2)
        self.assertEqual(result.provider_outcomes[0].provider_name, "embedded_evidence")
        self.assertEqual(result.provider_outcomes[1].provider_name, "github_evidence")


class DiscoveryWorkflowEvidenceIntegrationTest(unittest.TestCase):
    def test_embedded_evidence_in_end_to_end_discovery(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_embedded_resources())

        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(len(discovery.candidate_resources.candidates), 3)
        self.assertEqual(len(discovery.evidence.records), 3)
        self.assertEqual(
            discovery.evidence.records[0].evidence_type,
            EvidenceType.EMBEDDED_REFERENCE,
        )

    def test_empty_evidence_when_no_candidates(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[]),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Empty"),
            goal=AnalysisGoal(research_goal="No resources"),
        )
        discovery = workflow.run(analysis)
        self.assertEqual(discovery.evidence.records, [])


if __name__ == "__main__":
    unittest.main()
