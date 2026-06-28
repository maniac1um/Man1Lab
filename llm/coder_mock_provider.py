from llm.provider import LLMMessage, LLMProvider

MOCK_FILE_CONTENT: dict[str, str] = {
    "requirements.txt": "torch>=2.0.0\nnumpy>=1.24.0\n",
    "src/dataset.py": '"""Dataset module."""\n\n\nclass Dataset:\n    """Dataset placeholder."""\n\n    pass\n',
    "configs/dataset.yaml": "dataset:\n  name: benchmark\n  path: data/\n",
    "src/model.py": '"""Model module."""\n\n\nclass Model:\n    """Model placeholder."""\n\n    pass\n',
    "scripts/train.py": '"""Training script."""\n\n\ndef main() -> None:\n    print("Training complete.")\n\n\nif __name__ == "__main__":\n    main()\n',
    "configs/train.yaml": "training:\n  epochs: 10\n  batch_size: 32\n",
    "scripts/evaluate.py": '"""Evaluation script."""\n\n\ndef main() -> None:\n    print("Evaluation complete.")\n\n\nif __name__ == "__main__":\n    main()\n',
}

_TARGET_FILE_PREFIX = "Target file: "


class CoderMockLLMProvider(LLMProvider):
    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        target_path = self._extract_target_path(messages)
        return MOCK_FILE_CONTENT.get(target_path, f"# Generated: {target_path}\n")

    @staticmethod
    def _extract_target_path(messages: list[LLMMessage]) -> str:
        for message in reversed(messages):
            if message.role != "user":
                continue
            for line in message.content.splitlines():
                if line.startswith(_TARGET_FILE_PREFIX):
                    return line.removeprefix(_TARGET_FILE_PREFIX).strip()
        return "unknown"
