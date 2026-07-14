"""Workspace persistence for immutable execution-evidence projections."""

from __future__ import annotations

from pathlib import Path

from models.execution_evidence import ExecutionEvidenceBundle
from runtime.execution_store.atomic_io import atomic_write_json

EXECUTION_EVIDENCE_DIR = "execution_evidence"
EXECUTION_EVIDENCE_JSON = "execution_evidence.json"


class ExecutionEvidenceArtifactStore:
    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root

    def path(self) -> Path:
        return self._root / EXECUTION_EVIDENCE_DIR / EXECUTION_EVIDENCE_JSON

    def save(self, bundle: ExecutionEvidenceBundle) -> None:
        atomic_write_json(self.path(), bundle.model_dump(mode="json"))

    def load(self) -> ExecutionEvidenceBundle | None:
        path = self.path()
        if not path.is_file():
            return None
        return ExecutionEvidenceBundle.model_validate_json(path.read_text(encoding="utf-8"))
