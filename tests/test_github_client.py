import base64
import os
import unittest
from unittest import mock

import httpx

from providers.github.auth import GitHubAuth
from providers.github.client import GitHubClient
from providers.github.exceptions import (
    GitHubApiError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubProviderError,
    GitHubRateLimitError,
    GitHubReadmeNotFoundError,
    GitHubTimeoutError,
)
from providers.github.models import GitHubReadmeDTO, GitHubRepositoryDTO


class GitHubAuthTest(unittest.TestCase):
    def test_injected_token_resolution(self) -> None:
        auth = GitHubAuth(token="ghp_injected_token_value")
        self.assertEqual(auth.resolve_token(), "ghp_injected_token_value")

    def test_environment_token_resolution(self) -> None:
        auth = GitHubAuth()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_env_token_value"}, clear=False):
            self.assertEqual(auth.resolve_token(), "ghp_env_token_value")

    def test_unauthenticated_when_no_token(self) -> None:
        auth = GitHubAuth()
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(auth.resolve_token())
            self.assertEqual(auth.authorization_header(), {})

    def test_authorization_header_creation(self) -> None:
        auth = GitHubAuth(token="ghp_test_token_12345678")
        self.assertEqual(
            auth.authorization_header(),
            {"Authorization": "Bearer ghp_test_token_12345678"},
        )

    def test_request_headers_include_github_defaults(self) -> None:
        auth = GitHubAuth(token="ghp_test_token_12345678")
        headers = auth.request_headers({"User-Agent": "man1lab-discovery"})
        self.assertEqual(headers["Authorization"], "Bearer ghp_test_token_12345678")
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")
        self.assertEqual(headers["User-Agent"], "man1lab-discovery")

    def test_token_masking(self) -> None:
        self.assertEqual(GitHubAuth.mask_token(None), "<none>")
        self.assertEqual(GitHubAuth.mask_token(""), "<none>")
        self.assertEqual(GitHubAuth.mask_token("short"), "***")
        self.assertEqual(
            GitHubAuth.mask_token("ghp_test_token_12345678"),
            "ghp_...5678",
        )

    def test_repr_never_exposes_raw_token(self) -> None:
        auth = GitHubAuth(token="ghp_test_token_12345678")
        representation = repr(auth)
        self.assertNotIn("ghp_test_token_12345678", representation)
        self.assertIn("ghp_...5678", representation)


class GitHubClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(GitHubAuth(token="ghp_test_token_12345678"))

    def test_client_interface_exists(self) -> None:
        self.assertIsInstance(self.client, GitHubClient)
        self.assertIsInstance(self.client.auth, GitHubAuth)
        self.assertTrue(callable(self.client.get_repository))
        self.assertTrue(callable(self.client.get_readme))
        self.assertTrue(callable(self.client.search_repositories))

    def test_get_repository_success(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "Hello-World",
                    "full_name": "octocat/Hello-World",
                    "html_url": "https://github.com/octocat/Hello-World",
                    "owner": {
                        "login": "octocat",
                        "id": 1,
                        "node_id": "O_kgDOA",
                        "avatar_url": "https://github.com/octocat.png",
                        "html_url": "https://github.com/octocat",
                        "type": "User",
                    },
                },
            )
        )
        client = GitHubClient(
            auth=GitHubAuth(token="ghp_test_token_12345678"),
            http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
        )
        repository = client.get_repository("octocat", "Hello-World")
        self.assertIsInstance(repository, GitHubRepositoryDTO)
        self.assertEqual(repository.full_name, "octocat/Hello-World")

    def test_get_repository_not_found(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(404, json={"message": "Not Found"})
        )
        client = GitHubClient(
            http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
        )
        with self.assertRaises(GitHubNotFoundError):
            client.get_repository("octocat", "missing")

    def test_get_repository_authentication_error(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"message": "Bad credentials"})
        )
        client = GitHubClient(
            http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
        )
        with self.assertRaises(GitHubAuthenticationError):
            client.get_repository("octocat", "Hello-World")

    def test_get_readme_success(self) -> None:
        encoded = base64.b64encode(b"# README").decode("ascii")
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "type": "file",
                    "encoding": "base64",
                    "size": len(encoded),
                    "name": "README.md",
                    "path": "README.md",
                    "content": encoded,
                    "sha": "abc123",
                    "url": "https://api.github.com/repos/octocat/Hello-World/readme",
                },
            )
        )
        client = GitHubClient(
            http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
        )
        readme = client.get_readme("octocat", "Hello-World")
        self.assertIsInstance(readme, GitHubReadmeDTO)
        self.assertEqual(readme.decoded_text, "# README")

    def test_get_readme_not_found(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(404, json={"message": "Not Found"})
        )
        client = GitHubClient(
            http_client=httpx.Client(transport=transport, base_url="https://api.github.com"),
        )
        with self.assertRaises(GitHubReadmeNotFoundError):
            client.get_readme("octocat", "Hello-World")

    def test_search_repositories_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.client.search_repositories("resnet arxiv")


class GitHubExceptionsTest(unittest.TestCase):
    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(GitHubAuthenticationError, GitHubProviderError))
        self.assertTrue(issubclass(GitHubRateLimitError, GitHubProviderError))
        self.assertTrue(issubclass(GitHubNotFoundError, GitHubProviderError))
        self.assertTrue(issubclass(GitHubApiError, GitHubProviderError))
        self.assertTrue(issubclass(GitHubReadmeNotFoundError, GitHubNotFoundError))

    def test_exceptions_are_catchable_by_base_type(self) -> None:
        with self.assertRaises(GitHubProviderError):
            raise GitHubNotFoundError("Repository not found")


if __name__ == "__main__":
    unittest.main()
