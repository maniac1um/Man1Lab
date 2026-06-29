import unittest

from agents.coder_quality import (
    build_framework_binding,
    collect_required_packages,
    extract_python_import_roots,
    reconcile_requirements_content,
    validate_generated_repository,
)


class CoderQualityTest(unittest.TestCase):
    def test_build_framework_binding_pytorch(self) -> None:
        binding = build_framework_binding("PyTorch")

        self.assertEqual(binding["framework"], "PyTorch")
        self.assertIn("torch", binding["required_primary_packages"])
        self.assertIn("caffe", binding["forbidden_import_roots"])

    def test_extract_python_import_roots(self) -> None:
        content = "import torch\nfrom src.dataset import load_data\nimport yaml\n"
        roots = extract_python_import_roots(content)

        self.assertEqual(roots, ["torch", "src", "yaml"])

    def test_reconcile_requirements_adds_missing_packages(self) -> None:
        existing = "numpy\nPyYAML\n"
        required = {"torch", "numpy"}

        merged = reconcile_requirements_content(existing, required)

        self.assertIn("numpy", merged)
        self.assertIn("torch", merged)

    def test_collect_required_packages_includes_framework_and_imports(self) -> None:
        files = {
            "scripts/train.py": "import torch\nimport yaml\n",
            "src/dataset.py": "import numpy\n",
        }

        packages = collect_required_packages(files, "PyTorch")

        self.assertIn("torch", packages)
        self.assertIn("numpy", packages)
        self.assertIn("PyYAML", packages)

    def test_validate_generated_repository_detects_missing_requirement(self) -> None:
        findings = validate_generated_repository(
            workspace_root=__import__("pathlib").Path("."),
            routed_paths={"scripts/train.py", "requirements.txt"},
            python_files={"scripts/train.py": "import torch\n"},
            requirements_content="numpy\n",
            framework_binding=build_framework_binding("PyTorch"),
            interface_registry={},
        )

        codes = {finding["code"] for finding in findings}
        self.assertIn("import_not_in_requirements", codes)

    def test_validate_generated_repository_detects_forbidden_framework(self) -> None:
        findings = validate_generated_repository(
            workspace_root=__import__("pathlib").Path("."),
            routed_paths={"scripts/train.py", "requirements.txt"},
            python_files={"scripts/train.py": "import torch\n"},
            requirements_content="torch\ncaffe\n",
            framework_binding=build_framework_binding("Caffe"),
            interface_registry={},
        )

        codes = {finding["code"] for finding in findings}
        self.assertIn("forbidden_framework_import", codes)


if __name__ == "__main__":
    unittest.main()
