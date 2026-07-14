"""doctor command — validate runtime environment."""

from __future__ import annotations

import typer

from application.lifecycle import format_check_status
from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command


def command() -> None:
    """Validate runtime environment and prerequisites."""
    def _run():
        report = get_platform().doctor()
        llm_checks = [check for check in report.checks if check.name.startswith("LLM")]
        other_checks = [check for check in report.checks if not check.name.startswith("LLM")]

        for check in other_checks:
            symbol = format_check_status(check.status)
            typer.echo(f"{symbol} {check.name}: {check.message}")

        if llm_checks:
            typer.echo("")
            typer.echo("LLM")
            for check in llm_checks:
                symbol = format_check_status(check.status)
                label = check.name.removeprefix("LLM ").strip()
                typer.echo(f"{symbol} {label}: {check.message}")

        if not report.healthy:
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo("Environment check passed.")

    run_command(_run)
