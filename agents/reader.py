from pathlib import Path

from llm.mock_provider import MockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from llm.response_parser import ResponseParser
from models.paper import PaperModel
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from services.pdf_service import PDFService
from validation.paper import build_paper_model


class Reader:
    def __init__(
        self,
        pdf_service: PDFService,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None:
        self._pdf_service = pdf_service
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())
        self._llm = llm or MockLLMProvider()
        self._response_parser = response_parser or ResponseParser()
        self._last_prompt: str | None = None
        self._last_extracted: dict | None = None

    def read_text(self, paper_path: Path) -> str:
        return self._pdf_service.extract(paper_path)

    def run(self, paper_path: Path) -> PaperModel:
        text = self.read_text(paper_path)
        self._last_prompt = self._prompt_builder.build_reader_prompt()
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(role="user", content=f"Paper text:\n{text}"),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        return build_paper_model(self._last_extracted, paper_path)
