"""init command — initialize a Man1Lab workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command


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
) -> None:
    """Initialize workspace directories and default configuration templates."""
    def _run():
        report = get_platform().init(workspace_root=workspace_root)
        for action in report.actions:
            typer.echo(f"[{action.action}] {action.path}: {action.message}")
        if report.github_token_configured:
            typer.echo("GitHub token: configured")
        else:
            typer.echo("GitHub token: not configured")
        typer.echo("")
        typer.echo("Next steps:")
        for step in report.next_steps:
            typer.echo(f"  - {step}")
        if not report.successful:
            raise typer.Exit(EXIT_PLATFORM_FAILURE)

    run_command(_run)
