import unittest

from agents.analysis_context import build_coder_shared_context
from agents.coder import Coder
from models.routing import RepositoryTarget, TaskRoutingTable
from models.task import TaskModel, TaskStep
from routing.task_router import TaskRouter
from tests.fixtures import sample_reproduction_analysis


def _sample_analysis():
    return sample_reproduction_analysis()


class CoderContractTest(unittest.TestCase):
    def test_build_repository_contract_includes_dataset_provider(self) -> None:
        task = TaskModel(
            paper_title="Contract Test Paper",
            steps=[
                TaskStep(id="task_3", name="Dataset preparation", description="Load data."),
                TaskStep(id="task_5", name="Training", description="Train."),
            ],
        )
        routing_table = TaskRouter().route_task(task)
        shared_context = build_coder_shared_context(
            _sample_analysis(),
            task,
            routing_table,
        )
        contract = Coder._build_repository_contract(routing_table, shared_context)

        self.assertIn("framework_binding", contract)
        module_roles = contract["module_roles"]
        self.assertIn("src/dataset.py", module_roles)
        self.assertEqual(module_roles["src/dataset.py"]["role"], "Dataset Provider")

    def test_build_repository_contract_omits_model_builder_when_not_routed(self) -> None:
        task = TaskModel(
            paper_title="Contract Test Paper",
            steps=[TaskStep(id="task_3", name="Dataset preparation", description="Load.")],
        )
        routing_table = TaskRouter().route_task(task)
        shared_context = build_coder_shared_context(
            _sample_analysis(),
            task,
            routing_table,
        )
        contract = Coder._build_repository_contract(routing_table, shared_context)

        self.assertNotIn("src/model.py", contract["module_roles"])

    def test_extract_python_symbols(self) -> None:
        content = '''"""Module."""

class Model:
    pass


def load_data(config: dict):
    return config
'''
        symbols = Coder._extract_python_symbols(content)

        self.assertEqual(symbols["public_symbols"], ["load_data", "Model"])
        self.assertEqual(symbols["symbol_kinds"]["load_data"], "function")
        self.assertEqual(symbols["symbol_kinds"]["Model"], "class")

    def test_extract_yaml_top_level_keys(self) -> None:
        content = """dataset: imagenet
batch_size: 32
training:
  epochs: 10
"""
        keys = Coder._extract_yaml_top_level_keys(content)

        self.assertEqual(keys, ["dataset", "batch_size", "training"])

    def test_record_interface_registry_for_source_and_config(self) -> None:
        registry: dict[str, object] = {}
        Coder._record_interface_registry(
            registry,
            "src/dataset.py",
            "def load_dataloaders(config):\n    return None, None\n",
            "source",
        )
        Coder._record_interface_registry(
            registry,
            "configs/train.yaml",
            "dataset: benchmark\nbatch_size: 32\n",
            "config",
        )

        self.assertEqual(
            registry["src/dataset.py"],
            {
                "public_symbols": ["load_dataloaders"],
                "symbol_kinds": {"load_dataloaders": "function"},
                "import_roots": [],
            },
        )
        self.assertEqual(
            registry["configs/train.yaml"],
            {"top_level_keys": ["dataset", "batch_size"]},
        )

    def test_contract_slice_for_training_script(self) -> None:
        targets = [
            RepositoryTarget(
                relative_path="scripts/train.py",
                file_category="script",
                task_id="task_5",
            )
        ]
        routing_table = TaskRoutingTable(targets=targets)
        shared_context = build_coder_shared_context(
            _sample_analysis(),
            TaskModel(paper_title="Contract Test Paper", steps=[]),
            routing_table,
        )
        contract = Coder._build_repository_contract(routing_table, shared_context)
        target = targets[0]
        slice_data = Coder._contract_slice_for_target(contract, target)

        self.assertIn("execution_expectation", slice_data)
        self.assertEqual(
            slice_data["execution_expectation"]["runner_invocation"],
            "python scripts/train.py",
        )


if __name__ == "__main__":
    unittest.main()
