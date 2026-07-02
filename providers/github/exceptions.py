"""GitHub Discovery Provider — provider-scoped exceptions.

These types are internal to ``providers/github`` and must be translated to port
outcomes before crossing the Discovery provider boundary.
"""

from __future__ import annotations


class GitHubProviderError(Exception):
    """Base exception for GitHub provider internals."""


class GitHubAuthenticationError(GitHubProviderError):
    """Raised when GitHub rejects or cannot use the configured credentials."""


class GitHubRateLimitError(GitHubProviderError):
    """Raised when GitHub rate limits are exceeded."""


class GitHubNotFoundError(GitHubProviderError):
    """Raised when a requested GitHub resource does not exist."""


class GitHubReadmeNotFoundError(GitHubNotFoundError):
    """Raised when a repository exists but has no README."""


class GitHubApiError(GitHubProviderError):
    """Raised for non-specific GitHub API failures."""


class GitHubTimeoutError(GitHubProviderError):
    """Raised when a GitHub request times out."""
