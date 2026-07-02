import unittest

from models.paper_reproduction_analysis import (
    AnalysisGoal,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from models.research_resource_discovery import (
    SCHEMA_VERSION,
    AnalysisReference,
    DiscoveryMetadata,
    DiscoveryStatus,
    RepositoryCandidate,
    ResearchResourceDiscovery,
)
from models.research_resource_discovery import (
    DiscoveryGap,
    DiscoveryGaps,
    RankingResult,
    SelectionResult,
)
from discovery.workflow import DiscoveryWorkflow, ResearchResourceDiscoveryBuilder
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.verification_service import VerificationService
from services.discovery.ranking_service import RankingService
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from validation.exceptions import DiscoveryValidationError
from validation.research_resource_discovery import (
    build_research_resource_discovery,
    normalize_discovery_dict,
    validate_discovery_dict,
)


def _sample_analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Deep Residual Learning for Image Recognition",
            arxiv_id="1512.03385",
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.TRAINING,
            research_goal="Reproduce ResNet training on ImageNet.",
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="No official repository URL provided in the paper.",
            )
        ],
    )


class ResearchResourceDiscoveryModelTest(unittest.TestCase):
    def test_schema_version_constant(self) -> None:
        discovery = ResearchResourceDiscovery(
            metadata=DiscoveryMetadata(
                discovery_id="disc-1",
                created_at="2026-07-02T00:00:00+00:00",
                status=DiscoveryStatus.PARTIAL,
            ),
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Test Paper",
                analysis_content_hash="abc123",
            ),
        )
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(discovery.candidate_resources.candidates, [])

    def test_frozen_model(self) -> None:
        discovery = ResearchResourceDiscovery(
            metadata=DiscoveryMetadata(
                discovery_id="disc-1",
                created_at="2026-07-02T00:00:00+00:00",
                status=DiscoveryStatus.PARTIAL,
            ),
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Test Paper",
                analysis_content_hash="abc123",
            ),
        )
        with self.assertRaises(Exception):
            discovery.metadata = discovery.metadata  # type: ignore[misc]


class DiscoveryValidationTest(unittest.TestCase):
    def test_build_minimal_discovery(self) -> None:
        data = normalize_discovery_dict(
            {
                "metadata": {
                    "discovery_id": "disc-1",
                    "created_at": "2026-07-02T00:00:00+00:00",
                    "status": "partial",
                    "candidate_count": 0,
                    "selection_count": 0,
                    "unresolved_gap_count": 1,
                },
                "analysis_reference": {
                    "analysis_schema_version": "1.0",
                    "paper_title": "Test Paper",
                    "analysis_content_hash": "hash",
                },
                "discovery_gaps": {
                    "gaps": [
                        {
                            "gap_id": "gap-1",
                            "gap_type": "no_official_repository",
                            "severity": "blocking",
                            "description": "No repository found.",
                        }
                    ]
                },
            }
        )
        discovery = build_research_resource_discovery(data)
        self.assertEqual(discovery.metadata.status, DiscoveryStatus.PARTIAL)
        self.assertEqual(len(discovery.discovery_gaps.gaps), 1)

    def test_reference_integrity_rejects_unknown_candidate(self) -> None:
        payload = normalize_discovery_dict(
            {
                "metadata": {
                    "discovery_id": "disc-1",
                    "created_at": "2026-07-02T00:00:00+00:00",
                    "status": "partial",
                },
                "analysis_reference": {
                    "analysis_schema_version": "1.0",
                    "paper_title": "Test Paper",
                    "analysis_content_hash": "hash",
                },
                "evidence": {
                    "records": [
                        {
                            "evidence_id": "ev-1",
                            "candidate_id": "missing",
                            "evidence_type": "http_status",
                            "evidence_source": {
                                "source_kind": "http_fetch",
                            },
                        }
                    ]
                },
            }
        )
        with self.assertRaises(DiscoveryValidationError):
            validate_discovery_dict(payload)

    def test_metadata_count_mismatch_rejected(self) -> None:
        payload = normalize_discovery_dict(
            {
                "metadata": {
                    "discovery_id": "disc-1",
                    "created_at": "2026-07-02T00:00:00+00:00",
                    "status": "partial",
                    "candidate_count": 2,
                },
                "analysis_reference": {
                    "analysis_schema_version": "1.0",
                    "paper_title": "Test Paper",
                    "analysis_content_hash": "hash",
                },
            }
        )
        with self.assertRaises(DiscoveryValidationError):
            validate_discovery_dict(payload)


