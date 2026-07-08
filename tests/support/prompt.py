"""Shared test fixtures for prompt infrastructure."""

from __future__ import annotations

from pathlib import Path

from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader


def default_prompt_builder(*, prompts_dir: Path | None = None) -> PromptBuilder:
    """Build a PromptBuilder for unit tests that construct agents in isolation."""
    return PromptBuilder(PromptLoader(prompts_dir=prompts_dir or Path("prompts")))
