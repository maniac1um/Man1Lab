"""First-run model configuration helpers for workspace initialization."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InitWizardRequest:
    profile_name: str = "default"
    provider: str = "openai"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    description: str = ""


@dataclass(frozen=True)
class ResolvedWizardProfile:
    profile_name: str
    provider: str
    model: str
    base_url: str
    api_key_reference: str
    temperature: float | None
    max_tokens: int | None
    description: str


@dataclass(frozen=True)
class ProviderWizardDefaults:
    model: str
    api_key_reference: str
    base_url: str = ""


PROVIDER_DEFAULTS: dict[str, ProviderWizardDefaults] = {
    "openai": ProviderWizardDefaults(
        model="gpt-4o-mini",
        api_key_reference="OPENAI_API_KEY",
    ),
    "deepseek": ProviderWizardDefaults(
        model="deepseek-chat",
        api_key_reference="OPENAI_API_KEY",
        base_url="https://api.deepseek.com",
    ),
    "anthropic": ProviderWizardDefaults(
        model="claude-sonnet-4",
        api_key_reference="ANTHROPIC_API_KEY",
    ),
}

PROVIDER_MENU: tuple[tuple[str, str], ...] = (
    ("1", "openai"),
    ("2", "deepseek"),
    ("3", "anthropic"),
)


def resolve_provider_choice(choice: str) -> str:
    normalized = choice.strip().lower()
    mapping = {key: provider for key, provider in PROVIDER_MENU}
    mapping.update({provider: provider for _, provider in PROVIDER_MENU})
    if normalized not in mapping:
        raise ValueError(f"Unknown provider choice: {choice}")
    return mapping[normalized]


def resolve_wizard_profile(request: InitWizardRequest) -> ResolvedWizardProfile:
    provider = resolve_provider_choice(request.provider)
    defaults = PROVIDER_DEFAULTS[provider]
    return ResolvedWizardProfile(
        profile_name=request.profile_name or "default",
        provider=provider,
        model=request.model or defaults.model,
        base_url=request.base_url if request.base_url else defaults.base_url,
        api_key_reference=defaults.api_key_reference,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        description=request.description,
    )


def write_api_key_to_env(env_path: Path, api_key_reference: str, api_key: str) -> None:
    if not api_key.strip():
        raise ValueError("API key is required.")

    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(f"{api_key_reference}="):
            new_lines.append(f"{api_key_reference}={api_key}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"{api_key_reference}={api_key}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[api_key_reference] = api_key
