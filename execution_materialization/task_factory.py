"""Project typed execution specifications into ExecutionTask metadata."""

from __future__ import annotations

import json

from models.execution_materialization import ExecutableTaskSpec


_METADATA_KEYS = (
    "command",
    "working_directory",
    "environment_variables",
    "timeout_seconds",
    "artifact_paths",
)


def project_spec_to_metadata(spec: ExecutableTaskSpec) -> dict[str, str]:
    """Deterministic projection consumed by LocalExecutor.parse_local_invocation."""
    metadata = {
        "command": json.dumps(list(spec.command), separators=(",", ":")),
        "working_directory": spec.working_directory,
        "environment_variables": json.dumps(spec.environment_variables, separators=(",", ":")),
        "artifact_paths": json.dumps(spec.artifact_paths, separators=(",", ":")),
    }
    if spec.timeout_seconds is not None:
        metadata["timeout_seconds"] = str(spec.timeout_seconds)
    return metadata


def merge_metadata(base: dict[str, str], spec: ExecutableTaskSpec) -> dict[str, str]:
    """Merge decomposition provenance with executable metadata projection."""
    merged = dict(base)
    merged.update(project_spec_to_metadata(spec))
    return merged
