import base64
import unittest
from datetime import UTC, datetime

import httpx

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
    DiscoveryProvider,
    EvidenceSourceKind,
    EvidenceType,
    ProviderInvocationStatus,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceType,
    SCHEMA_VERSION,
)
from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
from providers.github.auth import GitHubAuth
from providers.github.client import GitHubClient
from providers.github.collection import GitHubCollectionProvider
from providers.github.evidence import GitHubEvidenceProvider
from providers.github.exceptions import GitHubAuthenticationError, GitHubReadmeNotFoundError
from providers.github.mapper import GitHubMapper
from providers.noop.collection import NoOpCollectionProvider
from providers.noop.noop_evidence_provider import NoOpEvidenceProvider
from services.discovery.collection_service import CollectionService
from services.discovery.evidence_service import EvidenceService
from services.discovery.ranking_service import RankingService
from services.discovery.verification_service import VerificationService


def _repository_payload(
    *,
    full_name: str = "octocat/Hello-World",
    html_url: str = "https://github.com/octocat/Hello-World",
) -> dict:
    owner, repo = full_name.split("/", 1)
    return {
        "id": 1296269,
        "node_id": "R_kgDOA",
        "name": repo,
        "full_name": full_name,
        "private": False,
        "html_url": html_url,
        "description": "My first repository on GitHub!",
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
        "language": "Python",
        "pushed_at": "2011-01-26T19:06:43Z",
        "updated_at": "2011-01-26T19:14:43Z",
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


def _readme_payload(*, text: str = "# Hello World") -> dict:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(encoded),
        "name": "README.md",
        "path": "README.md",
        "content": encoded,
        "sha": "abc123",
        "url": "https://api.github.com/repos/octocat/Hello-World/readme",
        "html_url": "https://github.com/octocat/Hello-World/blob/main/README.md",
        "download_url": "https://raw.githubusercontent.com/octocat/Hello-World/main/README.md",
    }


def _mock_transport(
    *,
    repositories: dict[tuple[str, str], dict | Exception] | None = None,
    readmes: dict[tuple[str, str], dict | Exception | None] | None = None,
) -> httpx.MockTransport:
    repositories = repositories or {}
    readmes = readmes or {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET" or not request.url.path.startswith("/repos/"):
            return httpx.Response(404, json={"message": "Not Found"})

        parts = [part for part in request.url.path.split("/") if part]
        if len(parts) < 3 or parts[0] != "repos":
            return httpx.Response(404, json={"message": "Not Found"})

        owner, repo = parts[1], parts[2]
        key = (owner, repo)

        if len(parts) >= 4 and parts[3] == "readme":
            outcome = readmes.get(key, _readme_payload())
            if isinstance(outcome, Exception):
                if isinstance(outcome, GitHubReadmeNotFoundError):
                    return httpx.Response(404, json={"message": "Not Found"})
                if isinstance(outcome, GitHubAuthenticationError):
                    return httpx.Response(401, json={"message": "Bad credentials"})
                raise outcome
            if outcome is None:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, json=outcome)

        outcome = repositories.get(key)
        if isinstance(outcome, Exception):
            if isinstance(outcome, GitHubAuthenticationError):
                return httpx.Response(401, json={"message": "Bad credentials"})
            return httpx.Response(404, json={"message": "Not Found"})
        if outcome is None:
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json=outcome)

    return httpx.MockTransport(handler)


def _github_client(transport: httpx.MockTransport) -> GitHubClient:
    return GitHubClient(
        auth=GitHubAuth(token="ghp_test_token"),
        http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
    )


def _github_candidate(candidate_id: str = "github-abc") -> RepositoryCandidate:
    return RepositoryCandidate(
        candidate_id=candidate_id,
        identity=ResourceIdentity(
            provider=DiscoveryProvider.GITHUB,
            provider_native_id="octocat/Hello-World",
            normalized_url="https://github.com/octocat/Hello-World",
        ),
        provider=DiscoveryProvider.GITHUB,
        resource_type=ResourceType.OFFICIAL_REPOSITORY,
        url="https://github.com/octocat/Hello-World",
        collection_source=CollectionSource(
            source_type=CollectionSourceType.METADATA_LOOKUP,
            provider_name="github",
            source_query="resources.external_resources:official-release",
        ),
    )


def _analysis_with_github_repo() -> PaperReproductionAnalysis:
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


