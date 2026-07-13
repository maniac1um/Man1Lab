"""Tests for execution graph and task DAG validation."""

from __future__ import annotations

import unittest

from execution.errors import GraphValidationError, TaskDagValidationError, UnsupportedStageError
from execution.validation import validate_execution_graph, validate_task_dag
from models.execution_engine import ExecutionTask, ExecutionTaskStatus, ExecutionTaskType
from models.execution_graph import ExecutionGraph, ExecutionGraphNode, ExecutionGraphStageType
from tests.execution_engine_fixtures import linear_graph


class ExecutionGraphValidationTest(unittest.TestCase):
    def test_valid_linear_graph_passes(self) -> None:
        validate_execution_graph(linear_graph())

    def test_duplicate_node_ids_fail(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-dup",
            created_at=linear_graph().created_at,
            strategy_id="strategy-1",
            nodes=[
                ExecutionGraphNode(
                    node_id="dup",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="A",
                ),
                ExecutionGraphNode(
                    node_id="dup",
                    stage_type=ExecutionGraphStageType.EVALUATION,
                    label="B",
                ),
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_execution_graph(graph)

    def test_unknown_dependency_fails(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-unknown-dep",
            created_at=linear_graph().created_at,
            strategy_id="strategy-1",
            nodes=[
                ExecutionGraphNode(
                    node_id="node-training",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="Training",
                    depends_on=["missing"],
                )
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_execution_graph(graph)

    def test_self_dependency_fails(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-self",
            created_at=linear_graph().created_at,
            strategy_id="strategy-1",
            nodes=[
                ExecutionGraphNode(
                    node_id="node-training",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="Training",
                    depends_on=["node-training"],
                )
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_execution_graph(graph)

    def test_cycle_fails(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-cycle",
            created_at=linear_graph().created_at,
            strategy_id="strategy-1",
            nodes=[
                ExecutionGraphNode(
                    node_id="a",
                    stage_type=ExecutionGraphStageType.TRAINING,
                    label="A",
                    depends_on=["b"],
                ),
                ExecutionGraphNode(
                    node_id="b",
                    stage_type=ExecutionGraphStageType.EVALUATION,
                    label="B",
                    depends_on=["a"],
                ),
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_execution_graph(graph)

    def test_task_dag_duplicate_ids_fail(self) -> None:
        tasks = [
            ExecutionTask(id="task-a", name="A", type=ExecutionTaskType.TRAINING),
            ExecutionTask(id="task-a", name="B", type=ExecutionTaskType.EVALUATION),
        ]
        with self.assertRaises(TaskDagValidationError):
            validate_task_dag(tasks)

    def test_task_dag_cycle_fails(self) -> None:
        tasks = [
            ExecutionTask(
                id="task-a",
                name="A",
                type=ExecutionTaskType.TRAINING,
                dependencies=("task-b",),
            ),
            ExecutionTask(
                id="task-b",
                name="B",
                type=ExecutionTaskType.EVALUATION,
                dependencies=("task-a",),
            ),
        ]
        with self.assertRaises(TaskDagValidationError):
            validate_task_dag(tasks)

    def test_supported_stage_mapping_includes_configuration(self) -> None:
        from execution.validation import task_type_for_stage

        self.assertEqual(
            task_type_for_stage(ExecutionGraphStageType.GENERATE_CONFIG),
            ExecutionTaskType.CONFIGURATION,
        )

    def test_graph_input_not_mutated(self) -> None:
        graph = linear_graph()
        original_nodes = [node.model_copy() for node in graph.nodes]
        validate_execution_graph(graph)
        self.assertEqual(graph.nodes, original_nodes)


if __name__ == "__main__":
    unittest.main()
