import unittest
from datetime import UTC, datetime

from discovery.workflow import DiscoveryWorkflow
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    AnalysisResources,
    ExternalResource,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from models.research_resource_discovery import (
    CollectionSource,
    CollectionSourceType,
    DimensionResult,
    DiscoveryProvider,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    ProviderInvocationStatus,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceType,
    SCHEMA_VERSION,
    VerificationDimensionName,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.github.evidence import GitHubEvidenceProvider
from providers.github.verification import GitHubVerificationProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService


def _github_candidate(
    *,
    candidate_id: str = "github-abc",
    full_name: str = "octocat/Hello-World",
    url: str = "https://github.com/octocat/Hello-World",
) -> RepositoryCandidate:
    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.GITHUB,
            provider_native_id=full_name,
            normalized_url=url,
        ),
        provider=DiscoveryProvider.GITHUB,
        resource_type=ResourceType.OFFICIAL_REPOSITORY,
        url=url,
        collection_source=CollectionSource(
            source_type=CollectionSourceType.METADATA_LOOKUP,
            provider_name="github",
            source_query="resources.external_resources:official-release",
        ),
        extensions={"source_url": url},
    )


def _metadata_evidence(
    candidate_id: str,
    *,
    full_name: str = "octocat/Hello-World",
    repository_url: str = "https://github.com/octocat/Hello-World",
    description: str = "Repository description",
    license: str = "MIT",
    topics: str = "demo",
    homepage: str = "https://example.com",
    default_branch: str = "main",
    archived: bool = False,
    evidence_id: str = "github-evidence-metadata",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        evidence_type=EvidenceType.METADATA_EXTRACT,
        evidence_source=EvidenceSource(
            source_kind=EvidenceSourceKind.PROVIDER_API,
            provider_name="github",
            uri=repository_url,
            fetch_status=FetchStatus.SUCCESS,
        ),
        observed_fact=ObservedFact(
            fields={
                "repository_url": repository_url,
                "full_name": full_name,
                "owner": full_name.split("/", 1)[0],
                "description": description,
                "license": license,
                "topics": topics,
                "homepage": homepage,
                "default_branch": default_branch,
                "archived": archived,
                "stars": 10,
                "forks": 2,
                "open_issues": 1,
                "language": "Python",
                "latest_push": "2011-01-26T19:06:43+00:00",
                "latest_update": "2011-01-26T19:14:43+00:00",
            }
        ),
        polarity=EvidencePolarity.NEUTRAL,
        confidence=1.0,
        collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )


def _readme_evidence(
    candidate_id: str,
    *,
    evidence_id: str = "github-evidence-readme",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        evidence_type=EvidenceType.README_CLAIM,
        evidence_source=EvidenceSource(
            source_kind=EvidenceSourceKind.PROVIDER_API,
            provider_name="github",
            uri="https://github.com/octocat/Hello-World/blob/main/README.md",
            fetch_status=FetchStatus.SUCCESS,
        ),
        observed_fact=ObservedFact(
            fields={
                "readme_exists": True,
                "readme_url": "https://github.com/octocat/Hello-World/blob/main/README.md",
                "readme_text": "# Hello World",
                "content_hash": "abc123",
                "encoding": "base64",
                "size": 13,
            }
        ),
        polarity=EvidencePolarity.NEUTRAL,
        confidence=1.0,
        collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )


def _analysis() -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(title="Test Paper"),
        goal=AnalysisGoal(scope=ReproductionScope.TRAINING, research_goal="Reproduce."),
        resources=AnalysisResources(
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="official-release",
                    url="https://github.com/octocat/Hello-World",
                )
            ]
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            )
        ],
    )


def _dimension_by_check(record, check_name: str):
    for dimension in record.dimensions:
        if dimension.details.get("check") == check_name:
            return dimension
    raise AssertionError(f"Missing dimension check: {check_name}")


class GitHubVerificationProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = GitHubVerificationProvider()
        self.candidate = _github_candidate()
        self.collection = CollectionProviderResult(candidates=[self.candidate])

    def _verify(self, evidence_records):
        return self.provider.verify(
            _analysis(),
            self.collection,
            EvidenceProviderResult(evidence_records=evidence_records),
        )

    def test_repository_exists_passes_with_metadata_evidence(self) -> None:
        result = self._verify(
            [
                _metadata_evidence(self.candidate.candidate_id),
                _readme_evidence(self.candidate.candidate_id),
            ]
        )
        record = result.verification_records[0]
        self.assertEqual(record.status, VerificationStatus.PASS)
        check = _dimension_by_check(record, "repository_exists")
        self.assertEqual(check.result, DimensionResult.PASS)
        self.assertEqual(check.evidence_ids, ["github-evidence-metadata"])

    def test_repository_missing_fails(self) -> None:
        result = self._verify([])
        record = result.verification_records[0]
        self.assertEqual(record.status, VerificationStatus.FAIL)
        self.assertIn("repository metadata missing", record.blocking_failures)

    def test_readme_present_and_absent(self) -> None:
        with_readme = self._verify(
            [
                _metadata_evidence(self.candidate.candidate_id),
                _readme_evidence(self.candidate.candidate_id),
            ]
        )
        readme_check = _dimension_by_check(with_readme.verification_records[0], "readme_present")
        self.assertEqual(readme_check.result, DimensionResult.PASS)
        self.assertEqual(readme_check.evidence_ids, ["github-evidence-readme"])

        without_readme = self._verify([_metadata_evidence(self.candidate.candidate_id)])
        self.assertEqual(without_readme.verification_records[0].status, VerificationStatus.PARTIAL)
        readme_missing = _dimension_by_check(without_readme.verification_records[0], "readme_present")
        self.assertEqual(readme_missing.result, DimensionResult.PARTIAL)
        self.assertNotIn("README evidence absent", without_readme.verification_records[0].blocking_failures)

    def test_archived_repository_is_blocking_failure(self) -> None:
        result = self._verify(
            [
                _metadata_evidence(
                    self.candidate.candidate_id,
                    archived=True,
                )
            ]
        )
        record = result.verification_records[0]
        self.assertEqual(record.status, VerificationStatus.FAIL)
        archived = _dimension_by_check(record, "repository_archived")
        self.assertEqual(archived.result, DimensionResult.FAIL)
        self.assertIn("Repository is archived.", record.blocking_failures)

    def test_missing_optional_metadata_fields_are_partial(self) -> None:
        result = self._verify(
            [
                _metadata_evidence(
                    self.candidate.candidate_id,
                    description="",
                    license="",
                    topics="",
                    homepage="",
                )
            ]
        )
        record = result.verification_records[0]
        self.assertEqual(record.status, VerificationStatus.PARTIAL)
        self.assertEqual(_dimension_by_check(record, "repository_license_present").result, DimensionResult.PARTIAL)
        self.assertEqual(
            _dimension_by_check(record, "repository_description_present").result,
            DimensionResult.PARTIAL,
        )
        self.assertEqual(_dimension_by_check(record, "repository_topics_present").result, DimensionResult.PARTIAL)
        self.assertEqual(_dimension_by_check(record, "repository_homepage_present").result, DimensionResult.PARTIAL)

    def test_missing_default_branch_is_partial(self) -> None:
        result = self._verify(
            [_metadata_evidence(self.candidate.candidate_id, default_branch="")]
        )
        check = _dimension_by_check(result.verification_records[0], "default_branch_present")
        self.assertEqual(check.result, DimensionResult.PARTIAL)

    def test_identity_mismatch_fails(self) -> None:
        result = self._verify(
            [
                _metadata_evidence(
                    self.candidate.candidate_id,
                    full_name="other/repo",
                    repository_url="https://github.com/other/repo",
                )
            ]
        )
        record = result.verification_records[0]
        self.assertEqual(record.status, VerificationStatus.FAIL)
        identity = _dimension_by_check(record, "repository_identity_match")
        self.assertEqual(identity.result, DimensionResult.FAIL)
        self.assertTrue(record.blocking_failures)

    def test_evidence_linkage_on_all_dimensions(self) -> None:
        result = self._verify(
            [
                _metadata_evidence(self.candidate.candidate_id),
                _readme_evidence(self.candidate.candidate_id),
            ]
        )
        record = result.verification_records[0]
        for dimension in record.dimensions:
            self.assertTrue(dimension.evidence_ids)
        paper_match = _dimension_by_check(record, "paper_url_match")
        self.assertEqual(paper_match.dimension, VerificationDimensionName.PAPER_MATCH)

    def test_overall_confidence_values(self) -> None:
        pass_result = self._verify(
            [
                _metadata_evidence(self.candidate.candidate_id),
                _readme_evidence(self.candidate.candidate_id),
            ]
        )
        self.assertEqual(
            pass_result.verification_records[0].dimensions[0].details["overall_confidence"],
            "1.0",
        )

        partial_result = self._verify([_metadata_evidence(self.candidate.candidate_id)])
        self.assertEqual(
            partial_result.verification_records[0].dimensions[0].details["overall_confidence"],
            "0.6",
        )

    def test_skips_non_github_candidates(self) -> None:
        foreign = _github_candidate().model_copy(
            update={
                "candidate_id": "embedded-1",
                "provider": DiscoveryProvider.PAPER_LINK,
                "identity": ResourceIdentity(
                    provider=DiscoveryProvider.PAPER_LINK,
                    provider_native_id="",
                    normalized_url="https://example.com/repo",
                ),
            }
        )
        result = self.provider.verify(
            _analysis(),
            CollectionProviderResult(candidates=[foreign]),
            EvidenceProviderResult(),
        )
        self.assertEqual(result.verification_records, [])
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.SKIPPED)


