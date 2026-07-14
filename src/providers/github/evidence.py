"""GitHub EvidenceProvider — repository metadata and README evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DiscoveryProvider,
    ProviderInvocationStatus,
    ProviderRecord,
    RepositoryCandidate,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from providers.github.client import GitHubClient
from providers.github.exceptions import (
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubProviderError,
    GitHubRateLimitError,
    GitHubReadmeNotFoundError,
    GitHubTimeoutError,
)
from providers.github.mapper import GitHubMapper

_PROVIDER_NAME = "github_evidence"
_PROVIDER_VERSION = "1.0.0"


class GitHubEvidenceProvider:
    """Collect GitHub API metadata and README evidence for GitHub candidates."""

    def __init__(
        self,
        client: GitHubClient | None = None,
        mapper: GitHubMapper | None = None,
    ) -> None:
        self._client = client or GitHubClient()
        self._mapper = mapper or GitHubMapper()

    def collect(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        candidates: list[RepositoryCandidate],
    ) -> EvidenceProviderResult:
        del analysis, collection_result
        now = datetime.now(UTC)
        github_candidates = _github_candidates(candidates)
        if not github_candidates:
            return EvidenceProviderResult(
                provider_outcomes=[
                    ProviderRecord(
                        provider_name=_PROVIDER_NAME,
                        provider_version=_PROVIDER_VERSION,
                        invoked_at=now,
                        status=ProviderInvocationStatus.SKIPPED,
                        evidence_contributed=0,
                    )
                ]
            )

        records = []
        errors: list[str] = []
        readme_missing_count = 0
        auth_failed = False

        for candidate in github_candidates:
            full_name = candidate.identity.provider_native_id.strip()
            if not full_name or "/" not in full_name:
                errors.append(f"invalid GitHub candidate identity: {candidate.candidate_id}")
                continue

            owner, repo = self._mapper.parse_full_name(full_name)

            try:
                repository = self._client.get_repository(owner, repo)
                records.append(
                    self._mapper.repository_to_evidence(
                        repository,
                        candidate_id=candidate.candidate_id,
                        collected_at=now,
                    )
                )
            except GitHubAuthenticationError as exc:
                errors.append(f"authentication failed: {exc}")
                auth_failed = True
                break
            except GitHubNotFoundError:
                errors.append(f"repository not found: {full_name}")
                continue
            except (GitHubRateLimitError, GitHubTimeoutError, GitHubProviderError) as exc:
                errors.append(f"{full_name}: {exc}")
                continue

            try:
                readme = self._client.get_readme(owner, repo)
                records.append(
                    self._mapper.readme_to_evidence(
                        readme,
                        candidate_id=candidate.candidate_id,
                        collected_at=now,
                    )
                )
            except GitHubReadmeNotFoundError:
                readme_missing_count += 1
            except GitHubAuthenticationError as exc:
                errors.append(f"authentication failed: {exc}")
                auth_failed = True
                break
            except (GitHubRateLimitError, GitHubTimeoutError, GitHubProviderError) as exc:
                errors.append(f"{full_name}/readme: {exc}")
                continue

        status = _resolve_status(
            evidence_count=len(records),
            error_count=len(errors),
            readme_missing_count=readme_missing_count,
            auth_failed=auth_failed,
            candidate_count=len(github_candidates),
        )
        return EvidenceProviderResult(
            evidence_records=records,
            provider_outcomes=[
                ProviderRecord(
                    provider_name=_PROVIDER_NAME,
                    provider_version=_PROVIDER_VERSION,
                    invoked_at=now,
                    status=status,
                    evidence_contributed=len(records),
                    error_summary="; ".join(errors) if errors else None,
                )
            ],
        )


def _github_candidates(candidates: list[RepositoryCandidate]) -> list[RepositoryCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.provider == DiscoveryProvider.GITHUB
        or candidate.identity.provider == DiscoveryProvider.GITHUB
    ]


def _resolve_status(
    *,
    evidence_count: int,
    error_count: int,
    readme_missing_count: int,
    auth_failed: bool,
    candidate_count: int,
) -> ProviderInvocationStatus:
    if auth_failed:
        return ProviderInvocationStatus.FAILED
    if evidence_count == 0 and error_count > 0:
        return ProviderInvocationStatus.FAILED
    if readme_missing_count > 0 or error_count > 0:
        return ProviderInvocationStatus.PARTIAL
    if evidence_count > 0:
        return ProviderInvocationStatus.SUCCESS
    if candidate_count == 0:
        return ProviderInvocationStatus.SKIPPED
    return ProviderInvocationStatus.FAILED
