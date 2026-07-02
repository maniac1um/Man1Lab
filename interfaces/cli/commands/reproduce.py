"""reproduce command — run the full Man1Lab pipeline."""

from __future__ import annotations

from pathlib import Path

import typer

from interfaces.cli.common import get_platform, resolve_paper_path, run_command


def command(
    paper_path: Path = typer.Argument(
        ...,
        help="Path to the research paper PDF.",
    ),
) -> None:
    """Run the complete reproduction workflow."""
    path = resolve_paper_path(paper_path)

    def _run():
        platform = get_platform()
        report = platform.reproduce(path)
        typer.echo(f"Workflow complete. Final status: {report.final_status}")
        if report.report_path:
            typer.echo(f"Report written to: {report.report_path}")

    run_command(_run)
