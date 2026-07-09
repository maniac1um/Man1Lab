"""Tests for unified research asset model."""

from __future__ import annotations

import unittest

from discovery.assets import build_research_assets, map_resource_type_to_asset_type
from discovery.workflow import DiscoveryWorkflow
from models.research_resource_discovery import ResourceType, ResearchAssetType
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService
from tests.benchmarks.golden.fixtures import resnet_official_analysis


class ResearchAssetModelTest(unittest.TestCase):
    def test_repository_maps_to_repository_asset_type(self) -> None:
        self.assertEqual(
            map_resource_type_to_asset_type(ResourceType.OFFICIAL_REPOSITORY),
            ResearchAssetType.REPOSITORY,
        )
        self.assertEqual(
            map_resource_type_to_asset_type(ResourceType.CHECKPOINT),
            ResearchAssetType.CHECKPOINT_WEIGHTS,
        )

    def test_discovery_builds_research_assets(self) -> None:
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(providers=[EmbeddedResourceProvider()]),
            evidence_service=EvidenceService(providers=[EmbeddedEvidenceProvider()]),
            verification_service=VerificationService(providers=[EmbeddedVerificationProvider()]),
            ranking_service=RankingService(providers=[EmbeddedRankingProvider()]),
        )
        discovery = workflow.run(resnet_official_analysis())
        self.assertGreater(len(discovery.research_assets.assets), 0)
        repo_assets = [
            asset for asset in discovery.research_assets.assets if asset.asset_type == ResearchAssetType.REPOSITORY
        ]
        self.assertTrue(repo_assets)
        self.assertTrue(any(asset.selected_primary for asset in repo_assets))


class ResearchAssetBackwardCompatTest(unittest.TestCase):
    def test_legacy_discovery_without_research_assets_field(self) -> None:
        from datetime import UTC, datetime

        from models.research_resource_discovery import (
            AnalysisReference,
            DiscoveryMetadata,
            DiscoveryStatus,
            ResearchResourceDiscovery,
        )
        from validation.research_resource_discovery import build_research_resource_discovery

        payload = ResearchResourceDiscovery(
            metadata=DiscoveryMetadata(
                discovery_id="legacy",
                created_at=datetime.now(UTC),
                status=DiscoveryStatus.PARTIAL,
            ),
            analysis_reference=AnalysisReference(
                analysis_schema_version="1.0",
                paper_title="Legacy",
                analysis_content_hash="hash",
            ),
        ).model_dump(mode="json")
        del payload["research_assets"]
        artifact = build_research_resource_discovery(payload)
        self.assertEqual(artifact.research_assets.assets, [])


if __name__ == "__main__":
    unittest.main()
