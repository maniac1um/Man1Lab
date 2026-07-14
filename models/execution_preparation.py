"""Canonical request contract shared by Materialization and preparation adapters."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PreparationOperation(str, Enum):
    REPOSITORY = "repository"
    DATASET = "dataset"
    CHECKPOINT = "checkpoint"
    CONFIGURATION = "configuration"


class PreparationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: PreparationOperation
    source_kind: str
    source_uri: str = ""
    source_path: str = ""
    target_path: str
    receipt_path: str
    revision: str = ""
    checksum_sha256: str = ""
    archive_format: str = ""
    required_paths: tuple[str, ...] = Field(default_factory=tuple)
    configuration_format: str = "json"
    configuration_values: dict[str, str | int | float | bool] = Field(default_factory=dict)
    schema_version: str = "1.0"

    @field_validator("target_path", "receipt_path", "source_path")
    @classmethod
    def _safe_paths(cls, value: str) -> str:
        if not value:
            return value
        normalized = value.replace("\\", "/").strip().lstrip("/")
        parts = tuple(part for part in normalized.split("/") if part and part != ".")
        if not parts or ".." in parts or ":" in parts[0]:
            raise ValueError("preparation paths must be workspace-relative")
        return "/".join(parts)

    @field_validator("source_uri")
    @classmethod
    def _safe_uri(cls, value: str) -> str:
        if "://" in value:
            authority = value.split("://", 1)[1].split("/", 1)[0]
            if "@" in authority:
                raise ValueError("source_uri must not contain embedded credentials")
        return value
