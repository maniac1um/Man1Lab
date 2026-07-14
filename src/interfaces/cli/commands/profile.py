"""profile command — profile platform startup and runtime initialization."""

from __future__ import annotations

import typer

from application.facade import Man1Lab
from interfaces.cli.common import run_command


def command() -> None:
    """Profile startup and runtime initialization."""
    def _run():
        report = Man1Lab.profile_startup()
        typer.echo(report.format_report())

    run_command(_run)
