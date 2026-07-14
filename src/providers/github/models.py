"""GitHub REST response DTOs.

These models mirror GitHub API payloads only. They are not canonical Discovery
models and must not leak outside ``providers/github``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GitHubOwnerDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    login: str = Field(description="GitHub account login.")
    id: int = Field(description="Numeric GitHub user or organization ID.")
    node_id: str = Field(default="", description="Global node ID.")
    avatar_url: str = Field(default="", description="Avatar image URL.")
    html_url: str = Field(default="", description="Profile or organization page URL.")
    type: str = Field(default="User", description="Account type: User or Organization.")


class GitHubLicenseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(description="License key returned by GitHub.")
    name: str = Field(default="", description="Human-readable license name.")
    spdx_id: str | None = Field(default=None, description="SPDX identifier when available.")
    url: str | None = Field(default=None, description="License reference URL.")
    node_id: str | None = Field(default=None, description="Global node ID.")


class GitHubRepositoryDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int = Field(description="Numeric repository ID.")
    node_id: str = Field(default="", description="Global node ID.")
    name: str = Field(description="Repository short name.")
    full_name: str = Field(description="Owner-qualified repository name.")
    private: bool = Field(default=False, description="Whether the repository is private.")
    html_url: str = Field(default="", description="Canonical repository web URL.")
    description: str | None = Field(default=None, description="Repository description.")
    fork: bool = Field(default=False, description="Whether the repository is a fork.")
    url: str = Field(default="", description="API URL for the repository.")
    created_at: datetime | None = Field(default=None, description="Repository creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Last metadata update timestamp.")
    pushed_at: datetime | None = Field(default=None, description="Last push timestamp.")
    homepage: str | None = Field(default=None, description="Configured homepage URL.")
    size: int = Field(default=0, description="Repository size in kilobytes.")
    stargazers_count: int = Field(default=0, description="Star count.")
    watchers_count: int = Field(default=0, description="Watcher count.")
    language: str | None = Field(default=None, description="Primary language.")
    forks_count: int = Field(default=0, description="Fork count.")
    open_issues_count: int = Field(default=0, description="Open issue count.")
    archived: bool = Field(default=False, description="Whether the repository is archived.")
    disabled: bool = Field(default=False, description="Whether the repository is disabled.")
    license: GitHubLicenseDTO | None = Field(default=None, description="Detected license metadata.")
    topics: list[str] = Field(default_factory=list, description="Repository topic tags.")
    visibility: str | None = Field(default=None, description="Repository visibility label.")
    default_branch: str = Field(default="main", description="Default branch name.")
    owner: GitHubOwnerDTO = Field(description="Repository owner account.")


class GitHubSearchItemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int = Field(description="Numeric repository ID.")
    node_id: str = Field(default="", description="Global node ID.")
    name: str = Field(description="Repository short name.")
    full_name: str = Field(description="Owner-qualified repository name.")
    private: bool = Field(default=False, description="Whether the repository is private.")
    html_url: str = Field(default="", description="Canonical repository web URL.")
    description: str | None = Field(default=None, description="Repository description.")
    fork: bool = Field(default=False, description="Whether the repository is a fork.")
    url: str = Field(default="", description="API URL for the repository.")
    stargazers_count: int = Field(default=0, description="Star count.")
    language: str | None = Field(default=None, description="Primary language.")
    archived: bool = Field(default=False, description="Whether the repository is archived.")
    owner: GitHubOwnerDTO = Field(description="Repository owner account.")


class GitHubSearchResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_count: int = Field(default=0, description="Total repositories matching the query.")
    incomplete_results: bool = Field(
        default=False,
        description="Whether GitHub returned a partial result set.",
    )
    items: list[GitHubSearchItemDTO] = Field(
        default_factory=list,
        description="Repositories returned for the current page.",
    )


class GitHubReadmeDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str = Field(default="file", description="Git object type.")
    encoding: str = Field(default="base64", description="Content encoding.")
    size: int = Field(default=0, description="Encoded content size in bytes.")
    name: str = Field(default="README.md", description="File name.")
    path: str = Field(default="README.md", description="Repository-relative path.")
    content: str = Field(default="", description="Encoded README content.")
    decoded_text: str = Field(
        default="",
        description="UTF-8 decoded README text when encoding is base64.",
    )
    sha: str = Field(default="", description="Git blob SHA.")
    url: str = Field(default="", description="API URL for the README object.")
    html_url: str | None = Field(default=None, description="HTML URL for the README.")
    git_url: str | None = Field(default=None, description="Git API URL for the README.")
    download_url: str | None = Field(default=None, description="Raw download URL.")


class GitHubErrorDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: str = Field(description="GitHub error message.")
    documentation_url: str | None = Field(
        default=None,
        description="Documentation URL for the error.",
    )
    status: int | None = Field(default=None, description="HTTP status when available.")
