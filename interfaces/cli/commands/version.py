"""version command — show platform version."""

from __future__ import annotations

import typer

from interfaces.cli.common import get_platform


def command() -> None:
    """Show the Man1Lab platform version."""
    typer.echo(get_platform().version())
