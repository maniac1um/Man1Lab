"""Tests for execution materialization models and graph compatibility."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime

from models.execution_graph import (
    ExecutionGraph,
    ExecutionGraphNode,
    ExecutionGraphStageType,
)
from models.execution_materialization import (
    ExecutableTaskSpec,
    MaterializationReport,
    MaterializationStatus,
)


class ExecutionMaterializationModelsTest(unittest.TestCase):
    def test_legacy_graph_round_trip_without_materialization_fields(self) -> None:
        payload = {
            "graph_id": "graph-legacy",
            "created_at": "2026-01-01T00:00:00+00:00",
            "strategy_id": "strategy-legacy",
            "nodes": [
                {
                    "node_id": "node-1",
                    "stage_type": "prepare_environment",
                    "label": "Prepare Environment",
                }
            ],
            "schema_version": "1.0",
        }
        graph = ExecutionGraph.model_validate(payload)
        dumped = json.loads(graph.model_dump_json())
        self.assertIsNone(dumped["materialization_id"])
        self.assertIsNone(graph.nodes[0].execution_spec)

    def test_graph_with_execution_spec_round_trip(self) -> None:
        spec = ExecutableTaskSpec(
            command=("python", "train.py"),
            working_directory="repositories/demo",
        )
        graph = ExecutionGraph(
            graph_id="graph-mat",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            strategy_id="strategy-1",
            nodes=[
                ExecutionGraphNode(
                    node_id="node-training",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="Training",
                    execution_spec=spec,
                )
            ],
            materialization_id="mat-abc",
            materialization_schema_version="1.0",
        )
        restored = ExecutionGraph.model_validate_json(graph.model_dump_json())
        self.assertEqual(restored.materialization_id, "mat-abc")
        self.assertIsNotNone(restored.nodes[0].execution_spec)
        self.assertEqual(restored.nodes[0].execution_spec.command, ("python", "train.py"))

    def test_executable_spec_rejects_shell_operators(self) -> None:
        with self.assertRaises(ValueError):
            ExecutableTaskSpec(
                command=("python", "-c", "print('a'; rm -rf /)"),
                working_directory="repo",
            )

    def test_executable_spec_rejects_absolute_working_directory(self) -> None:
        with self.assertRaises(ValueError):
            ExecutableTaskSpec(
                command=("python", "train.py"),
                working_directory="C:/outside/repository",
            )

    def test_executable_spec_rejects_traversing_artifact_path(self) -> None:
        with self.assertRaises(ValueError):
            ExecutableTaskSpec(
                command=("python", "train.py"),
                working_directory="repositories/demo",
                artifact_paths={"training_output": "../outside.pt"},
            )

    def test_ready_report_requires_all_nodes_ready(self) -> None:
        from models.execution_materialization import NodeMaterializationResult

        with self.assertRaises(ValueError):
            MaterializationReport(
                status=MaterializationStatus.READY,
                node_results=(
                    NodeMaterializationResult(
                        node_id="node-1",
                        stage_type="training",
                        status=MaterializationStatus.BLOCKED,
                    ),
                ),
                errors=(),
            )


if __name__ == "__main__":
    unittest.main()
