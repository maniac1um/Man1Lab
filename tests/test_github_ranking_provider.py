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
    NeedCategory,
    ObservedFact,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceNeed,
    ResourceType,
    SCHEMA_VERSION,
    VerificationDimension,
    VerificationDimensionName,
    VerificationRecord,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
from providers.github.collection import GitHubCollectionProvider
from providers.github.evidence import GitHubEvidenceProvider
from providers.github.ranking import GitHubRankingProvider
from providers.github.verification import GitHubVerificationProvider
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from providers.noop.noop_ranking_provider import NoOpRankingProvider
from providers.noop.noop_verification_provider import NoOpVerificationProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService


def _need() -> ResourceNeed:
    return ResourceNeed(
        need_id="need-repository-0",
        need_category=NeedCategory.CODE_REPOSITORY,
        derived_from_analysis_gap=True,
        analysis_gap_index=0,
        required_for_scope=["training"],
        description="Repository URL cited in analysis resources.",
    )


def _github_candidate(
    *,
    candidate_id: str,
    full_name: str = "octocat/Hello-World",
    url: str = "https://github.com/octocat/Hello-World",
    need_id: str = "need-repository-0",
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
        addresses_needs=[need_id],
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
    stars: int = 100,
    forks: int = 20,
    archived: bool = False,
    description: str = "Repository description",
    license: str = "MIT",
    topics: str = "demo",
    homepage: str = "https://example.com",
    default_branch: str = "main",
    latest_push: str = "2020-01-01T00:00:00+00:00",
    full_name: str = "octocat/Hello-World",
    repository_url: str = "https://github.com/octocat/Hello-World",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"github-evidence-metadata-{candidate_id}",
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
                "stars": stars,
                "forks": forks,
                "open_issues": 1,
                "language": "Python",
                "latest_push": latest_push,
                "latest_update": latest_push,
            }
        ),
        polarity=EvidencePolarity.NEUTRAL,
        confidence=1.0,
        collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )


def _verification_record(
    candidate_id: str,
    *,
    status: VerificationStatus,
    checks: dict[str, DimensionResult],
) -> VerificationRecord:
    dimensions = [
        VerificationDimension(
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=result,
            summary=f"{check_name} {result.value}",
            evidence_ids=[f"github-evidence-metadata-{candidate_id}"],
            details={
                "check": check_name,
                "provider": "github_verification",
                "confidence": "1.0",
            },
        )
        for check_name, result in checks.items()
    ]
    return VerificationRecord(
        verification_id=f"github-verification-{candidate_id}",
        candidate_id=candidate_id,
        status=status,
        dimensions=dimensions,
        blocking_failures=[],
        verified_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        verifier_version="1.0.0",
    )


def _full_pass_checks() -> dict[str, DimensionResult]:
    return {
        "repository_exists": DimensionResult.PASS,
        "repository_accessible": DimensionResult.PASS,
        "paper_url_match": DimensionResult.PASS,
        "repository_identity_match": DimensionResult.PASS,
        "readme_present": DimensionResult.PASS,
        "repository_archived": DimensionResult.PASS,
        "repository_license_present": DimensionResult.PASS,
        "repository_description_present": DimensionResult.PASS,
        "repository_topics_present": DimensionResult.PASS,
        "repository_homepage_present": DimensionResult.PASS,
        "default_branch_present": DimensionResult.PASS,
        "repository_metadata_completeness": DimensionResult.PASS,
    }


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


class GitHubRankingProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = GitHubRankingProvider()
        self.need = _need()

    def _rank(self, candidates, evidence_records, verification_records):
        collection = CollectionProviderResult(
            candidates=candidates,
            resource_needs=[self.need],
        )
        evidence = EvidenceProviderResult(evidence_records=evidence_records)
        verification = VerificationProviderResult(verification_records=verification_records)
        return self.provider.rank(_analysis(), collection, evidence, verification)

    def test_pass_ranks_before_partial_and_fail(self) -> None:
        pass_candidate = _github_candidate(candidate_id="github-pass")
        partial_candidate = _github_candidate(candidate_id="github-partial")
        fail_candidate = _github_candidate(candidate_id="github-fail")

        evidence = [
            _metadata_evidence(pass_candidate.candidate_id),
            _metadata_evidence(partial_candidate.candidate_id, description="", topics="", license=""),
            _metadata_evidence(fail_candidate.candidate_id, archived=True),
        ]
        verification = [
            _verification_record(pass_candidate.candidate_id, status=VerificationStatus.PASS, checks=_full_pass_checks()),
            _verification_record(
                partial_candidate.candidate_id,
                status=VerificationStatus.PARTIAL,
                checks={**_full_pass_checks(), "repository_description_present": DimensionResult.PARTIAL},
            ),
            _verification_record(
                fail_candidate.candidate_id,
                status=VerificationStatus.FAIL,
                checks={**_full_pass_checks(), "repository_archived": DimensionResult.FAIL},
            ),
        ]
        result = self._rank([pass_candidate, partial_candidate, fail_candidate], evidence, verification)
        rank_list = result.rank_lists[0]
        self.assertEqual(
            rank_list.ordered_candidate_ids[:2],
            [pass_candidate.candidate_id, partial_candidate.candidate_id],
        )
        self.assertEqual(rank_list.ordered_candidate_ids[-1], fail_candidate.candidate_id)
        self.assertEqual(set(rank_list.eligible_candidate_ids), {pass_candidate.candidate_id, partial_candidate.candidate_id})

    def test_identity_tie_break(self) -> None:
        low = _github_candidate(candidate_id="github-low", full_name="octocat/low")
        high = _github_candidate(candidate_id="github-high", full_name="octocat/high")
        checks_low = {**_full_pass_checks(), "repository_identity_match": DimensionResult.FAIL}
        checks_high = _full_pass_checks()
        result = self._rank(
            [low, high],
            [_metadata_evidence(low.candidate_id, full_name="octocat/low"), _metadata_evidence(high.candidate_id)],
            [
                _verification_record(low.candidate_id, status=VerificationStatus.PASS, checks=checks_low),
                _verification_record(high.candidate_id, status=VerificationStatus.PASS, checks=checks_high),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], high.candidate_id)

    def test_paper_url_tie_break(self) -> None:
        no_match = _github_candidate(candidate_id="github-no-paper")
        matched = _github_candidate(candidate_id="github-paper")
        checks_no_match = {**_full_pass_checks(), "paper_url_match": DimensionResult.FAIL}
        checks_matched = _full_pass_checks()
        result = self._rank(
            [no_match, matched],
            [_metadata_evidence(no_match.candidate_id), _metadata_evidence(matched.candidate_id)],
            [
                _verification_record(no_match.candidate_id, status=VerificationStatus.PASS, checks=checks_no_match),
                _verification_record(matched.candidate_id, status=VerificationStatus.PASS, checks=checks_matched),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], matched.candidate_id)

    def test_archived_penalty(self) -> None:
        archived = _github_candidate(candidate_id="github-archived")
        active = _github_candidate(candidate_id="github-active")
        checks_archived = {**_full_pass_checks(), "repository_archived": DimensionResult.FAIL}
        checks_active = _full_pass_checks()
        result = self._rank(
            [archived, active],
            [
                _metadata_evidence(archived.candidate_id, archived=True),
                _metadata_evidence(active.candidate_id, archived=False),
            ],
            [
                _verification_record(archived.candidate_id, status=VerificationStatus.FAIL, checks=checks_archived),
                _verification_record(active.candidate_id, status=VerificationStatus.PASS, checks=checks_active),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], active.candidate_id)
        self.assertNotIn("not_archived", result.rank_lists[0].scores[archived.candidate_id].factor_scores)

    def test_metadata_completeness_influence(self) -> None:
        partial = _github_candidate(candidate_id="github-partial-meta")
        complete = _github_candidate(candidate_id="github-complete-meta")
        checks_partial = {
            **_full_pass_checks(),
            "repository_metadata_completeness": DimensionResult.PARTIAL,
        }
        checks_complete = _full_pass_checks()
        result = self._rank(
            [partial, complete],
            [_metadata_evidence(partial.candidate_id), _metadata_evidence(complete.candidate_id)],
            [
                _verification_record(partial.candidate_id, status=VerificationStatus.PASS, checks=checks_partial),
                _verification_record(complete.candidate_id, status=VerificationStatus.PASS, checks=checks_complete),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], complete.candidate_id)

    def test_readme_influence(self) -> None:
        no_readme = _github_candidate(candidate_id="github-no-readme")
        with_readme = _github_candidate(candidate_id="github-readme")
        checks_no_readme = {**_full_pass_checks(), "readme_present": DimensionResult.FAIL}
        checks_with_readme = _full_pass_checks()
        result = self._rank(
            [no_readme, with_readme],
            [_metadata_evidence(no_readme.candidate_id), _metadata_evidence(with_readme.candidate_id)],
            [
                _verification_record(no_readme.candidate_id, status=VerificationStatus.PASS, checks=checks_no_readme),
                _verification_record(with_readme.candidate_id, status=VerificationStatus.PASS, checks=checks_with_readme),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], with_readme.candidate_id)

    def test_forks_influence(self) -> None:
        fewer = _github_candidate(candidate_id="github-few-forks")
        more = _github_candidate(candidate_id="github-many-forks")
        checks = _full_pass_checks()
        result = self._rank(
            [fewer, more],
            [
                _metadata_evidence(fewer.candidate_id, forks=5),
                _metadata_evidence(more.candidate_id, forks=200),
            ],
            [
                _verification_record(fewer.candidate_id, status=VerificationStatus.PASS, checks=checks),
                _verification_record(more.candidate_id, status=VerificationStatus.PASS, checks=checks),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], more.candidate_id)

    def test_stars_influence_ordering(self) -> None:
        fewer = _github_candidate(candidate_id="github-few-stars")
        more = _github_candidate(candidate_id="github-many-stars")
        checks = _full_pass_checks()
        result = self._rank(
            [fewer, more],
            [
                _metadata_evidence(fewer.candidate_id, stars=10),
                _metadata_evidence(more.candidate_id, stars=500),
            ],
            [
                _verification_record(fewer.candidate_id, status=VerificationStatus.PASS, checks=checks),
                _verification_record(more.candidate_id, status=VerificationStatus.PASS, checks=checks),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], more.candidate_id)
        self.assertGreater(
            result.rank_lists[0].scores[more.candidate_id].total_score,
            result.rank_lists[0].scores[fewer.candidate_id].total_score,
        )

    def test_latest_push_influence(self) -> None:
        older = _github_candidate(candidate_id="github-old")
        newer = _github_candidate(candidate_id="github-new")
        checks = _full_pass_checks()
        result = self._rank(
            [older, newer],
            [
                _metadata_evidence(older.candidate_id, latest_push="2015-01-01T00:00:00+00:00"),
                _metadata_evidence(newer.candidate_id, latest_push="2024-01-01T00:00:00+00:00"),
            ],
            [
                _verification_record(older.candidate_id, status=VerificationStatus.PASS, checks=checks),
                _verification_record(newer.candidate_id, status=VerificationStatus.PASS, checks=checks),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids[0], newer.candidate_id)

    def test_stable_ordering_preserves_collection_order_on_tie(self) -> None:
        first = _github_candidate(candidate_id="github-a")
        second = _github_candidate(candidate_id="github-b")
        checks = _full_pass_checks()
        result = self._rank(
            [first, second],
            [_metadata_evidence(first.candidate_id, stars=50), _metadata_evidence(second.candidate_id, stars=50)],
            [
                _verification_record(first.candidate_id, status=VerificationStatus.PASS, checks=checks),
                _verification_record(second.candidate_id, status=VerificationStatus.PASS, checks=checks),
            ],
        )
        self.assertEqual(result.rank_lists[0].ordered_candidate_ids, [first.candidate_id, second.candidate_id])

    def test_score_breakdown_populated(self) -> None:
        candidate = _github_candidate(candidate_id="github-score")
        result = self._rank(
            [candidate],
            [_metadata_evidence(candidate.candidate_id)],
            [_verification_record(candidate.candidate_id, status=VerificationStatus.PASS, checks=_full_pass_checks())],
        )
        score = result.rank_lists[0].scores[candidate.candidate_id]
        self.assertGreater(score.total_score, 0.0)
        self.assertIn("verification_status", score.factor_scores)
        self.assertIn("identity_match", score.factor_scores)
        self.assertGreater(len(score.ranking_factors), 0)


class GitHubRankingServiceIntegrationTest(unittest.TestCase):
    def test_default_provider_order_includes_github_ranking(self) -> None:
        from services.discovery.ranking_service import _default_providers

        provider_types = [type(provider).__name__ for provider in _default_providers()]
        self.assertEqual(
            provider_types,
            [
                "EmbeddedRankingProvider",
                "GitHubRankingProvider",
                "NoOpRankingProvider",
            ],
        )

    def test_ranking_service_merges_embedded_and_github_rank_lists(self) -> None:
        need = _need()
        candidate = _github_candidate(candidate_id="github-service")
        collection = CollectionProviderResult(candidates=[candidate], resource_needs=[need])
        evidence = EvidenceProviderResult(evidence_records=[_metadata_evidence(candidate.candidate_id)])
        verification = VerificationProviderResult(
            verification_records=[
                _verification_record(candidate.candidate_id, status=VerificationStatus.PASS, checks=_full_pass_checks())
            ]
        )
        service = RankingService(
            providers=[
                EmbeddedRankingProvider(),
                GitHubRankingProvider(),
                NoOpRankingProvider(),
            ]
        )
        result = service.rank(_analysis(), collection, evidence, verification)
        self.assertEqual(len(result.rank_lists), 1)
        self.assertIn(candidate.candidate_id, result.rank_lists[0].ordered_candidate_ids)


class GitHubRankingWorkflowIntegrationTest(unittest.TestCase):
    def test_offline_workflow_with_mock_github_stack(self) -> None:
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
            ranking_service=RankingService(
                providers=[
                    EmbeddedRankingProvider(),
                    GitHubRankingProvider(),
                    NoOpRankingProvider(),
                ]
            ),
        )
        discovery = workflow.run(_analysis())
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        self.assertGreaterEqual(len(discovery.ranking.rank_lists), 1)


if __name__ == "__main__":
    unittest.main()
