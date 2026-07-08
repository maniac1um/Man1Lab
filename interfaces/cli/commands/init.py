"""init command — initialize a Man1Lab workspace."""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import Optional

import typer

from application.lifecycle.init_wizard import (
    PROVIDER_DEFAULTS,
    InitWizardRequest,
    resolve_provider_choice,
)
from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command


def _run_model_wizard() -> InitWizardRequest:
    typer.echo("")
    profile_name = typer.prompt("Profile name", default="default")
    typer.echo("Provider:")
    typer.echo("  1 OpenAI")
    typer.echo("  2 DeepSeek")
    typer.echo("  3 Anthropic")
    provider_choice = typer.prompt("Provider", default="1")
    provider = resolve_provider_choice(provider_choice)
    defaults = PROVIDER_DEFAULTS[provider]
    model = typer.prompt("Model", default=defaults.model)
    api_key = getpass.getpass("API Key: ")
    base_url = typer.prompt(
        "Base URL (optional)",
        default=defaults.base_url,
        show_default=bool(defaults.base_url),
    )
    temperature_raw = typer.prompt("Temperature (optional)", default="", show_default=False)
    max_tokens_raw = typer.prompt("Max Tokens (optional)", default="", show_default=False)
    description = typer.prompt("Description (optional)", default="", show_default=False)
    return InitWizardRequest(
        profile_name=profile_name,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=float(temperature_raw) if temperature_raw else None,
        max_tokens=int(max_tokens_raw) if max_tokens_raw else None,
        description=description,
    )


def command(
    workspace_root: Optional[Path] = typer.Option(
        None,
        "--workspace-root",
        "-w",
        help="Workspace root directory (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    skip_model_config: bool = typer.Option(
        False,
        "--skip-model-config",
        help="Skip interactive first-model configuration.",
    ),
) -> None:
    """Initialize workspace directories and default configuration templates."""
    def _run():
        wizard_request = None
        if not skip_model_config:
            configure = typer.confirm(
                "Configure your first AI model?",
                default=True,
            )
            if configure:
                wizard_request = _run_model_wizard()

        platform = get_platform()
        report = platform.init(workspace_root=workspace_root)
        for action in report.actions:
            typer.echo(f"[{action.action}] {action.path}: {action.message}")
        if report.github_token_configured:
            typer.echo("GitHub token: configured")
        else:
            typer.echo("GitHub token: not configured")

        if not report.successful:
            raise typer.Exit(EXIT_PLATFORM_FAILURE)

        if wizard_request is not None:
            setup = platform.setup_first_model(
                wizard_request,
                workspace_root=workspace_root,
            )
            if setup.successful:
                typer.echo("")
                typer.echo("Workspace initialized.")
                typer.echo(f"Active model: {setup.profile_name}")
                typer.echo(f"Provider: {setup.provider.capitalize()}")
                typer.echo("Run `man1lab doctor` to verify your environment.")
                typer.echo("")
                typer.echo("Next steps:")
                typer.echo("  - man1lab model list")
                typer.echo("  - man1lab model use <profile>")
            else:
                typer.secho(setup.message, fg=typer.colors.RED, err=True)
        else:
            typer.echo("")
            typer.echo("Next steps:")
            for step in report.next_steps:
                typer.echo(f"  - {step}")

    run_command(_run)
