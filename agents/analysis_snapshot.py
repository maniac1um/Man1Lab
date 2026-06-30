"""Serialize PaperReproductionAnalysis artifacts produced by Reader."""

from __future__ import annotations

import json
from pathlib import Path

from models.paper_reproduction_analysis import PaperReproductionAnalysis


def analysis_snapshot_dict(analysis: PaperReproductionAnalysis) -> dict:
    return analysis.model_dump(mode="json")


def write_analysis_snapshot(analysis: PaperReproductionAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(analysis_snapshot_dict(analysis), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
