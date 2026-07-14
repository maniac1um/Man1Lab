"""GitHub API token resolution and request header construction."""

from __future__ import annotations

import os
from typing import Mapping

_DEFAULT_ENV_VAR = "GITHUB_TOKEN"


class GitHubAuth:
    """Resolve GitHub credentials and build Authorization headers.

    Token resolution order:
    1. Explicit injected token
    2. Environment variable (default: ``GITHUB_TOKEN``)
    3. Unauthenticated mode when no token is available
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        env_var: str = _DEFAULT_ENV_VAR,
    ) -> None:
        self._injected_token = token
        self._env_var = env_var

    def resolve_token(self) -> str | None:
        """Return the configured token, or ``None`` for unauthenticated mode."""
        if self._injected_token is not None:
            return self._injected_token
        return os.environ.get(self._env_var) or None

    def authorization_header(self) -> dict[str, str]:
        """Build the Authorization header when a token is available."""
        token = self.resolve_token()
        if token is None:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def request_headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """Merge default GitHub headers with optional caller headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        headers.update(self.authorization_header())
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def mask_token(token: str | None) -> str:
        """Return a safe token representation for logs and diagnostics."""
        if token is None or token == "":
            return "<none>"
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    def masked_token(self) -> str:
        """Return the resolved token in masked form."""
        return self.mask_token(self.resolve_token())

    def __repr__(self) -> str:
        return f"GitHubAuth(token={self.masked_token()!r})"
