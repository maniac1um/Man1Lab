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
    CollectionSourceType,
    DiscoveryProvider,
    ResourceType,
    SCHEMA_VERSION,
)
from discovery.workflow import DiscoveryWorkflow
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.noop.collection import NoOpCollectionProvider
from services.discovery.candidate_merge import merge_candidates, normalize_url
from services.discovery.collection_service import CollectionService
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
                    description="Training dataset",
                )
            ],
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="official-release",
                    url="https://github.com/KaimingHe/deep-residual-networks",
                    notes="Paper-stated repository",
                ),
                ExternalResource(
                    resource_type="project_page",
                    name="project-home",
                    url="https://github.com/KaimingHe/deep-residual-networks",
                    notes="Duplicate URL for merge test",
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
            ),
            ReproductionGap(
                category=GapCategory.DATASET_LINK,
                description="Dataset portal link cited in analysis resources.",
            ),
        ],
    )


class EmbeddedResourceProviderTest(unittest.TestCase):
    def test_extracts_embedded_urls_only(self) -> None:
        result = EmbeddedResourceProvider().collect(_analysis_with_embedded_resources())

        self.assertEqual(len(result.resource_needs), 2)
        self.assertEqual(len(result.candidates), 4)
        urls = {candidate.url for candidate in result.candidates}
        self.assertIn("https://github.com/KaimingHe/deep-residual-networks", urls)
        self.assertIn("https://image-net.org/challenges/LSVRC/2012/", urls)
        self.assertIn("https://example.com/checkpoints/resnet50.pth", urls)

    def test_skips_entries_without_urls(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="No URLs"),
            goal=AnalysisGoal(research_goal="Test"),
            resources=AnalysisResources(
                datasets=[DatasetResource(name="ImageNet", link="")],
                external_resources=[
                    ExternalResource(resource_type="repository", name="missing", url="")
                ],
            ),
        )
        result = EmbeddedResourceProvider().collect(analysis)
        self.assertEqual(result.candidates, [])

    def test_github_identity_from_embedded_url(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Repo"),
            goal=AnalysisGoal(research_goal="Test"),
            resources=AnalysisResources(
                external_resources=[
                    ExternalResource(
                        resource_type="repository",
                        name="repo",
                        url="https://github.com/org/model",
                    )
                ]
            ),
        )
        candidate = EmbeddedResourceProvider().collect(analysis).candidates[0]
        self.assertEqual(candidate.provider, DiscoveryProvider.GITHUB)
        self.assertEqual(candidate.identity.provider_native_id, "org/model")
        self.assertEqual(candidate.collection_source.source_type, CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE)


class CandidateMergeTest(unittest.TestCase):
    def test_merge_duplicate_urls_preserves_first_candidate(self) -> None:
        first = EmbeddedResourceProvider().collect(_analysis_with_embedded_resources()).candidates[0]
        duplicate = first.model_copy(
            update={
                "candidate_id": "other-id",
                "notes": "duplicate source",
            }
        )
        merged = merge_candidates([first], [duplicate])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].candidate_id, first.candidate_id)
        self.assertIn("merged duplicate", merged[0].notes)

    def test_normalize_url_strips_tracking_params(self) -> None:
        normalized = normalize_url(
            "https://GitHub.com/Org/Repo/?utm_source=test&ref=abc"
        )
        self.assertEqual(normalized, "https://github.com/Org/Repo")


class CollectionServiceTest(unittest.TestCase):
    def test_default_provider_order(self) -> None:
        calls: list[str] = []

        class RecordingProvider:
            def __init__(self, name: str) -> None:
                self._name = name

            def collect(self, analysis):
                calls.append(self._name)
                return NoOpCollectionProvider().collect(analysis)

        service = CollectionService(
            providers=[
                RecordingProvider("embedded"),
                RecordingProvider("noop"),
            ]
        )
        service.collect(
            PaperReproductionAnalysis(
                metadata=PaperMetadata(title="T"),
                goal=AnalysisGoal(research_goal="g"),
            )
        )
        self.assertEqual(calls, ["embedded", "noop"])

    def test_merges_and_deduplicates_across_providers(self) -> None:
        service = CollectionService.default()
        result = service.collect(_analysis_with_embedded_resources())

        self.assertEqual(len(result.candidates), 3)
        self.assertEqual(len(result.provider_outcomes), 2)
        self.assertEqual(result.provider_outcomes[0].provider_name, "embedded_resource")
        self.assertEqual(result.provider_outcomes[1].provider_name, "github")

    def test_derives_needs_when_provider_returns_none(self) -> None:
        service = CollectionService(providers=[NoOpCollectionProvider()])
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="T"),
            goal=AnalysisGoal(research_goal="g"),
            reproduction_gaps=[
                ReproductionGap(category=GapCategory.REPOSITORY, description="missing repo")
            ],
        )
        result = service.collect(analysis)
        self.assertEqual(len(result.resource_needs), 1)
        self.assertEqual(result.resource_needs[0].need_category.value, "code_repository")


class DiscoveryWorkflowCollectionIntegrationTest(unittest.TestCase):
    def test_embedded_only_discovery_end_to_end(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_embedded_resources())

        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(len(discovery.candidate_resources.candidates), 3)
        self.assertGreaterEqual(len(discovery.provenance.providers_used), 1)
        self.assertEqual(
            discovery.provenance.providers_used[0].provider_name,
            "embedded_resource",
        )
        self.assertEqual(discovery.metadata.candidate_count, 3)

    def test_empty_analysis_still_runs(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService.default(),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Empty"),
            goal=AnalysisGoal(research_goal="No embedded resources"),
        )
        discovery = workflow.run(analysis)
        self.assertEqual(discovery.candidate_resources.candidates, [])


if __name__ == "__main__":
    unittest.main()
