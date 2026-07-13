"""Snapshot file metadata envelope for multi-file consistency."""

from __future__ import annotations

from typing import Any

from execution.errors import (
    CorruptSnapshotError,
    IncompatibleSchemaError,
    MixedRevisionSnapshotError,
)
from models.execution_engine import SCHEMA_VERSION

_SUPPORTED_SCHEMA_MAJOR = 1


def wrap_snapshot_payload(*, run_id: str, revision: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "revision": revision,
        "payload": payload,
    }


def unwrap_snapshot_payload(
    envelope: dict[str, Any],
    *,
    file_label: str,
    expected_run_id: str | None = None,
    expected_revision: int | None = None,
) -> tuple[str, int, dict[str, Any]]:
    version = str(envelope.get("schema_version", ""))
    if not version:
        raise IncompatibleSchemaError(f"missing schema_version in {file_label}")
    try:
        major = int(version.split(".", 1)[0])
    except ValueError as exc:
        raise IncompatibleSchemaError(f"invalid schema_version in {file_label}: {version}") from exc
    if major > _SUPPORTED_SCHEMA_MAJOR:
        raise IncompatibleSchemaError(f"unsupported schema_version in {file_label}: {version}")

    run_id = envelope.get("run_id")
    revision = envelope.get("revision")
    payload = envelope.get("payload")
    if not isinstance(run_id, str) or not run_id:
        raise CorruptSnapshotError(f"missing run_id in {file_label}")
    if not isinstance(revision, int) or revision < 0:
        raise CorruptSnapshotError(f"invalid revision in {file_label}")
    if not isinstance(payload, dict):
        raise CorruptSnapshotError(f"missing payload object in {file_label}")
    if expected_run_id is not None and run_id != expected_run_id:
        raise MixedRevisionSnapshotError(
            f"{file_label} run_id {run_id!r} does not match expected {expected_run_id!r}"
        )
    if expected_revision is not None and revision != expected_revision:
        raise MixedRevisionSnapshotError(
            f"{file_label} revision {revision} does not match expected {expected_revision}"
        )
    return run_id, revision, payload


def validate_snapshot_set(
  *,
  run_id: str,
  revision: int,
  file_revisions: dict[str, tuple[str, int]],
) -> None:
    """Ensure every snapshot file reports the same run_id and revision."""
    for label, (file_run_id, file_revision) in file_revisions.items():
        if file_run_id != run_id:
            raise MixedRevisionSnapshotError(
                f"{label} run_id {file_run_id!r} disagrees with envelope run_id {run_id!r}"
            )
        if file_revision != revision:
            raise MixedRevisionSnapshotError(
                f"{label} revision {file_revision} disagrees with envelope revision {revision}"
            )
