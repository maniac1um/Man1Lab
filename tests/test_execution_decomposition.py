"""Tests for deterministic task decomposition."""

from __future__ import annotations

import unittest

from execution.decomposition import decompose_execution_graph, task_id_for_node
from execution.validation import task_type_for_stage
from models.execution_engine import ExecutionTaskStatus, ExecutionTaskType, TraceEventType
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from tests.execution_engine_fixtures import full_stage_graph, linear_graph


class ExecutionDecompositionTest(unittest.TestCase):
    def test_all_stage_mappings(self) -> None:
        mappings = {
            ExecutionGraphStageType.CLONE_REPOSITORY: ExecutionTaskType.REPOSITORY,
            ExecutionGraphStageType.PREPARE_ENVIRONMENT: ExecutionTaskType.ENVIRONMENT,
            ExecutionGraphStageType.DOWNLOAD_DATASET: ExecutionTaskType.DATASET,
            ExecutionGraphStageType.DOWNLOAD_CHECKPOINTS: ExecutionTaskType.CHECKPOINT,
            ExecutionGraphStageType.GENERATE_CONFIG: ExecutionTaskType.CONFIGURATION,
            ExecutionGraphStageType.TRAINING: ExecutionTaskType.TRAINING,
            ExecutionGraphStageType.EVALUATION: ExecutionTaskType.EVALUATION,
            ExecutionGraphStageType.COMPARISON: ExecutionTaskType.REPORT,
        }
        for stage, expected in mappings.items():
            self.assertEqual(task_type_for_stage(stage), expected)

    def test_deterministic_task_ids(self) -> None:
        graph = linear_graph()
        first = decompose_execution_graph(graph, run_id="run-1")
        second = decompose_execution_graph(graph, run_id="run-1")
        self.assertEqual([task.id for task in first.tasks], [task.id for task in second.tasks])
        self.assertEqual(first.tasks[0].id, task_id_for_node("node-prepare-environment"))

    def test_dependencies_preserved(self) -> None:
        result = decompose_execution_graph(linear_graph(), run_id="run-1")
        by_id = {task.id: task for task in result.tasks}
        training = by_id[task_id_for_node("node-training")]
        self.assertEqual(
            training.dependencies,
            (task_id_for_node("node-prepare-environment"),),
        )

    def test_initial_status_pending_and_task_created_events(self) -> None:
        result = decompose_execution_graph(linear_graph(), run_id="run-1")
        self.assertTrue(all(task.status == ExecutionTaskStatus.PENDING for task in result.tasks))
        self.assertEqual(len(result.events), len(result.tasks))
        self.assertTrue(all(event.event_type == TraceEventType.TASK_CREATED for event in result.events))

    def test_provenance_metadata(self) -> None:
        graph = linear_graph()
        result = decompose_execution_graph(graph, run_id="run-1")
        task = result.tasks[0]
        self.assertEqual(task.metadata["source_graph_id"], graph.graph_id)
        self.assertEqual(task.metadata["source_node_id"], "node-prepare-environment")

    def test_graph_unchanged_after_decomposition(self) -> None:
        graph = linear_graph()
        before = graph.model_dump()
        decompose_execution_graph(graph, run_id="run-1")
        self.assertEqual(graph.model_dump(), before)

    def test_full_graph_decomposition_count(self) -> None:
        result = decompose_execution_graph(full_stage_graph(), run_id="run-full")
        self.assertEqual(len(result.tasks), 8)
        self.assertEqual(result.source_graph_id, "graph-full")


if __name__ == "__main__":
    unittest.main()
