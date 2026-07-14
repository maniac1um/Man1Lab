"""AST boundary verification for Decision Quality Phase 2 modules."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class DecisionQualityPhase2BoundaryTest(unittest.TestCase):
    _RUNTIME_FORBIDDEN = ("discovery", "execution_planning", "workflow", "providers", "agents")

    def test_runtime_session_decision_artifacts_uses_importlib(self) -> None:
        path = REPO_ROOT / "src" / "runtime" / "session" / "decision_artifacts.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in self._RUNTIME_FORBIDDEN:
                    offenders.append(node.module)
        self.assertEqual(offenders, [])

    def test_models_do_not_import_discovery_or_planning(self) -> None:
        model_paths = [
            REPO_ROOT / "src" / "models" / "decision_trace.py",
            REPO_ROOT / "src" / "models" / "execution_graph.py",
            REPO_ROOT / "src" / "models" / "explainable_confidence.py",
            REPO_ROOT / "src" / "models" / "research_asset.py",
        ]
        forbidden = {"discovery", "execution_planning", "providers", "services"}
        for path in model_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                if module and module.split(".", 1)[0] in forbidden:
                    self.fail(f"{path.name} must not import {module}")


if __name__ == "__main__":
    unittest.main()
