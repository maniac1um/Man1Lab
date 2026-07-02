import json
import unittest
from datetime import UTC, datetime
from unittest import mock

import httpx

from discovery.workflow import DiscoveryWorkflow
from models.paper_reproduction_analysis import (
    AnalysisGoal,
    AnalysisResources,
    ArtifactReference,
    ArtifactType,
    ExternalResource,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionGap,
    ReproductionScope,
)
from models.research_resource_discovery import (
    DiscoveryProvider,
    ProviderInvocationStatus,
    ResourceType,
    SCHEMA_VERSION,
)
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.github.auth import GitHubAuth
from providers.github.client import GitHubClient
from providers.github.collection import (
    GitHubCollectionProvider,
    extract_github_repository_urls,
    is_github_repository_url,
    parse_github_repository_url,
)
from providers.github.exceptions import GitHubAuthenticationError, GitHubNotFoundError
from providers.github.mapper import GitHubMapper
from providers.github.models import GitHubLicenseDTO, GitHubOwnerDTO, GitHubRepositoryDTO
from providers.noop.collection import NoOpCollectionProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService


def _repository_payload(
    *,
    full_name: str = "octocat/Hello-World",
    html_url: str = "https://github.com/octocat/Hello-World",
    description: str = "My first repository on GitHub!",
) -> dict:
    owner, repo = full_name.split("/", 1)
    return {
        "id": 1296269,
        "node_id": "R_kgDOA",
        "name": repo,
        "full_name": full_name,
        "private": False,
        "html_url": html_url,
        "description": description,
        "fork": False,
        "url": f"https://api.github.com/repos/{full_name}",
        "archived": False,
        "disabled": False,
        "stargazers_count": 80,
        "watchers_count": 80,
        "forks_count": 9,
        "open_issues_count": 0,
        "topics": ["demo"],
        "default_branch": "main",
        "owner": {
            "login": owner,
            "id": 1,
            "node_id": "O_kgDOA",
            "avatar_url": f"https://github.com/{owner}.png",
            "html_url": f"https://github.com/{owner}",
            "type": "User",
        },
        "license": {
            "key": "mit",
            "name": "MIT License",
            "spdx_id": "MIT",
            "url": "https://api.github.com/licenses/mit",
            "node_id": "MDc6TGljZW5zZTEz",
        },
    }


def _mock_transport_for_repositories(
    repositories: dict[tuple[str, str], dict | Exception],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET" or not request.url.path.startswith("/repos/"):
            return httpx.Response(404, json={"message": "Not Found"})

        parts = [part for part in request.url.path.split("/") if part]
        if len(parts) < 3 or parts[0] != "repos":
            return httpx.Response(404, json={"message": "Not Found"})

        key = (parts[1], parts[2])
        outcome = repositories.get(key)
        if isinstance(outcome, Exception):
            if isinstance(outcome, GitHubNotFoundError):
                return httpx.Response(404, json={"message": str(outcome)})
            if isinstance(outcome, GitHubAuthenticationError):
                return httpx.Response(401, json={"message": str(outcome)})
            raise outcome

        if outcome is None:
            return httpx.Response(404, json={"message": "Not Found"})

        return httpx.Response(200, json=outcome)

    return httpx.MockTransport(handler)


def _analysis_with_github_urls(**resource_overrides) -> PaperReproductionAnalysis:
    external_resources = resource_overrides.get(
        "external_resources",
        [
            ExternalResource(
                resource_type="code_repository",
                name="official-release",
                url="https://github.com/octocat/Hello-World",
                notes="Paper-stated repository",
            )
        ],
    )
    artifacts = resource_overrides.get("artifacts", [])
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(title="Test Paper", arxiv_id="1234.5678"),
        goal=AnalysisGoal(scope=ReproductionScope.TRAINING, research_goal="Reproduce."),
        resources=AnalysisResources(
            external_resources=external_resources,
            artifacts=artifacts,
        ),
        reproduction_gaps=[
            ReproductionGap(
                category=GapCategory.REPOSITORY,
                description="Repository URL cited in analysis resources.",
            )
        ],
    )


