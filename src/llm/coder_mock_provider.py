import json
import re

from llm.provider import LLMMessage, LLMProvider

MOCK_FILE_CONTENT: dict[str, str] = {
    "requirements.txt": "torch>=2.0.0\nnumpy>=1.24.0\nPyYAML>=6.0\n",
    "src/dataset.py": '''"""Dataset module."""


def load_dataloaders(config: dict):
    """Return train and validation dataloaders."""
    return None, None
''',
    "configs/dataset.yaml": "dataset: benchmark\ndata_root: data/\n",
    "src/model.py": '''"""Model module."""


class Model:
    """Model placeholder."""

    pass


def build_model(config: dict):
    """Build a model from configuration."""
    return Model()
''',
    "configs/train.yaml": (
        "dataset: benchmark\n"
        "batch_size: 32\n"
        "learning_rate: 0.001\n"
        "momentum: 0.9\n"
        "weight_decay: 0.0001\n"
        "num_workers: 4\n"
        "epochs: 1\n"
    ),
}

_TARGET_FILE_PREFIX = "Target file: "
_REGISTRY_HEADER = "Interface registry (commitments from files already generated):"


class CoderMockLLMProvider(LLMProvider):
    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        target_path = self._extract_target_path(messages)
        if target_path == "scripts/train.py":
            return self._build_train_script(messages)
        if target_path == "scripts/evaluate.py":
            return self._build_evaluate_script(messages)
        return MOCK_FILE_CONTENT.get(target_path, f"# Generated: {target_path}\n")

    def _build_train_script(self, messages: list[LLMMessage]) -> str:
        registry = self._extract_interface_registry(messages)
        framework = self._extract_framework(messages)
        imports = ["from pathlib import Path", "", "import yaml", ""]
        if "pytorch" in framework:
            imports = ["import torch", ""] + imports
        elif "caffe" in framework:
            imports = ["import caffe", ""] + imports
        body = [
            "def main() -> None:",
            '    config_path = Path("configs/train.yaml")',
            '    with config_path.open(encoding="utf-8") as handle:',
            "        config = yaml.safe_load(handle)",
        ]
        if "configs/train.yaml" in registry:
            for key in registry["configs/train.yaml"].get("top_level_keys", []):
                body.append(f'    _ = config["{key}"]')
        else:
            body.extend(
                [
                    '    _ = config.get("dataset", "benchmark")',
                    '    _ = config.get("batch_size", 32)',
                ]
            )
        if "src/dataset.py" in registry:
            symbol = registry["src/dataset.py"]["public_symbols"][0]
            imports.append(f"from src.dataset import {symbol}")
            imports.append("")
            body.append(f"    train_loader, val_loader = {symbol}(config)")
        if "src/model.py" in registry:
            symbol = registry["src/model.py"]["public_symbols"][0]
            imports.append(f"from src.model import {symbol}")
            imports.append("")
            body.append(f"    model = {symbol}(config)")
        if "src/model.py" in registry and "src/dataset.py" in registry:
            body.append('    print("Training complete.", model, train_loader, val_loader)')
        elif "src/model.py" in registry:
            body.append('    print("Training complete.", model)')
        elif "src/dataset.py" in registry:
            body.append('    print("Training complete.", train_loader, val_loader)')
        else:
            body.append('    print("Training complete.")')
        lines = ['"""Training script."""', ""] + imports + body + ["", "", 'if __name__ == "__main__":', "    main()", ""]
        return "\n".join(lines)

    def _build_evaluate_script(self, messages: list[LLMMessage]) -> str:
        registry = self._extract_interface_registry(messages)
        framework = self._extract_framework(messages)
        lines = ['"""Evaluation script."""', ""]
        if "pytorch" in framework:
            lines.extend(["import torch", ""])
        elif "caffe" in framework:
            lines.extend(["import caffe", ""])
        if "src/dataset.py" in registry:
            symbol = registry["src/dataset.py"]["public_symbols"][0]
            lines.extend(
                [
                    f"from src.dataset import {symbol}",
                    "",
                    "def main() -> None:",
                    '    config = {"dataset": "benchmark", "batch_size": 32}',
                    f"    {symbol}(config)",
                    '    print("Evaluation complete.")',
                    "",
                    'if __name__ == "__main__":',
                    "    main()",
                    "",
                ]
            )
            return "\n".join(lines)
        return (
            '"""Evaluation script."""\n\n\n'
            "def main() -> None:\n"
            '    print("Evaluation complete.")\n\n\n'
            "if __name__ == \"__main__\":\n"
            "    main()\n"
        )

    @staticmethod
    def _extract_target_path(messages: list[LLMMessage]) -> str:
        for message in reversed(messages):
            if message.role != "user":
                continue
            for line in message.content.splitlines():
                if line.startswith(_TARGET_FILE_PREFIX):
                    return line.removeprefix(_TARGET_FILE_PREFIX).strip()
        return "unknown"

    @staticmethod
    def _extract_interface_registry(messages: list[LLMMessage]) -> dict[str, object]:
        for message in reversed(messages):
            if message.role != "user":
                continue
            content = message.content
            start = content.find(_REGISTRY_HEADER)
            if start == -1:
                continue
            json_start = content.find("{", start)
            if json_start == -1:
                if "No interfaces recorded yet." in content[start:]:
                    return {}
                continue
            depth = 0
            for index in range(json_start, len(content)):
                char = content[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(content[json_start : index + 1])
                        except json.JSONDecodeError:
                            return {}
                        if isinstance(data, dict):
                            return data
                        return {}
        return {}

    @staticmethod
    def _extract_framework(messages: list[LLMMessage]) -> str:
        for message in reversed(messages):
            if message.role != "user":
                continue
            match = re.search(r'"framework":\s*"([^"]+)"', message.content)
            if match:
                return match.group(1).casefold()
        return ""
