import os
from pathlib import Path

WORKSPACE_ROOT = Path("workspace/tasks")
OUTPUTS_DIR = Path("outputs")
LOGS_DIR = Path("logs")
PROMPTS_DIR = Path("prompts")
MAX_REVIEW_ITERATIONS = 3

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

# Truncate extracted PDF text before sending to the LLM.
MAX_PAPER_TEXT_CHARS = 80_000
