"""Tests for explainable confidence composition."""

from __future__ import annotations

import unittest

from discovery.confidence import compose_selection_confidence
from models.research_resource_discovery import (
    CollectionSource,
    CollectionSourceType,
    DiscoveryProvider,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceType,
    EvidenceSourceKind,
    Officiality,
    RankScore,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceType,
    VerificationRecord,
    VerificationStatus,
)


class ExplainableConfidenceTest(unittest.TestCase):
    def test_pass_verification_meets_legacy_floor(self) -> None:
        candidate = RepositoryCandidate(
            candidate_id="c1",
            identity=ResourceIdentity(provider=DiscoveryProvider.GITHUB, normalized_url="https://example.com"),
            provider=DiscoveryProvider.GITHUB,
            resource_type=ResourceType.OFFICIAL_REPOSITORY,
            officiality=Officiality.OFFICIAL,
            collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
        )
        verification = VerificationRecord(
            verification_id="v1",
            candidate_id="c1",
            status=VerificationStatus.PASS,
        )
        evidence = [
            EvidenceRecord(
                evidence_id="e1",
                candidate_id="c1",
                evidence_type=EvidenceType.PAPER_CITATION_MATCH,
                evidence_source=EvidenceSource(source_kind=EvidenceSourceKind.PAPER_TEXT),
                polarity=EvidencePolarity.SUPPORTS,
            )
        ]
        composition = compose_selection_confidence(
            candidate=candidate,
            verification_record=verification,
            evidence_records=evidence,
            rank_score=RankScore(candidate_id="c1", total_score=4.0),
            need_category_value="code_repository",
        )
        self.assertGreaterEqual(composition.overall, 0.85)
        self.assertTrue(composition.contributions)
        signals = {item.signal for item in composition.contributions}
        self.assertIn("verification", signals)
        self.assertIn("official_organization", signals)

    def test_contributions_sum_is_documented(self) -> None:
        candidate = RepositoryCandidate(
            candidate_id="c1",
            identity=ResourceIdentity(provider=DiscoveryProvider.GITHUB),
            provider=DiscoveryProvider.GITHUB,
            resource_type=ResourceType.COMMUNITY_REPOSITORY,
            officiality=Officiality.COMMUNITY,
            collection_source=CollectionSource(source_type=CollectionSourceType.ANALYSIS_EXTERNAL_RESOURCE),
        )
        composition = compose_selection_confidence(
            candidate=candidate,
            verification_record=VerificationRecord(
                verification_id="v1",
                candidate_id="c1",
                status=VerificationStatus.PARTIAL,
            ),
            evidence_records=[],
            rank_score=None,
            need_category_value="code_repository",
        )
        self.assertGreaterEqual(composition.overall, 0.65)
        self.assertEqual(
            composition.composition_rule,
            "max(legacy_verification_floor, weighted_sum_capped)",
        )


if __name__ == "__main__":
    unittest.main()
