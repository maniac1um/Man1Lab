"""Persistence tests for materialization workspace artifacts."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from models.execution_materialization import ExecutionMaterialization, MaterializationReport, MaterializationStatus
from runtime.session.materialization_artifacts import MaterializationArtifactStore
from tests.test_execution_materialization_fixtures import materializable_graph


class MaterializationArtifactStoreTest(unittest.TestCase):
    def test_round_trip_persistence(self) -> None:
        graph = materializable_graph()
        materialization = ExecutionMaterialization(
            materialization_id="mat-persist",
            strategy_id="strategy-1",
            graph_id=graph.graph_id,
            materialized_graph=graph,
            report=MaterializationReport(status=MaterializationStatus.BLOCKED),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = MaterializationArtifactStore(root)
            store.save(materialization)
            self.assertTrue(store.has_materialization())
            self.assertEqual(store.load_materialization_envelope()["materialization_id"], "mat-persist")
            self.assertEqual(store.load_materialized_graph().graph_id, graph.graph_id)
            self.assertEqual(store.load_materialization_report().status, MaterializationStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
