"""Session-scoped workspace references with optional on-disk hydration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SessionWorkspace:
    """Optional session-scoped workspace placeholders for future interactive use."""

    workspace_root: Path | None = None
    current_paper: Any | None = None
    current_analysis: Any | None = None
    current_discovery: Any | None = None
    current_strategy: Any | None = None
    current_execution_run_id: str | None = None