class GitHubEvidenceProviderTest(unittest.TestCase):
    def test_metadata_and_readme_evidence(self) -> None:
        client = _github_client(
            _mock_transport(
                repositories={("octocat", "Hello-World"): _repository_payload()},
                readmes={("octocat", "Hello-World"): _readme_payload(text="# Hello World")},
            )
        )
        provider = GitHubEvidenceProvider(client=client, mapper=GitHubMapper())
        result = provider.collect(
            _analysis_with_github_repo(),
            collection_result=type("Result", (), {"candidates": [_github_candidate()]})(),
            candidates=[_github_candidate()],
        )

        self.assertEqual(len(result.evidence_records), 2)
        types = {record.evidence_type for record in result.evidence_records}
        self.assertEqual(types, {EvidenceType.METADATA_EXTRACT, EvidenceType.README_CLAIM})
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.SUCCESS)

        metadata = next(
            record for record in result.evidence_records if record.evidence_type == EvidenceType.METADATA_EXTRACT
        )
        self.assertEqual(metadata.observed_fact.fields["owner"], "octocat")
        self.assertEqual(metadata.observed_fact.fields["stars"], 80)
        self.assertEqual(metadata.evidence_source.source_kind, EvidenceSourceKind.PROVIDER_API)

        readme = next(
            record for record in result.evidence_records if record.evidence_type == EvidenceType.README_CLAIM
        )
        self.assertEqual(readme.observed_fact.fields["readme_text"], "# Hello World")
        self.assertTrue(readme.observed_fact.fields["readme_exists"])

    def test_no_readme_still_produces_metadata_evidence(self) -> None:
        client = _github_client(
            _mock_transport(
                repositories={("octocat", "Hello-World"): _repository_payload()},
                readmes={("octocat", "Hello-World"): GitHubReadmeNotFoundError("missing")},
            )
        )
        provider = GitHubEvidenceProvider(client=client)
        result = provider.collect(
            _analysis_with_github_repo(),
            collection_result=type("Result", (), {"candidates": []})(),
            candidates=[_github_candidate()],
        )
        self.assertEqual(len(result.evidence_records), 1)
        self.assertEqual(result.evidence_records[0].evidence_type, EvidenceType.METADATA_EXTRACT)
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.PARTIAL)

    def test_authentication_failure_records_provider_outcome(self) -> None:
        client = _github_client(
            _mock_transport(
                repositories={("octocat", "Hello-World"): GitHubAuthenticationError("Bad credentials")},
            )
        )
        provider = GitHubEvidenceProvider(client=client)
        result = provider.collect(
            _analysis_with_github_repo(),
            collection_result=type("Result", (), {"candidates": []})(),
            candidates=[_github_candidate()],
        )
        self.assertEqual(result.evidence_records, [])
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.FAILED)
        self.assertIn("authentication failed", result.provider_outcomes[0].error_summary or "")

    def test_skips_non_github_candidates(self) -> None:
        client = _github_client(_mock_transport())
        provider = GitHubEvidenceProvider(client=client)
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
        result = provider.collect(
            _analysis_with_github_repo(),
            collection_result=type("Result", (), {"candidates": []})(),
            candidates=[foreign],
        )
        self.assertEqual(result.evidence_records, [])
        self.assertEqual(result.provider_outcomes[0].status, ProviderInvocationStatus.SKIPPED)


class GitHubClientReadmeTest(unittest.TestCase):
    def test_get_readme_decodes_base64_utf8(self) -> None:
        client = _github_client(
            _mock_transport(readmes={("octocat", "Hello-World"): _readme_payload(text="# README")})
        )
        readme = client.get_readme("octocat", "Hello-World")
        self.assertEqual(readme.decoded_text, "# README")
        self.assertEqual(readme.encoding, "base64")

    def test_get_readme_not_found_raises_readme_not_found(self) -> None:
        client = _github_client(
            _mock_transport(readmes={("octocat", "Hello-World"): GitHubReadmeNotFoundError("missing")})
        )
        with self.assertRaises(GitHubReadmeNotFoundError):
            client.get_readme("octocat", "Hello-World")


class GitHubEvidenceServiceIntegrationTest(unittest.TestCase):
    def test_evidence_service_merges_embedded_and_github_evidence(self) -> None:
        transport = _mock_transport(
            repositories={("octocat", "Hello-World"): _repository_payload()},
            readmes={("octocat", "Hello-World"): _readme_payload()},
        )
        client = _github_client(transport)
        collection_service = CollectionService(
            providers=[
                EmbeddedResourceProvider(),
                GitHubCollectionProvider(client=client),
                NoOpCollectionProvider(),
            ]
        )
        evidence_service = EvidenceService(
            providers=[
                EmbeddedEvidenceProvider(),
                GitHubEvidenceProvider(client=client),
                NoOpEvidenceProvider(),
            ]
        )
        analysis = _analysis_with_github_repo()
        collection = collection_service.collect(analysis)
        result = evidence_service.collect(analysis, collection)

        github_records = [
            record
            for record in result.evidence_records
            if record.evidence_source.provider_name in {"github", "github_evidence"}
            or record.evidence_type in {EvidenceType.METADATA_EXTRACT, EvidenceType.README_CLAIM}
            and record.candidate_id.startswith("github-")
        ]
        self.assertGreaterEqual(len(github_records), 2)
        provider_names = [outcome.provider_name for outcome in result.provider_outcomes]
        self.assertIn("embedded_evidence", provider_names)
        self.assertIn("github_evidence", provider_names)

    def test_default_provider_order_includes_github_evidence(self) -> None:
        from services.discovery.evidence_service import _default_providers

        provider_types = [type(provider).__name__ for provider in _default_providers()]
        self.assertEqual(
            provider_types,
            [
                "EmbeddedEvidenceProvider",
                "GitHubEvidenceProvider",
                "NoOpEvidenceProvider",
            ],
        )


class GitHubEvidenceWorkflowIntegrationTest(unittest.TestCase):
    def test_workflow_collects_github_evidence(self) -> None:
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
            verification_service=VerificationService.default(),
            ranking_service=RankingService.default(),
        )
        discovery = workflow.run(_analysis_with_github_repo())
        self.assertEqual(discovery.schema_version, SCHEMA_VERSION)
        github_evidence = [
            record
            for record in discovery.evidence.records
            if record.evidence_type in {EvidenceType.METADATA_EXTRACT, EvidenceType.README_CLAIM}
            and record.evidence_source.provider_name == "github"
        ]
        self.assertGreaterEqual(len(github_evidence), 2)


if __name__ == "__main__":
    unittest.main()
