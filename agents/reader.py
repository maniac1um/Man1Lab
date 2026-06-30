from pathlib import Path

from agents.analysis_snapshot import analysis_snapshot_dict, write_analysis_snapshot
from llm.mock_provider import MockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from llm.response_parser import ResponseParser
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from ports.document_parser import DocumentParser
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from validation.analysis_builder import build_analysis_from_extraction


class Reader:
    def __init__(
        self,
        document_parser: DocumentParser,
        prompt_builder: PromptBuilder | None = None,
        llm: LLMProvider | None = None,
        response_parser: ResponseParser | None = None,
    ) -> None:
        self._document_parser = document_parser
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())
        self._llm = llm or MockLLMProvider()
        self._response_parser = response_parser or ResponseParser()
        self._last_prompt: str | None = None
        self._last_extracted: dict | None = None
        self._last_analysis: PaperReproductionAnalysis | None = None

    def read_text(self, paper_path: Path) -> str:
        # TODO: Migrate to a document-based API (e.g. read_parsed_document() ->
        # ParsedDocument) so callers can access structured fields beyond markdown.
        # Keep this method name and str return type until all upstream callers migrate.
        return self._document_parser.parse(paper_path).markdown

    @property
    def last_analysis(self) -> PaperReproductionAnalysis | None:
        return self._last_analysis

    def run(self, paper_path: Path) -> PaperReproductionAnalysis:
        return self.run_analysis(paper_path)

    def run_analysis(self, paper_path: Path) -> PaperReproductionAnalysis:
        text = self.read_text(paper_path)
        self._last_prompt = self._prompt_builder.build_reader_prompt()
        messages = [
            LLMMessage(role="system", content=self._last_prompt),
            LLMMessage(role="user", content=f"Paper text:\n{text}"),
        ]
        raw_response = self._llm.complete(messages, temperature=0.0)
        self._last_extracted = self._response_parser.parse(raw_response)
        self._last_analysis = build_analysis_from_extraction(
            self._last_extracted,
            paper_path,
        )
        return self._last_analysis

    def analysis_snapshot(self) -> dict | None:
        if self._last_analysis is None:
            return None
        return analysis_snapshot_dict(self._last_analysis)

    def save_analysis_snapshot(self, path: Path) -> None:
        if self._last_analysis is None:
            raise RuntimeError("No analysis snapshot available. Call run_analysis() first.")
        write_analysis_snapshot(self._last_analysis, path)
