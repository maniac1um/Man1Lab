"""model command group — manage LLM model profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command

app = typer.Typer(
    name="model",
    help="Manage LLM model profiles.",
    no_args_is_help=True,
    add_completion=False,
)


def _print_validation(report) -> None:
    for warning in report.warnings:
        typer.secho(f"Warning: {warning.message}", fg=typer.colors.YELLOW)
    for error in report.errors:
        typer.secho(f"Error: {error.message}", fg=typer.colors.RED, err=True)


@app.command("list")
def list_profiles() -> None:
    """List configured model profiles."""
    def _run():
        report = get_platform().list_models()
        for profile in report.profiles:
            marker = "*" if profile.active else " "
            enabled = "yes" if profile.enabled else "no"
            typer.echo(
                f"{marker} {profile.profile_name:<12} {profile.provider:<10} "
                f"{profile.model:<20} enabled={enabled}"
            )
            if profile.description:
                typer.echo(f"    {profile.description}")

    run_command(_run)


@app.command("current")
def current_profile() -> None:
    """Show the active model profile."""
    def _run():
        report = get_platform().current_model()
        if report is None:
            typer.secho("No active model profile is configured.", fg=typer.colors.YELLOW)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(f"Active Profile: {report.profile_name}")
        typer.echo(f"Provider: {report.provider}")
        typer.echo(f"Model: {report.model}")
        typer.echo(f"Base URL: {report.base_url or '-'}")
        typer.echo(f"API Key Reference: {report.api_key_reference}")
        typer.echo(f"Enabled: {'yes' if report.enabled else 'no'}")

    run_command(_run)


@app.command("use")
def use_profile(
    profile_name: str = typer.Argument(..., help="Profile name to activate."),
) -> None:
    """Switch the active model profile."""
    def _run():
        report = get_platform().use_model(profile_name)
        if not report.successful:
            if report.validation is not None:
                _print_validation(report.validation)
            typer.secho(report.message, fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(report.message)
        typer.echo(f"Active profile: {report.active_profile}")

    run_command(_run)


@app.command("add")
def add_profile(
    profile_name: Optional[str] = typer.Option(None, "--name", help="Profile name."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Provider name."),
    model: Optional[str] = typer.Option(None, "--model", help="Model identifier."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Optional API base URL."),
    api_key_reference: Optional[str] = typer.Option(
        None,
        "--api-key-reference",
        help="Environment variable reference for the API key.",
    ),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Default temperature."),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Default max tokens."),
    description: Optional[str] = typer.Option(None, "--description", help="Profile description."),
) -> None:
    """Add a model profile."""
    def _run():
        resolved_name = profile_name or typer.prompt("Profile name")
        resolved_provider = provider or typer.prompt("Provider", default="openai")
        resolved_model = model or typer.prompt("Model")
        resolved_base_url = base_url if base_url is not None else typer.prompt(
            "Base URL (optional)",
            default="",
            show_default=False,
        )
        resolved_api_key_reference = api_key_reference or typer.prompt(
            "API Key Reference",
            default="OPENAI_API_KEY",
        )
        resolved_temperature = temperature
        if resolved_temperature is None:
            raw_temperature = typer.prompt("Temperature (optional)", default="", show_default=False)
            resolved_temperature = float(raw_temperature) if raw_temperature else None
        resolved_max_tokens = max_tokens
        if resolved_max_tokens is None:
            raw_max_tokens = typer.prompt("Max Tokens (optional)", default="", show_default=False)
            resolved_max_tokens = int(raw_max_tokens) if raw_max_tokens else None
        resolved_description = description if description is not None else typer.prompt(
            "Description",
            default="",
            show_default=False,
        )

        report = get_platform().add_model(
            profile_name=resolved_name,
            provider=resolved_provider,
            model=resolved_model,
            base_url=resolved_base_url,
            api_key_reference=resolved_api_key_reference,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
            description=resolved_description,
        )
        if not report.successful:
            if report.validation is not None:
                _print_validation(report.validation)
            typer.secho(report.message, fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(report.message)

    run_command(_run)


@app.command("remove")
def remove_profile(
    profile_name: str = typer.Argument(..., help="Profile name to remove."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow removing the active profile.",
    ),
) -> None:
    """Remove a model profile."""
    def _run():
        report = get_platform().remove_model(profile_name, force=force)
        if not report.successful:
            if report.validation is not None:
                _print_validation(report.validation)
            typer.secho(report.message, fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(report.message)

    run_command(_run)


@app.command("rename")
def rename_profile(
    old_name: str = typer.Argument(..., help="Existing profile name."),
    new_name: str = typer.Argument(..., help="New profile name."),
) -> None:
    """Rename a model profile."""
    def _run():
        report = get_platform().rename_model(old_name, new_name)
        if not report.successful:
            if report.validation is not None:
                _print_validation(report.validation)
            typer.secho(report.message, fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(report.message)

    run_command(_run)


@app.command("test")
def test_profile(
    profile_name: Optional[str] = typer.Argument(
        None,
        help="Profile name to test (defaults to active profile).",
    ),
) -> None:
    """Test provider connectivity for a model profile."""
    def _run():
        report = get_platform().test_model(profile_name)
        typer.echo(f"Profile: {report.profile_name}")
        typer.echo(f"Provider: {report.provider}")
        typer.echo(f"Model: {report.model}")
        typer.echo(f"Authentication: {report.authentication}")
        typer.echo(f"Connection: {report.connection}")
        if report.latency_ms is not None:
            typer.echo(f"Latency: {report.latency_ms} ms")
        typer.echo(f"Result: {report.result}")
        typer.echo(report.message)
        if report.result != "passed":
            raise typer.Exit(EXIT_PLATFORM_FAILURE)

    run_command(_run)


@app.command("validate")
def validate_profiles() -> None:
    """Validate configured model profiles."""
    def _run():
        report = get_platform().validate_models()
        if report.warnings:
            typer.echo("Warnings:")
            for warning in report.warnings:
                typer.secho(f"  - {warning.message}", fg=typer.colors.YELLOW)
        if report.errors:
            typer.echo("Errors:")
            for error in report.errors:
                typer.secho(f"  - {error.message}", fg=typer.colors.RED, err=True)
        if report.valid:
            typer.echo("Validation passed.")
            return
        typer.secho("Validation failed.", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_PLATFORM_FAILURE)

    run_command(_run)


@app.command("export")
def export_profiles(
    output: Path = typer.Argument(
        ...,
        help="Path to write portable profile configuration.",
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Export portable model profile configuration (no secrets)."""
    def _run():
        path = get_platform().export_models(output)
        typer.echo(f"Exported model profiles to {path}")

    run_command(_run)


@app.command("import")
def import_profiles(
    source: Path = typer.Argument(
        ...,
        help="Portable profile configuration file to import.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Replace existing profiles with the same name.",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip profiles that already exist.",
    ),
) -> None:
    """Import portable model profile configuration."""
    def _run():
        report = get_platform().import_models(
            source,
            replace=replace,
            skip_existing=skip_existing,
        )
        if report.added:
            typer.echo("Imported:")
            for name in report.added:
                typer.echo(f"  - {name}")
        if report.skipped:
            typer.echo("Skipped:")
            for name in report.skipped:
                typer.echo(f"  - {name}")
        if report.replaced:
            typer.echo("Replaced:")
            for name in report.replaced:
                typer.echo(f"  - {name}")
        if not report.successful:
            typer.secho(report.message, fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo(report.message)

    run_command(_run)
