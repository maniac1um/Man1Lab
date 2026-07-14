"""Map GitHub DTOs to Discovery canonical models."""

from __future__ import annotations

import hashlib
from datetime import datetime

from models.research_resource_discovery import (
    CandidateStatus,
    CollectionSource,
    CollectionSourceType,
    DiscoveryProvider,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceType,
    FetchStatus,
    ObservedFact,
    Officiality,
    PaperRelation,
    PaperRelationType,
    RelationStrength,
    RepositoryCandidate,
    ResourceIdentity,
    ResourceType,
)
from providers.github.models import GitHubReadmeDTO, GitHubRepositoryDTO, GitHubSearchItemDTO
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "github"
_EXPLICIT_URL_CONFIDENCE = 0.95


class GitHubMapper:
    """Pure DTO-to-canonical transformations for the GitHub provider."""

    @staticmethod
    def parse_full_name(full_name: str) -> tuple[str, str]:
        """Split ``owner/repo`` into owner and repository components."""
        owner, separator, repo = full_name.partition("/")
        if not separator or not owner or not repo:
            raise ValueError(f"Invalid GitHub full_name: {full_name!r}")
        return owner, repo

    @staticmethod
    def repository_html_url(repository: GitHubRepositoryDTO) -> str:
        """Return the canonical HTML URL from a repository DTO."""
        return repository.html_url

    def repository_to_candidate(
        self,
        repository: GitHubRepositoryDTO,
        *,
        source_url: str,
        source_query: str,
        collected_at: datetime,
    ) -> RepositoryCandidate:
        """Map a repository DTO to a Discovery ``RepositoryCandidate``."""
        normalized_url = normalize_url(repository.html_url or source_url)
        resource_type = (
            ResourceType.COMMUNITY_REPOSITORY if repository.fork else ResourceType.OFFICIAL_REPOSITORY
        )
        officiality = Officiality.COMMUNITY if repository.fork else Officiality.OFFICIAL
        license_value = ""
        if repository.license is not None:
            license_value = repository.license.spdx_id or repository.license.key

        return RepositoryCandidate(
            candidate_id=_candidate_id(repository.full_name),
            identity=ResourceIdentity(
                provider=DiscoveryProvider.GITHUB,
                provider_native_id=repository.full_name,
                normalized_url=normalized_url,
            ),
            provider=DiscoveryProvider.GITHUB,
            resource_type=resource_type,
            tier=1,
            url=repository.html_url or source_url,
            title=repository.name,
            officiality=officiality,
            paper_relation=PaperRelation(
                relation_type=PaperRelationType.CITED_IN_PAPER,
                relation_strength=RelationStrength.EXPLICIT,
                matching_signals=[
                    f"analysis_field:{source_query}",
                    f"source_url:{source_url}",
                ],
            ),
            collection_source=CollectionSource(
                source_type=CollectionSourceType.METADATA_LOOKUP,
                provider_name=_PROVIDER_NAME,
                source_query=source_query,
            ),
            status=CandidateStatus.COLLECTED,
            confidence=_EXPLICIT_URL_CONFIDENCE,
            notes=repository.description or "",
            collected_at=collected_at,
            extensions={
                "github_owner": repository.owner.login,
                "github_default_branch": repository.default_branch,
                "github_license": license_value,
                "github_archived": str(repository.archived).lower(),
                "github_topics": ",".join(repository.topics),
                "source_url": source_url,
            },
        )

    def search_item_to_candidate(self, item: GitHubSearchItemDTO) -> RepositoryCandidate:
        """Map a search result item to a Discovery ``RepositoryCandidate``."""
        raise NotImplementedError("GitHub search mapping is not implemented in Phase 1.2")

    def readme_to_evidence(
        self,
        readme: GitHubReadmeDTO,
        *,
        candidate_id: str,
        collected_at: datetime,
    ) -> EvidenceRecord:
        """Map a README DTO to a Discovery ``EvidenceRecord``."""
        text = readme.decoded_text or readme.content
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        readme_url = readme.html_url or readme.download_url or readme.url

        return EvidenceRecord(
            evidence_id=_evidence_id(candidate_id, "readme"),
            candidate_id=candidate_id,
            evidence_type=EvidenceType.README_CLAIM,
            evidence_source=EvidenceSource(
                source_kind=EvidenceSourceKind.PROVIDER_API,
                provider_name=_PROVIDER_NAME,
                uri=readme_url,
                fetch_status=FetchStatus.SUCCESS,
            ),
            observed_fact=ObservedFact(
                fields={
                    "readme_exists": True,
                    "readme_url": readme_url,
                    "readme_text": text,
                    "content_hash": content_hash,
                    "encoding": readme.encoding,
                    "size": readme.size,
                }
            ),
            polarity=EvidencePolarity.NEUTRAL,
            confidence=1.0,
            collected_at=collected_at,
            raw_reference=readme.path,
        )

    def repository_to_evidence(
        self,
        repository: GitHubRepositoryDTO,
        *,
        candidate_id: str,
        collected_at: datetime,
    ) -> EvidenceRecord:
        """Map repository metadata to a Discovery ``EvidenceRecord``."""
        license_value = ""
        if repository.license is not None:
            license_value = repository.license.spdx_id or repository.license.key

        return EvidenceRecord(
            evidence_id=_evidence_id(candidate_id, "metadata"),
            candidate_id=candidate_id,
            evidence_type=EvidenceType.METADATA_EXTRACT,
            evidence_source=EvidenceSource(
                source_kind=EvidenceSourceKind.PROVIDER_API,
                provider_name=_PROVIDER_NAME,
                uri=repository.html_url,
                fetch_status=FetchStatus.SUCCESS,
            ),
            observed_fact=ObservedFact(
                fields={
                    "repository_url": repository.html_url,
                    "full_name": repository.full_name,
                    "owner": repository.owner.login,
                    "description": repository.description or "",
                    "license": license_value,
                    "topics": ",".join(repository.topics),
                    "homepage": repository.homepage or "",
                    "default_branch": repository.default_branch,
                    "archived": repository.archived,
                    "stars": repository.stargazers_count,
                    "forks": repository.forks_count,
                    "open_issues": repository.open_issues_count,
                    "language": repository.language or "",
                    "latest_push": _format_datetime(repository.pushed_at),
                    "latest_update": _format_datetime(repository.updated_at),
                }
            ),
            polarity=EvidencePolarity.NEUTRAL,
            confidence=1.0,
            collected_at=collected_at,
            raw_reference=repository.url,
        )


def _candidate_id(full_name: str) -> str:
    digest = hashlib.sha256(full_name.encode("utf-8")).hexdigest()[:16]
    return f"github-{digest}"


def _evidence_id(candidate_id: str, suffix: str) -> str:
    digest = hashlib.sha256(f"{candidate_id}:{suffix}".encode("utf-8")).hexdigest()[:16]
    return f"github-evidence-{digest}"


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()