class ResearchResourceDiscoveryBuilderTest(unittest.TestCase):
    def test_builder_produces_valid_empty_artifact(self) -> None:
        analysis = _sample_analysis()
        discovery = ResearchResourceDiscoveryBuilder.build(
            analysis=analysis,
            collection=CollectionProviderResult(),
            evidence=EvidenceProviderResult(),
            verification=VerificationProviderResult(),
            ranking=RankingResult(),
            selection=SelectionResult(),
            discovery_gaps=DiscoveryGaps(
                gaps=[
                    DiscoveryGap(
                        gap_id="gap-0",
                        gap_type="no_official_repository",
                        severity="blocking",
                        description="Unresolved repository gap.",
                        related_analysis_gap_index=0,
                    )
                ],
                analysis_gaps_remaining=["repository"],
            ),
        )
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(discovery.analysis_reference.paper_title, analysis.metadata.title)
        self.assertNotEqual(discovery.analysis_reference.analysis_content_hash, "")
        self.assertEqual(discovery.metadata.candidate_count, 0)


class DiscoveryWorkflowSkeletonTest(unittest.TestCase):
    def test_empty_discovery_end_to_end(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[]),
            evidence_service=EvidenceService(providers=[]),
            verification_service=VerificationService(providers=[]),
            ranking_service=RankingService(providers=[]),
        )
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(
                title="Deep Residual Learning for Image Recognition",
                arxiv_id="1512.03385",
            ),
            goal=AnalysisGoal(
                scope=ReproductionScope.TRAINING,
                research_goal="Reproduce ResNet training on ImageNet.",
            ),
        )
        discovery = workflow.run(analysis)

        self.assertIsInstance(discovery, ResearchResourceDiscovery)
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertEqual(discovery.candidate_resources.candidates, [])
        self.assertEqual(discovery.evidence.records, [])
        self.assertEqual(discovery.verification.records, [])
        self.assertEqual(discovery.metadata.status, DiscoveryStatus.PARTIAL)
        self.assertGreaterEqual(len(discovery.discovery_gaps.gaps), 1)
        self.assertEqual(discovery.analysis_reference.paper_title, "Deep Residual Learning for Image Recognition")

    def test_provenance_stage_timestamps_recorded(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[]),
            evidence_service=EvidenceService(providers=[]),
            verification_service=VerificationService(providers=[]),
            ranking_service=RankingService(providers=[]),
        )
        discovery = workflow.run(
            PaperReproductionAnalysis(
                metadata=PaperMetadata(title="T"),
                goal=AnalysisGoal(research_goal="g"),
            )
        )
        self.assertIn("candidate_collection", discovery.provenance.stage_timestamps)
        self.assertIn("assembly", discovery.provenance.stage_timestamps)


class NoOpProviderTest(unittest.TestCase):
    def test_noop_providers_return_empty_results(self) -> None:
        analysis = _sample_analysis()
        collection = NoOpCollectionProvider().collect(analysis)
        evidence = NoOpEvidenceProvider().collect(analysis, collection, collection.candidates)
        verification = NoOpVerificationProvider().verify(
            analysis, collection, evidence
        )
        self.assertEqual(collection.candidates, [])
        self.assertEqual(evidence.evidence_records, [])
        self.assertEqual(verification.verification_records, [])


if __name__ == "__main__":
    unittest.main()
