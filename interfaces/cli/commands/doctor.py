"""doctor command — validate runtime environment."""

from __future__ import annotations

import typer

from application.lifecycle import format_check_status
from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command


def command() -> None:
    """Validate runtime environment and prerequisites."""
    def _run():
        report = get_platform().doctor()
        for check in report.checks:
            symbol = format_check_status(check.status)
            typer.echo(f"{symbol} {check.name}: {check.message}")
        if not report.healthy:
            raise typer.Exit(EXIT_PLATFORM_FAILURE)
        typer.echo("Environment check passed.")

    run_command(_run)
