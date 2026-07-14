"""Build PaperReproductionAnalysis from Reader LLM extraction."""

from __future__ import annotations

from pathlib import Path

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from validation.paper_reproduction_analysis import build_paper_reproduction_analysis


def build_analysis_from_extraction(
    data: dict,
    source_path: Path,
) -> PaperReproductionAnalysis:
    """Validate and construct analysis from native Reader LLM JSON."""
    return build_paper_reproduction_analysis(data, source_path=source_path)
