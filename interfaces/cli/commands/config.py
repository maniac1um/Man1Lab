"""config command — show effective runtime configuration."""

from __future__ import annotations

import json

import typer

from interfaces.cli.common import get_platform, run_command


def command() -> None:
    """Show effective runtime configuration."""
    def _run():
        configuration = get_platform().configuration()
        typer.echo(json.dumps(configuration, indent=2))

    run_command(_run)