def _github_provider(
    repositories: dict[tuple[str, str], dict | Exception],
) -> GitHubCollectionProvider:
    transport = _mock_transport_for_repositories(repositories)
    client = GitHubClient(
        auth=GitHubAuth(token="ghp_test_token"),
        http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
    )
    return GitHubCollectionProvider(client=client, mapper=GitHubMapper())


class GitHubCollectionProviderTest(unittest.TestCase):
    def test_valid_repository_url(self) -> None:
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        result = provider.collect(_analysis_with_github_urls())

        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.identity.provider_native_id, "octocat/Hello-World")
        self.assertEqual(candidate.provider, DiscoveryProvider.GITHUB)
        self.assertEqual(candidate.resource_type, ResourceType.OFFICIAL_REPOSITORY)
        self.assertEqual(candidate.extensions["github_owner"], "octocat")
        self.assertEqual(candidate.extensions["github_default_branch"], "main")
        self.assertEqual(candidate.extensions["github_license"], "MIT")
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.SUCCESS)

    def test_multiple_repository_urls(self) -> None:
        analysis = _analysis_with_github_urls(
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="repo-a",
                    url="https://github.com/octocat/Hello-World",
                ),
                ExternalResource(
                    resource_type="community_repository",
                    name="repo-b",
                    url="https://github.com/github/linguist",
                ),
            ]
        )
        provider = _github_provider(
            {
                ("octocat", "Hello-World"): _repository_payload(),
                ("github", "linguist"): _repository_payload(
                    full_name="github/linguist",
                    html_url="https://github.com/github/linguist",
                    description="Language detection",
                ),
            }
        )
        result = provider.collect(analysis)
        self.assertEqual(len(result.candidates), 2)
        full_names = {candidate.identity.provider_native_id for candidate in result.candidates}
        self.assertEqual(full_names, {"octocat/Hello-World", "github/linguist"})

    def test_duplicate_urls_produce_single_candidate(self) -> None:
        analysis = _analysis_with_github_urls(
            external_resources=[
                ExternalResource(
                    resource_type="code_repository",
                    name="repo-a",
                    url="https://github.com/octocat/Hello-World",
                ),
                ExternalResource(
                    resource_type="code_repository",
                    name="repo-b",
                    url="https://www.github.com/octocat/Hello-World/",
                ),
            ]
        )
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        result = provider.collect(analysis)
        self.assertEqual(len(result.candidates), 1)

    def test_non_repository_github_urls_are_ignored(self) -> None:
        analysis = _analysis_with_github_urls(
            external_resources=[
                ExternalResource(
                    resource_type="project_page",
                    name="project-page",
                    url="https://github.com/octocat/Hello-World",
                ),
            ]
        )
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        result = provider.collect(analysis)
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.SKIPPED)

    def test_repository_not_found_records_provider_outcome(self) -> None:
        provider = _github_provider(
            {("octocat", "Hello-World"): GitHubNotFoundError("Repository not found")}
        )
        result = provider.collect(_analysis_with_github_urls())
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.FAILED)
        self.assertIn("repository not found", result.provider_outcomes[0].error_summary or "")

    def test_authentication_failure_records_provider_outcome(self) -> None:
        provider = _github_provider(
            {("octocat", "Hello-World"): GitHubAuthenticationError("Bad credentials")}
        )
        result = provider.collect(_analysis_with_github_urls())
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.FAILED)
        self.assertIn("authentication failed", result.provider_outcomes[0].error_summary or "")

    def test_search_api_not_used(self) -> None:
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        with mock.patch.object(
            provider._client,
            "search_repositories",
            side_effect=AssertionError("search API must not be used"),
        ):
            provider.collect(_analysis_with_github_urls())

    def test_artifact_github_repository_url(self) -> None:
        analysis = _analysis_with_github_urls(
            external_resources=[],
            artifacts=[
                ArtifactReference(
                    artifact_type=ArtifactType.CONFIG,
                    name="config-repo",
                    location="https://github.com/octocat/config-repo",
                )
            ],
        )
        provider = _github_provider(
            {
                ("octocat", "config-repo"): _repository_payload(
                    full_name="octocat/config-repo",
                    html_url="https://github.com/octocat/config-repo",
                )
            }
        )
        result = provider.collect(analysis)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].collection_source.source_query, "resources.artifacts:config-repo")


