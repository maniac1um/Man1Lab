"""clean command — remove regeneratable workspace artifacts."""

from __future__ import annotations

import typer

from application.lifecycle import CleanPolicy
from interfaces.cli.common import EXIT_PLATFORM_FAILURE, get_platform, run_command


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _display_path(path: object, project_root: object | None = None) -> str:
    from pathlib import Path

    resolved = Path(path)
    if project_root is not None:
        try:
            return str(resolved.relative_to(Path(project_root).resolve()))
        except ValueError:
            pass
    return str(resolved)


def command(
    all_: bool = typer.Option(
        False,
        "--all",
        help="Remove all workspace outputs including tasks and artifacts.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report removable paths without deleting anything.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation for --all cleanup.",
    ),
) -> None:
    """Remove regeneratable workspace artifacts (SAFE mode by default)."""
    def _run():
        if all_ and not dry_run and not yes:
            typer.confirm(
                "This will remove all workspace outputs including tasks. Continue?",
                abort=True,
            )

        policy = CleanPolicy.ALL if all_ else CleanPolicy.SAFE
        report = get_platform().clean(policy=policy, dry_run=dry_run)

        if dry_run:
            typer.echo("Will remove")
            for path in report.planned_paths:
                typer.echo(f"✓ {_display_path(path)}")
            typer.echo("")
            typer.echo(f"Total reclaimable size: {_format_bytes(report.bytes_removed)}")
            typer.echo("Nothing deleted.")
            return

        for path in report.deleted_paths:
            typer.echo(f"Removed {_display_path(path)}")
        for path in report.skipped_paths:
            typer.echo(f"Skipped {_display_path(path)}")
        for warning in report.warnings:
            typer.echo(f"Warning: {warning}")
        for error in report.errors:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)

        if report.deleted_paths:
            typer.echo(f"Reclaimed {_format_bytes(report.bytes_removed)}.")
        else:
            typer.echo("No removable artifacts found.")

        if not report.successful:
            raise typer.Exit(EXIT_PLATFORM_FAILURE)

    run_command(_run)
