import json

from llm.provider import LLMMessage, LLMProvider

MOCK_PAPER_JSON = json.dumps(
    {
        "title": "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
        "abstract": "Mock abstract for skeleton execution.",
        "method": "Action diffusion for visuomotor control.",
        "dataset": "Robomimic benchmark tasks.",
        "model": "Conditional diffusion policy network.",
        "framework": "PyTorch",
        "optimizer": "AdamW",
        "loss": "Behavior cloning diffusion loss.",
        "training_pipeline": "Collect demos, train diffusion policy, evaluate success rate.",
        "evaluation_metric": "Task success rate",
    }
)


class MockLLMProvider(LLMProvider):
    def __init__(self, response: str = MOCK_PAPER_JSON) -> None:
        self._response = response

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        return self._response
