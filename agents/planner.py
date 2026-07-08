from agents.analysis_context import build_planner_legacy_user_content, build_planner_user_content
from llm.mock_provider import MOCK_PLANNER_JSON, MockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from llm.response_parser import ResponseParser
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.task import TaskModel
from prompt.builder import PromptBuilder
from validation.task import build_task_model


class Planner:
    def __init__(
        self,
        prompt_builder: PromptBuilder,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm = llm or MockLLMProvider(MOCK_PLANNER_JSON)
        self._response_parser = response_parser or ResponseParser()
        self._last_prompt: str | None = None
        self._last_extracted: dict | None = None

    def run(self, execution_strategy: ExecutionStrategy) -> TaskModel:
        """Decompose tasks from a committed ExecutionStrategy (strategy-driven planning)."""
        self._last_prompt = self._prompt_builder.build_planner_prompt()
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(role="user", content=build_planner_user_content(execution_strategy)),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        return build_task_model(self._last_extracted)

    def run_legacy(self, analysis: PaperReproductionAnalysis) -> TaskModel:
        """Transitional compatibility — plan directly from analysis without ExecutionStrategy."""
        self._last_prompt = self._prompt_builder.build_planner_prompt()
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(role="user", content=build_planner_legacy_user_content(analysis)),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        return build_task_model(self._last_extracted)
