from pathlib import Path

from models.paper import PaperModel
from services.pdf_service import PDFService

_PLACEHOLDER = "Pending LLM extraction."


class Reader:
    def __init__(self, pdf_service: PDFService) -> None:
        self._pdf_service = pdf_service

    def read_text(self, paper_path: Path) -> str:
        return self._pdf_service.extract(paper_path)

    def run(self, paper_path: Path) -> PaperModel:
        text = self.read_text(paper_path)
        return self._build_placeholder_paper(text, paper_path)

    @staticmethod
    def _build_placeholder_paper(text: str, paper_path: Path) -> PaperModel:
        title = Reader._extract_title(text)
        return PaperModel(
            title=title,
            abstract=_PLACEHOLDER,
            method=_PLACEHOLDER,
            dataset=_PLACEHOLDER,
            model=_PLACEHOLDER,
            framework=_PLACEHOLDER,
            optimizer=_PLACEHOLDER,
            loss=_PLACEHOLDER,
            training_pipeline=_PLACEHOLDER,
            evaluation_metric=_PLACEHOLDER,
            source_path=paper_path,
        )

    @staticmethod
    def _extract_title(text: str) -> str:
        for line in text.splitlines():
            if line.startswith("Title:"):
                return line.removeprefix("Title:").strip()
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return "Unknown"
