from agents.analysis_context import build_reviewer_user_content
from llm.mock_provider import MOCK_REVIEWER_PASS_JSON, MockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from llm.response_parser import ResponseParser
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.review import PatchPlan
from models.review_report import ReviewReport
from models.task import TaskModel
from models.verification import VerificationResult
from planning.patch_planner import PatchPlanner
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from validation.review import build_review_report


class Reviewer:
    def __init__(
        self,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
        patch_planner: PatchPlanner | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())
        self._llm = llm or MockLLMProvider(MOCK_REVIEWER_PASS_JSON)
        self._response_parser = response_parser or ResponseParser()
        self._patch_planner = patch_planner or PatchPlanner()
        self._last_prompt: str | None = None
        self._last_extracted: dict | None = None

    def run(
        self,
        analysis: PaperReproductionAnalysis,
        task: TaskModel,
        verification_result: VerificationResult,
    ) -> ReviewReport:
        self._last_prompt = self._prompt_builder.build_reviewer_prompt()
        user_content = build_reviewer_user_content(analysis, task, verification_result)
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(role="user", content=user_content),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        return build_review_report(self._last_extracted)

    def plan_patch(self, review_report: ReviewReport) -> PatchPlan:
        return self._patch_planner.plan(review_report)