class GitHubUrlExtractionTest(unittest.TestCase):
    def test_parse_github_repository_url(self) -> None:
        self.assertEqual(
            parse_github_repository_url("https://github.com/octocat/Hello-World.git"),
            ("octocat", "Hello-World"),
        )
        self.assertIsNone(parse_github_repository_url("https://example.com/octocat/Hello-World"))
        self.assertTrue(is_github_repository_url("https://github.com/octocat/Hello-World"))

    def test_extract_ignores_datasets_and_non_repository_resources(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="T"),
            goal=AnalysisGoal(research_goal="g"),
            resources=AnalysisResources(
                datasets=[],
                external_resources=[
                    ExternalResource(
                        resource_type="dataset",
                        name="dataset",
                        url="https://github.com/octocat/dataset-repo",
                    ),
                    ExternalResource(
                        resource_type="model_card",
                        name="model-card",
                        url="https://github.com/octocat/model-card",
                    ),
                ],
            ),
        )
        self.assertEqual(extract_github_repository_urls(analysis), [])


class GitHubMapperRepositoryCandidateTest(unittest.TestCase):
    def test_repository_to_candidate_maps_required_fields(self) -> None:
        repository = GitHubRepositoryDTO.model_validate(_repository_payload())
        candidate = GitHubMapper().repository_to_candidate(
            repository,
            source_url="https://github.com/octocat/Hello-World",
            source_query="resources.external_resources:official-release",
            collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(candidate.url, "https://github.com/octocat/Hello-World")
        self.assertEqual(candidate.identity.provider_native_id, "octocat/Hello-World")
        self.assertEqual(candidate.extensions["github_topics"], "demo")
        self.assertEqual(candidate.extensions["source_url"], "https://github.com/octocat/Hello-World")


class GitHubCollectionServiceIntegrationTest(unittest.TestCase):
    def test_collection_service_merges_embedded_and_github_candidates(self) -> None:
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        service = CollectionService(
            providers=[
                EmbeddedResourceProvider(),
                provider,
                NoOpCollectionProvider(),
            ]
        )
        result = service.collect(_analysis_with_github_urls())
        self.assertGreaterEqual(len(result.candidates), 1)
        providers = {candidate.provider for candidate in result.candidates}
        self.assertIn(DiscoveryProvider.GITHUB, providers)
        provider_names = [outcome.provider_name for outcome in result.provider_outcomes]
        self.assertEqual(provider_names.count("embedded_resource"), 1)
        self.assertEqual(provider_names.count("github"), 1)
        self.assertEqual(result.candidates[0].identity.provider_native_id, "octocat/Hello-World")

    def test_default_provider_order_includes_github(self) -> None:
        from services.discovery.collection_service import _default_providers

        provider_types = [type(provider).__name__ for provider in _default_providers()]
        self.assertEqual(
            provider_types,
            [
                "EmbeddedResourceProvider",
                "GitHubCollectionProvider",
                "NoOpCollectionProvider",
            ],
        )


class GitHubCollectionWorkflowTest(unittest.TestCase):
    def test_workflow_end_to_end_with_mock_github_provider(self) -> None:
        provider = _github_provider({("octocat", "Hello-World"): _repository_payload()})
        workflow = DiscoveryWorkflow(
            collection_service=CollectionService(
                providers=[
                    EmbeddedResourceProvider(),
                    provider,
                    NoOpCollectionProvider(),
                ]
            ),
            evidence_service=EvidenceService.default(),
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_github_urls())
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        github_candidates = [
            candidate
            for candidate in discovery.candidate_resources.candidates
            if candidate.provider == DiscoveryProvider.GITHUB
        ]
        self.assertEqual(len(github_candidates), 1)
        self.assertEqual(github_candidates[0].identity.provider_native_id, "octocat/Hello-World")


if __name__ == "__main__":
    unittest.main()
