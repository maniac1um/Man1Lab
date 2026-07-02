import json
import unittest
from datetime import UTC, datetime

from providers.github.models import (
    GitHubErrorDTO,
    GitHubLicenseDTO,
    GitHubOwnerDTO,
    GitHubReadmeDTO,
    GitHubRepositoryDTO,
    GitHubSearchItemDTO,
    GitHubSearchResultDTO,
)


def _owner() -> GitHubOwnerDTO:
    return GitHubOwnerDTO(
        login="octocat",
        id=1,
        node_id="O_kgDOA",
        avatar_url="https://github.com/images/error/octocat_happy.gif",
        html_url="https://github.com/octocat",
        type="User",
    )


def _repository() -> GitHubRepositoryDTO:
    return GitHubRepositoryDTO(
        id=1296269,
        node_id="R_kgDOA",
        name="Hello-World",
        full_name="octocat/Hello-World",
        private=False,
        html_url="https://github.com/octocat/Hello-World",
        description="My first repository on GitHub!",
        fork=False,
        url="https://api.github.com/repos/octocat/Hello-World",
        created_at=datetime(2011, 1, 26, 19, 1, 12, tzinfo=UTC),
        updated_at=datetime(2011, 1, 26, 19, 14, 43, tzinfo=UTC),
        pushed_at=datetime(2011, 1, 26, 19, 6, 43, tzinfo=UTC),
        homepage="https://github.com",
        size=108,
        stargazers_count=80,
        watchers_count=80,
        language=None,
        forks_count=9,
        open_issues_count=0,
        archived=False,
        disabled=False,
        license=GitHubLicenseDTO(
            key="mit",
            name="MIT License",
            spdx_id="MIT",
            url="https://api.github.com/licenses/mit",
            node_id="MDc6TGljZW5zZTEz",
        ),
        topics=["octocat", "atom", "electron"],
        visibility="public",
        default_branch="main",
        owner=_owner(),
    )


class GitHubModelsTest(unittest.TestCase):
    def test_repository_dto_construction(self) -> None:
        repository = _repository()
        self.assertEqual(repository.full_name, "octocat/Hello-World")
        self.assertEqual(repository.owner.login, "octocat")
        self.assertEqual(repository.license.spdx_id if repository.license else None, "MIT")
        self.assertEqual(repository.topics, ["octocat", "atom", "electron"])

    def test_search_result_dto_defaults(self) -> None:
        result = GitHubSearchResultDTO()
        self.assertEqual(result.total_count, 0)
        self.assertFalse(result.incomplete_results)
        self.assertEqual(result.items, [])

    def test_readme_dto_construction(self) -> None:
        readme = GitHubReadmeDTO(
            content="IyBIZWxsbyBXb3JsZA==",
            encoding="base64",
            size=14,
            sha="abc123",
            url="https://api.github.com/repos/octocat/Hello-World/readme",
        )
        self.assertEqual(readme.encoding, "base64")
        self.assertEqual(readme.path, "README.md")

    def test_error_dto_construction(self) -> None:
        error = GitHubErrorDTO(
            message="Not Found",
            documentation_url="https://docs.github.com/rest",
            status=404,
        )
        self.assertEqual(error.status, 404)

    def test_frozen_models(self) -> None:
        repository = _repository()
        with self.assertRaises(Exception):
            repository.name = "changed"  # type: ignore[misc]

    def test_json_round_trip_repository(self) -> None:
        repository = _repository()
        restored = GitHubRepositoryDTO.model_validate(json.loads(repository.model_dump_json()))
        self.assertEqual(restored, repository)

    def test_json_round_trip_search_result(self) -> None:
        result = GitHubSearchResultDTO(
            total_count=1,
            incomplete_results=False,
            items=[
                GitHubSearchItemDTO(
                    id=1296269,
                    name="Hello-World",
                    full_name="octocat/Hello-World",
                    html_url="https://github.com/octocat/Hello-World",
                    owner=_owner(),
                )
            ],
        )
        restored = GitHubSearchResultDTO.model_validate(json.loads(result.model_dump_json()))
        self.assertEqual(restored, result)


if __name__ == "__main__":
    unittest.main()
