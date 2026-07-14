"""Immutable workspace persistence for materialization artifacts."""

from __future__ import annotations

from pathlib import Path

from models.execution_graph import ExecutionGraph
from models.execution_materialization import ExecutionMaterialization, MaterializationReport
from runtime.execution_store.atomic_io import atomic_write_json, load_json

MATERIALIZATION_DIR = "materialization"
MATERIALIZATION_JSON = "execution_materialization.json"
MATERIALIZED_GRAPH_JSON = "materialized_execution_graph.json"
MATERIALIZATION_REPORT_JSON = "materialization_report.json"


class MaterializationArtifactStore:
    """Persist materialization outputs under workspace/materialization/."""

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root

    @property
    def root(self) -> Path:
        return self._root

    def materialization_dir(self) -> Path:
        return self._root / MATERIALIZATION_DIR

    def materialization_json_path(self) -> Path:
        return self.materialization_dir() / MATERIALIZATION_JSON

    def materialized_graph_json_path(self) -> Path:
        return self.materialization_dir() / MATERIALIZED_GRAPH_JSON

    def materialization_report_json_path(self) -> Path:
        return self.materialization_dir() / MATERIALIZATION_REPORT_JSON

    def has_materialization(self) -> bool:
        return self.materialization_json_path().is_file()

    def save(self, materialization: ExecutionMaterialization) -> None:
        envelope = {
            "materialization_id": materialization.materialization_id,
            "strategy_id": materialization.strategy_id,
            "graph_id": materialization.graph_id,
            "discovery_id": materialization.discovery_id,
            "analysis_id": materialization.analysis_id,
            "evidence_bundle_id": materialization.evidence_bundle_id,
            "backend_kind": materialization.backend_kind,
            "created_at": materialization.created_at.isoformat(),
            "schema_version": materialization.schema_version,
        }
        atomic_write_json(self.materialization_json_path(), envelope)
        graph: ExecutionGraph = materialization.materialized_graph
        atomic_write_json(
            self.materialized_graph_json_path(),
            graph.model_dump(mode="json"),
        )
        atomic_write_json(
            self.materialization_report_json_path(),
            materialization.report.model_dump(mode="json"),
        )

    def load_materialization_envelope(self) -> dict | None:
        path = self.materialization_json_path()
        if not path.is_file():
            return None
        return load_json(path)

    def load_materialized_graph(self) -> ExecutionGraph | None:
        path = self.materialized_graph_json_path()
        if not path.is_file():
            return None
        return ExecutionGraph.model_validate_json(path.read_text(encoding="utf-8"))

    def load_materialization_report(self) -> MaterializationReport | None:
        path = self.materialization_report_json_path()
        if not path.is_file():
            return None
        return MaterializationReport.model_validate_json(path.read_text(encoding="utf-8"))
