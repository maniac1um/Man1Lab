"""Resolve bundled and development resource paths."""

from __future__ import annotations

import sysconfig
from pathlib import Path


def resolve_conf_dir() -> Path:
    """Return the Hydra configuration directory."""
    candidates = (
        Path(__file__).resolve().parents[1] / "conf",
        Path(sysconfig.get_path("data")) / "share" / "man1lab" / "conf",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Man1Lab configuration directory not found.")


def resolve_prompts_dir() -> Path:
    """Return the prompts resource directory."""
    candidates = (
        Path(__file__).resolve().parents[1] / "prompts",
        Path(sysconfig.get_path("data")) / "share" / "man1lab" / "prompts",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Man1Lab prompts directory not found.")


def resolve_configured_prompts_dir(configured: Path) -> Path:
    """Resolve ``prompts_dir`` from settings; relative values use bundled/dev layout."""
    if configured.is_absolute():
        return configured
    return resolve_prompts_dir()


def resolve_env_example() -> Path | None:
    """Return the bundled .env.example template when available."""
    candidates = (
        Path(__file__).resolve().parents[1] / ".env.example",
        Path(sysconfig.get_path("data")) / "share" / "man1lab" / ".env.example",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def resolve_llm_user_profiles_path() -> Path:
    """Return the user-writable LLM profile overlay path."""
    return resolve_conf_dir() / "llm" / "user_profiles.yaml"
