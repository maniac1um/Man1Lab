"""GitHub REST client — sole HTTP knowledge for the GitHub provider."""

from __future__ import annotations

import base64
import binascii
import json

import httpx

from providers.github.auth import GitHubAuth
from providers.github.exceptions import (
    GitHubApiError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubReadmeNotFoundError,
    GitHubTimeoutError,
)
from providers.github.models import GitHubErrorDTO, GitHubReadmeDTO, GitHubRepositoryDTO, GitHubSearchResultDTO

_API_BASE_URL = "https://api.github.com"


class GitHubClient:
    """Thin GitHub REST client facade."""

    def __init__(
        self,
        auth: GitHubAuth | None = None,
        *,
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._auth = auth or GitHubAuth()
        self._timeout = timeout_seconds
        self._http_client = http_client

    @property
    def auth(self) -> GitHubAuth:
        return self._auth

    def get_repository(self, owner: str, repo: str) -> GitHubRepositoryDTO:
        """Fetch repository metadata for ``GET /repos/{owner}/{repo}``."""
        response = self._request("GET", f"/repos/{owner}/{repo}")
        return self._parse_repository_response(response, owner=owner, repo=repo)

    def get_readme(self, owner: str, repo: str) -> GitHubReadmeDTO:
        """Fetch repository README for ``GET /repos/{owner}/{repo}/readme``."""
        response = self._request("GET", f"/repos/{owner}/{repo}/readme")
        return self._parse_readme_response(response, owner=owner, repo=repo)

    def search_repositories(
        self,
        query: str,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> GitHubSearchResultDTO:
        """Search repositories for ``GET /search/repositories``."""
        raise NotImplementedError("GitHub search transport is not implemented in Phase 1.2")

    def _request(self, method: str, path: str) -> httpx.Response:
        url = f"{_API_BASE_URL}{path}"
        headers = self._auth.request_headers()
        try:
            if self._http_client is not None:
                return self._http_client.request(method, url, headers=headers)
            with httpx.Client(timeout=self._timeout) as client:
                return client.request(method, url, headers=headers)
        except httpx.TimeoutException as exc:
            raise GitHubTimeoutError(f"GitHub request timed out for {path}") from exc
        except httpx.HTTPError as exc:
            raise GitHubApiError(f"GitHub request failed for {path}: {exc}") from exc

    def _parse_repository_response(
        self,
        response: httpx.Response,
        *,
        owner: str,
        repo: str,
    ) -> GitHubRepositoryDTO:
        if response.status_code == 200:
            payload = response.json()
            if not isinstance(payload, dict):
                raise GitHubApiError(f"Unexpected GitHub repository payload for {owner}/{repo}")
            return GitHubRepositoryDTO.model_validate(payload)

        error = _parse_error_payload(response)
        if response.status_code == 404:
            raise GitHubNotFoundError(error.message or f"Repository not found: {owner}/{repo}")
        if response.status_code == 401:
            raise GitHubAuthenticationError(error.message or "GitHub authentication failed")
        if response.status_code == 403:
            message = error.message.lower()
            if "rate limit" in message:
                raise GitHubRateLimitError(error.message or "GitHub rate limit exceeded")
            raise GitHubApiError(error.message or f"GitHub API forbidden for {owner}/{repo}")
        raise GitHubApiError(
            error.message or f"GitHub API error ({response.status_code}) for {owner}/{repo}"
        )

    def _parse_readme_response(
        self,
        response: httpx.Response,
        *,
        owner: str,
        repo: str,
    ) -> GitHubReadmeDTO:
        if response.status_code == 200:
            payload = response.json()
            if not isinstance(payload, dict):
                raise GitHubApiError(f"Unexpected GitHub README payload for {owner}/{repo}")
            readme = GitHubReadmeDTO.model_validate(payload)
            return _decode_readme_text(readme)

        error = _parse_error_payload(response)
        if response.status_code == 404:
            raise GitHubReadmeNotFoundError(
                error.message or f"README not found for repository: {owner}/{repo}"
            )
        if response.status_code == 401:
            raise GitHubAuthenticationError(error.message or "GitHub authentication failed")
        if response.status_code == 403:
            message = error.message.lower()
            if "rate limit" in message:
                raise GitHubRateLimitError(error.message or "GitHub rate limit exceeded")
            raise GitHubApiError(error.message or f"GitHub API forbidden for {owner}/{repo}/readme")
        raise GitHubApiError(
            error.message or f"GitHub API error ({response.status_code}) for {owner}/{repo}/readme"
        )


def _decode_readme_text(readme: GitHubReadmeDTO) -> GitHubReadmeDTO:
    if readme.encoding.casefold() != "base64":
        return readme.model_copy(update={"decoded_text": readme.content})

    try:
        decoded = base64.b64decode(readme.content, validate=False).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise GitHubApiError("Failed to decode GitHub README content as UTF-8") from exc

    return readme.model_copy(update={"decoded_text": decoded})


def _parse_error_payload(response: httpx.Response) -> GitHubErrorDTO:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return GitHubErrorDTO(
            message=response.text or f"HTTP {response.status_code}",
            status=response.status_code,
        )
    if isinstance(payload, dict):
        return GitHubErrorDTO.model_validate(
            {
                "message": payload.get("message", response.text or f"HTTP {response.status_code}"),
                "documentation_url": payload.get("documentation_url"),
                "status": response.status_code,
            }
        )
    return GitHubErrorDTO(message=response.text or f"HTTP {response.status_code}", status=response.status_code)