class GitHubVerificationServiceIntegrationTest(unittest.TestCase):
    def test_default_provider_order_includes_github_verification(self) -> None:
        from services.discovery.verification_service import _default_providers

        provider_types = [type(provider).__name__ for provider in _default_providers()]
        self.assertEqual(
            provider_types,
            [
                "EmbeddedVerificationProvider",
                "GitHubVerificationProvider",
                "NoOpVerificationProvider",
            ],
        )

    def test_verification_service_merges_embedded_and_github_records(self) -> None:
        candidate = _github_candidate()
        collection = CollectionProviderResult(candidates=[candidate])
        evidence = EvidenceProviderResult(
            evidence_records=[
                _metadata_evidence(candidate.candidate_id),
                _readme_evidence(candidate.candidate_id),
            ]
        )
        service = VerificationService(
            providers=[
                EmbeddedVerificationProvider(),
                GitHubVerificationProvider(),
                NoOpVerificationProvider(),
            ]
        )
        result = service.verify(_analysis(), collection, evidence)
        self.assertEqual(len(result.verification_records), 1)
        provider_names = [outcome.provider_name for outcome in result.provider_outcomes]
        self.assertIn("embedded_verification", provider_names)
        self.assertIn("github_verification", provider_names)


class GitHubVerificationWorkflowIntegrationTest(unittest.TestCase):
    def test_offline_workflow_with_mock_github_stack(self) -> None:
        from providers.github.collection import GitHubCollectionProvider
        from tests.test_github_evidence_provider import (
            _github_client,
            _mock_transport,
            _readme_payload,
            _repository_payload,
        )

        transport = _mock_transport(
            repositories={("octocat", "Hello-World"): _repository_payload()},
            readmes={("octocat", "Hello-World"): _readme_payload()},
        )
        client = _github_client(transport)
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(
                providers=[
                    EmbeddedResourceProvider(),
                    GitHubCollectionProvider(client=client),
                    NoOpCollectionProvider(),
                ]
            ),
            evidence_service=EvidenceService(
                providers=[
                    EmbeddedEvidenceProvider(),
                    GitHubEvidenceProvider(client=client),
                    NoOpEvidenceProvider(),
                ]
            ),
            verification_service=VerificationService(
                providers=[
                    EmbeddedVerificationProvider(),
                    GitHubVerificationProvider(),
                    NoOpVerificationProvider(),
                ]
            ),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis())
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        github_records = [
            record
            for record in discovery.verification.records
            if record.verifier_version == "1.0.0"
            and any(dimension.details.get("provider") == "github_verification" for dimension in record.dimensions)
        ]
        self.assertGreaterEqual(len(github_records), 1)
        self.assertIn(github_records[0].status, {VerificationStatus.PASS, VerificationStatus.PARTIAL})


if __name__ == "__main__":
    unittest.main()
