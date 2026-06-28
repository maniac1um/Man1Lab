from pathlib import Path

import config


def load_agent_prompts(agent_name: str, prompts_dir: Path | None = None) -> tuple[str, str]:
    base_dir = prompts_dir or config.PROMPTS_DIR
    agent_dir = base_dir / agent_name

    system_path = agent_dir / "system.md"
    output_path = agent_dir / "output.md"

    if not system_path.exists():
        raise FileNotFoundError(f"Missing system prompt: {system_path}")
    if not output_path.exists():
        raise FileNotFoundError(f"Missing output prompt: {output_path}")

    system_prompt = system_path.read_text(encoding="utf-8").strip()
    output_prompt = output_path.read_text(encoding="utf-8").strip()
    return system_prompt, output_prompt
