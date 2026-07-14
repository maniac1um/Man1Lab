"""Canonical typed evidence used to materialize preparation tasks."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"


class EvidenceAvailability(str, Enum):
    PRESENT = "present"
    WILL_BE_PRODUCED = "will_be_produced"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


class PreparationSourceKind(str, Enum):
    WORKSPACE = "workspace"
    GIT = "git"
    HTTPS = "https"
    REPOSITORY = "repository"
    DETERMINISTIC_RENDER = "deterministic_render"


class ExecutionEvidenceIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    candidate_id: str | None = None
    field: str | None = None


class RepositoryExecutionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    source_kind: PreparationSourceKind
    source_uri: str = ""
    revision: str = ""
    target_path: str
    entry_script: str = ""
    eval_script: str = ""
    comparison_script: str = ""
    requirements_file: str = ""
    config_path: str = ""
    output_path: str = ""
    manifest_paths: tuple[str, ...] = Field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    auth_reference: str = ""

    @field_validator("target_path", "entry_script", "eval_script", "comparison_script", "requirements_file", "config_path", "output_path")
    @classmethod
    def _safe_paths(cls, value: str) -> str:
        return _normalize_relative(value) if value else value

    @field_validator("source_uri")
    @classmethod
    def _safe_source_uri(cls, value: str) -> str:
        return _validate_non_secret_uri(value)


class DatasetExecutionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    source_kind: PreparationSourceKind
    source_uri: str = ""
    revision: str = ""
    target_path: str
    checksum_sha256: str = ""
    archive_format: str = ""
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    auth_reference: str = ""

    @field_validator("target_path")
    @classmethod
    def _safe_target(cls, value: str) -> str:
        return _normalize_relative(value)

    @field_validator("source_uri")
    @classmethod
    def _safe_source_uri(cls, value: str) -> str:
        return _validate_non_secret_uri(value)


class CheckpointExecutionEvidence(DatasetExecutionEvidence):
    format: str = ""


class ConfigurationMode(str, Enum):
    EXISTING_FILE = "existing_file"
    COPY_TEMPLATE = "copy_template"
    DETERMINISTIC_RENDER = "deterministic_render"


class ConfigurationExecutionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    mode: ConfigurationMode
    source_path: str = ""
    target_path: str
    format: str = "json"
    values: dict[str, str | int | float | bool] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("source_path", "target_path")
    @classmethod
    def _safe_paths(cls, value: str) -> str:
        return _normalize_relative(value) if value else value

    @field_validator("values")
    @classmethod
    def _no_secret_values(cls, value: dict[str, str | int | float | bool]):
        for key in value:
            if re.search(r"password|secret|token|api[_-]?key|credential", key, re.IGNORECASE):
                raise ValueError("configuration evidence must not contain secret values")
        return value


class ExecutionEvidenceBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    bundle_id: str
    discovery_id: str
    analysis_content_hash: str
    created_at: datetime
    repositories: tuple[RepositoryExecutionEvidence, ...] = Field(default_factory=tuple)
    datasets: tuple[DatasetExecutionEvidence, ...] = Field(default_factory=tuple)
    checkpoints: tuple[CheckpointExecutionEvidence, ...] = Field(default_factory=tuple)
    configurations: tuple[ConfigurationExecutionEvidence, ...] = Field(default_factory=tuple)
    issues: tuple[ExecutionEvidenceIssue, ...] = Field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION


def _normalize_relative(value: str) -> str:
    normalized = value.replace("\\", "/").strip().lstrip("/")
    parts = tuple(part for part in normalized.split("/") if part and part != ".")
    if not parts or ".." in parts or (parts and ":" in parts[0]):
        raise ValueError("execution evidence paths must be safe workspace-relative paths")
    return "/".join(parts)


def _validate_non_secret_uri(value: str) -> str:
    if "://" in value:
        authority = value.split("://", 1)[1].split("/", 1)[0]
        if "@" in authority:
            raise ValueError("source_uri must not contain embedded credentials")
    return value


__all__ = [
    "CheckpointExecutionEvidence",
    "ConfigurationExecutionEvidence",
    "ConfigurationMode",
    "DatasetExecutionEvidence",
    "EvidenceAvailability",
    "ExecutionEvidenceBundle",
    "ExecutionEvidenceIssue",
    "PreparationSourceKind",
    "RepositoryExecutionEvidence",
    "SCHEMA_VERSION",
]
