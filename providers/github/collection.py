"""GitHub CollectionProvider — resolve explicit paper GitHub repository URLs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ProviderInvocationStatus, ProviderRecord
from ports.collection_provider import CollectionProviderResult
from providers.github.client import GitHubClient
from providers.github.exceptions import (
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubProviderError,
    GitHubRateLimitError,
    GitHubTimeoutError,
)
from providers.github.mapper import GitHubMapper
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "github"
_PROVIDER_VERSION = "1.0.0"
_REPOSITORY_RESOURCE_TYPES = frozenset(
    {
        "code_repository",
        "repository",
        "official_repository",
        "community_repository",
    }
)
_RESERVED_GITHUB_OWNERS = frozenset(
    {
        "apps",
        "features",
        "login",
        "marketplace",
        "settings",
        "site",
    }
)


class GitHubCollectionProvider:
    """Resolve explicit GitHub repository URLs cited in analysis."""

    def __init__(
        self,
        client: GitHubClient | None = None,
        mapper: GitHubMapper | None = None,
    ) -> None:
        self._client = client or GitHubClient()
        self._mapper = mapper or GitHubMapper()

    def collect(self, analysis: PaperReproductionAnalysis) -> CollectionProviderResult:
        now = datetime.now(UTC)
        source_urls = extract_github_repository_urls(analysis)
        if not source_urls:
            return CollectionProviderResult(
                provider_outcomes=[
                    ProviderRecord(
                        provider_name=_PROVIDER_NAME,
                        provider_version=_PROVIDER_VERSION,
                        invoked_at=now,
                        status=ProviderInvocationStatus.SKIPPED,
                        candidates_contributed=0,
                    )
                ]
            )

        candidates = []
        errors: list[str] = []
        seen_full_names: set[str] = set()

        for source_url, source_query in source_urls:
            parsed = parse_github_repository_url(source_url)
            if parsed is None:
                errors.append(f"invalid GitHub repository URL: {source_url}")
                continue

            owner, repo = parsed
            full_name = f"{owner}/{repo}"
            if full_name in seen_full_names:
                continue

            try:
                repository = self._client.get_repository(owner, repo)
                candidate = self._mapper.repository_to_candidate(
                    repository,
                    source_url=source_url,
                    source_query=source_query,
                    collected_at=now,
                )
            except GitHubNotFoundError:
                errors.append(f"repository not found: {full_name}")
                continue
            except GitHubAuthenticationError as exc:
                errors.append(f"authentication failed: {exc}")
                break
            except (GitHubRateLimitError, GitHubTimeoutError, GitHubProviderError) as exc:
                errors.append(f"{full_name}: {exc}")
                continue

            candidates.append(candidate)
            seen_full_names.add(full_name)

        status = _resolve_status(candidate_count=len(candidates), error_count=len(errors))
        return CollectionProviderResult(
            candidates=candidates,
            provider_outcomes=[
                ProviderRecord(
                    provider_name=_PROVIDER_NAME,
                    provider_version=_PROVIDER_VERSION,
                    invoked_at=now,
                    status=status,
                    candidates_contributed=len(candidates),
                    error_summary="; ".join(errors) if errors else None,
                )
            ],
        )


def extract_github_repository_urls(
    analysis: PaperReproductionAnalysis,
) -> list[tuple[str, str]]:
    """Return explicit GitHub repository URLs and their analysis field provenance."""
    results: list[tuple[str, str]] = []
    seen_normalized_urls: set[str] = set()

    for resource in analysis.resources.external_resources:
        if not _is_repository_resource_type(resource.resource_type):
            continue
        url = resource.url.strip()
        if not is_github_repository_url(url):
            continue
        normalized = normalize_url(url)
        if normalized in seen_normalized_urls:
            continue
        seen_normalized_urls.add(normalized)
        results.append((url, f"resources.external_resources:{resource.name}"))

    for artifact in analysis.resources.artifacts:
        url = artifact.location.strip()
        if not is_github_repository_url(url):
            continue
        normalized = normalize_url(url)
        if normalized in seen_normalized_urls:
            continue
        seen_normalized_urls.add(normalized)
        results.append((url, f"resources.artifacts:{artifact.name}"))

    return results


def is_github_repository_url(url: str) -> bool:
    return parse_github_repository_url(url) is not None


def parse_github_repository_url(url: str) -> tuple[str, str] | None:
    """Parse ``owner`` and ``repo`` from a GitHub repository web URL."""
    text = url.strip()
    if not text:
        return None

    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        return None

    owner = path_parts[0]
    repo = path_parts[1]
    if owner in _RESERVED_GITHUB_OWNERS:
        return None
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _REPO_NAME_PATTERN.fullmatch(repo):
        return None

    return owner, repo


def _is_repository_resource_type(resource_type: str) -> bool:
    normalized = resource_type.strip().casefold().replace("-", "_").replace(" ", "_")
    return normalized in _REPOSITORY_RESOURCE_TYPES


def _resolve_status(*, candidate_count: int, error_count: int) -> ProviderInvocationStatus:
    if candidate_count > 0 and error_count == 0:
        return ProviderInvocationStatus.SUCCESS
    if candidate_count > 0 and error_count > 0:
        return ProviderInvocationStatus.PARTIAL
    if error_count > 0:
        return ProviderInvocationStatus.FAILED
    return ProviderInvocationStatus.SKIPPED


_REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
