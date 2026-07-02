"""GitHub Discovery Provider foundation package."""

from providers.github.auth import GitHubAuth
from providers.github.client import GitHubClient
from providers.github.collection import GitHubCollectionProvider
from providers.github.ranking import GitHubRankingProvider
from providers.github.verification import GitHubVerificationProvider
from providers.github.exceptions import (
    GitHubApiError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubProviderError,
    GitHubRateLimitError,
    GitHubReadmeNotFoundError,
    GitHubTimeoutError,
)
from providers.github.mapper import GitHubMapper
from providers.github.models import (
    GitHubErrorDTO,
    GitHubLicenseDTO,
    GitHubOwnerDTO,
    GitHubReadmeDTO,
    GitHubRepositoryDTO,
    GitHubSearchItemDTO,
    GitHubSearchResultDTO,
)

__all__ = [
    "GitHubApiError",
    "GitHubAuth",
    "GitHubAuthenticationError",
    "GitHubClient",
    "GitHubCollectionProvider",
    "GitHubEvidenceProvider",
    "GitHubVerificationProvider",
    "GitHubErrorDTO",
    "GitHubLicenseDTO",
    "GitHubMapper",
    "GitHubNotFoundError",
    "GitHubOwnerDTO",
    "GitHubProviderError",
    "GitHubRateLimitError",
    "GitHubRankingProvider",
    "GitHubReadmeNotFoundError",
    "GitHubReadmeDTO",
    "GitHubRepositoryDTO",
    "GitHubSearchItemDTO",
    "GitHubSearchResultDTO",
    "GitHubTimeoutError",
]
