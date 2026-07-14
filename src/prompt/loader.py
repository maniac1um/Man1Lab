from pathlib import Path

import config
from prompt.exceptions import PromptNotFoundError


class PromptLoader:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or config.PROMPTS_DIR
        self._cache: dict[tuple[str, str], str] = {}

    def load(self, agent: str, section: str) -> str:
        cache_key = (agent, section)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt_path = self._prompts_dir / agent / f"{section}.md"
        if not prompt_path.exists():
            raise PromptNotFoundError(
                f"Prompt resource not found: {agent}/{section}.md"
            )

        content = prompt_path.read_text(encoding="utf-8").strip()
        self._cache[cache_key] = content
        return content
