import unittest
from datetime import UTC, datetime

from providers.github.mapper import GitHubMapper
from providers.github.models import (
    GitHubLicenseDTO,
    GitHubOwnerDTO,
    GitHubReadmeDTO,
    GitHubRepositoryDTO,
    GitHubSearchItemDTO,
)


class GitHubMapperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = GitHubMapper()

    def test_mapper_construction(self) -> None:
        self.assertIsInstance(self.mapper, GitHubMapper)

    def test_parse_full_name(self) -> None:
        owner, repo = GitHubMapper.parse_full_name("octocat/Hello-World")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")

    def test_parse_full_name_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValueError):
            GitHubMapper.parse_full_name("invalid")

    def test_repository_html_url(self) -> None:
        repository = GitHubRepositoryDTO(
            id=1,
            name="Hello-World",
            full_name="octocat/Hello-World",
            html_url="https://github.com/octocat/Hello-World",
            owner=GitHubOwnerDTO(login="octocat", id=1),
        )
        self.assertEqual(
            GitHubMapper.repository_html_url(repository),
            "https://github.com/octocat/Hello-World",
        )

    def test_repository_to_candidate_maps_fields(self) -> None:
        repository = GitHubRepositoryDTO(
            id=1,
            name="Hello-World",
            full_name="octocat/Hello-World",
            html_url="https://github.com/octocat/Hello-World",
            description="Repository description",
            owner=GitHubOwnerDTO(login="octocat", id=1),
            default_branch="main",
            topics=["demo"],
            license=GitHubLicenseDTO(key="mit", name="MIT License", spdx_id="MIT"),
        )
        candidate = GitHubMapper().repository_to_candidate(
            repository,
            source_url="https://github.com/octocat/Hello-World",
            source_query="resources.external_resources:official-release",
            collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(candidate.identity.provider_native_id, "octocat/Hello-World")
        self.assertEqual(candidate.extensions["github_owner"], "octocat")
        self.assertEqual(candidate.extensions["github_license"], "MIT")

    def test_repository_to_candidate_not_fork(self) -> None:
        repository = GitHubRepositoryDTO(
            id=1,
            name="Hello-World",
            full_name="octocat/Hello-World",
            owner=GitHubOwnerDTO(login="octocat", id=1),
        )
        candidate = GitHubMapper().repository_to_candidate(
            repository,
            source_url="https://github.com/octocat/Hello-World",
            source_query="resources.external_resources:repo",
            collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(candidate.resource_type.value, "official_repository")

    def test_search_item_to_candidate_not_implemented(self) -> None:
        item = GitHubSearchItemDTO(
            id=1,
            name="Hello-World",
            full_name="octocat/Hello-World",
            owner=GitHubOwnerDTO(login="octocat", id=1),
        )
        with self.assertRaises(NotImplementedError):
            self.mapper.search_item_to_candidate(item)

    def test_readme_to_evidence_maps_fields(self) -> None:
        readme = GitHubReadmeDTO(
            content="IyBIZWxsbyBXb3JsZA==",
            encoding="base64",
            decoded_text="# Hello World",
            size=13,
            path="README.md",
            html_url="https://github.com/octocat/Hello-World/blob/main/README.md",
        )
        record = GitHubMapper().readme_to_evidence(
            readme,
            candidate_id="github-abc",
            collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(record.evidence_type.value, "readme_claim")
        self.assertEqual(record.observed_fact.fields["readme_text"], "# Hello World")
        self.assertTrue(record.observed_fact.fields["readme_exists"])

    def test_repository_to_evidence_maps_metadata(self) -> None:
        repository = GitHubRepositoryDTO(
            id=1,
            name="Hello-World",
            full_name="octocat/Hello-World",
            html_url="https://github.com/octocat/Hello-World",
            description="Repository description",
            owner=GitHubOwnerDTO(login="octocat", id=1),
            default_branch="main",
            topics=["demo"],
            license=GitHubLicenseDTO(key="mit", name="MIT License", spdx_id="MIT"),
            stargazers_count=10,
            forks_count=2,
            open_issues_count=1,
            language="Python",
        )
        record = GitHubMapper().repository_to_evidence(
            repository,
            candidate_id="github-abc",
            collected_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(record.evidence_type.value, "metadata_extract")
        self.assertEqual(record.observed_fact.fields["owner"], "octocat")
        self.assertEqual(record.observed_fact.fields["license"], "MIT")


if __name__ == "__main__":
    unittest.main()
