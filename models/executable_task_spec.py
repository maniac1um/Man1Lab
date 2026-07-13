"""Backend-neutral executable task specification shared by graph and materialization."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"

_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)


class ExecutableTaskSpec(BaseModel):
    """Backend-neutral concrete invocation specification."""

    model_config = ConfigDict(frozen=True)

    backend_kind: str = "local"
    command: tuple[str, ...]
    working_directory: str
    environment_variables: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    template_id: str = ""
    template_version: str = ""
    source_binding_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_asset_ids: tuple[str, ...] = Field(default_factory=tuple)
    provenance: str = ""
    schema_version: str = SCHEMA_VERSION

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("command must be a non-empty argument vector")
        if not all(isinstance(part, str) and part for part in value):
            raise ValueError("command must contain only non-empty strings")
        for part in value:
            if any(op in part for op in ("|", "&", ";", "`", "$(")):
                raise ValueError("command must not contain shell operators")
        return value

    @field_validator("working_directory")
    @classmethod
    def _validate_working_directory(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip()
        if not normalized:
            raise ValueError("working_directory must be non-empty")
        if _is_unsafe_workspace_path(normalized):
            raise ValueError("working_directory must be workspace-relative and must not traverse")
        return normalized

    @field_validator("artifact_paths")
    @classmethod
    def _validate_artifact_paths(cls, value: dict[str, str]) -> dict[str, str]:
        for logical_name, path in value.items():
            normalized = path.replace("\\", "/").strip()
            if not logical_name or not normalized:
                raise ValueError("artifact_paths must contain non-empty names and paths")
            if _is_unsafe_workspace_path(normalized):
                raise ValueError("artifact paths must be relative and must not traverse")
        return value

    @field_validator("environment_variables")
    @classmethod
    def _validate_environment(cls, value: dict[str, str]) -> dict[str, str]:
        for key, env_value in value.items():
            if _SECRET_KEY_PATTERN.search(key.replace("-", "_")):
                raise ValueError(f"secret-like environment key not allowed: {key}")
            if _SECRET_KEY_PATTERN.search(env_value):
                raise ValueError("environment values must not contain secret-like content")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("timeout_seconds must be positive when set")
        return value


def _is_unsafe_workspace_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return posix.is_absolute() or windows.is_absolute() or ".." in posix.parts
