"""Workspace initialization lifecycle service."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from application.lifecycle.common import ensure_directory
from configuration.models import AppSettings
from configuration.paths import resolve_env_example


@dataclass(frozen=True)
class InitAction:
    path: Path
    action: str
    message: str


@dataclass(frozen=True)
class InitReport:
    successful: bool
    actions: list[InitAction] = field(default_factory=list)
    github_token_configured: bool = False
    next_steps: list[str] = field(default_factory=list)


def init_workspace(
    settings: AppSettings,
    *,
    workspace_root: Path | None = None,
) -> InitReport:
    """Initialize a Man1Lab workspace without overwriting existing user files."""
    actions: list[InitAction] = []
    next_steps: list[str] = []
    root = workspace_root or Path.cwd()

    directory_targets = {
        "workspace_root": settings.workspace_root,
        "outputs_dir": settings.outputs_dir,
        "logs_dir": settings.logs_dir,
        "mlruns": root / "mlruns",
        "cache": root / ".cache" / "man1lab",
    }

    for path in directory_targets.values():
        action, message = ensure_directory(path)
        actions.append(InitAction(path=path, action=action, message=message))
        if action == "failed":
            return InitReport(
                successful=False,
                actions=actions,
                next_steps=["Fix write permissions and run `man1lab init` again."],
            )

    env_path = root / ".env"
    env_example = resolve_env_example()
    if env_path.exists():
        actions.append(
            InitAction(
                path=env_path,
                action="skipped",
                message="Existing .env preserved.",
            )
        )
    elif env_example is not None:
        shutil.copy(env_example, env_path)
        actions.append(
            InitAction(
                path=env_path,
                action="created",
                message="Created .env from template.",
            )
        )
        next_steps.append("Edit .env and add your LLM API keys.")
    else:
        actions.append(
            InitAction(
                path=env_path,
                action="skipped",
                message=".env template not found; create .env manually.",
            )
        )

    config_path = root / "conf" / "config.yaml"
    if config_path.exists():
        actions.append(
            InitAction(
                path=config_path,
                action="skipped",
                message="Existing configuration preserved.",
            )
        )
    else:
        actions.append(
            InitAction(
                path=config_path,
                action="info",
                message="Using bundled Hydra configuration (conf/).",
            )
        )

    github_token_configured = bool(os.environ.get("GITHUB_TOKEN", "").strip())
    if github_token_configured:
        next_steps.append("GitHub token detected — discovery can use GitHub providers.")
    else:
        next_steps.append("Set GITHUB_TOKEN in .env for GitHub discovery.")

    next_steps.extend(
        [
            "Run `man1lab doctor` to validate the environment.",
            "Run `man1lab reproduce paper.pdf` to start a reproduction.",
        ]
    )

    return InitReport(
        successful=True,
        actions=actions,
        github_token_configured=github_token_configured,
        next_steps=next_steps,
    )
