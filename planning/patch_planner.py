from llm.mock_provider import MOCK_PATCH_NO_ITERATION_JSON, MockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from llm.response_parser import ResponseParser
from models.review_report import ReviewReport
from models.review import PatchPlan
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from validation.patch import build_patch_plan


class PatchPlanner:
    def __init__(
        self,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())
        self._llm = llm or MockLLMProvider(MOCK_PATCH_NO_ITERATION_JSON)
        self._response_parser = response_parser or ResponseParser()
        self._last_prompt: str | None = None
        self._last_extracted: dict | None = None

    def plan(self, review_report: ReviewReport) -> PatchPlan:
        self._last_prompt = self._prompt_builder.build_patch_planner_prompt()
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(
                role="user",
                content=(
                    "ReviewReport:\n"
                    f"{review_report.model_dump_json(indent=2)}"
                ),
            ),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        return build_patch_plan(self._last_extracted)
