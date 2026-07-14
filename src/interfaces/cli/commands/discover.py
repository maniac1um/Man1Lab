"""discover command — run discovery only."""

from __future__ import annotations

from pathlib import Path

import typer

from interfaces.cli.common import echo_json, get_platform, resolve_paper_path, run_command


def command(
    paper_path: Path = typer.Argument(
        ...,
        help="Path to the research paper PDF.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write discovery JSON.",
    ),
) -> None:
    """Produce ResearchResourceDiscovery for a paper."""
    path = resolve_paper_path(paper_path)

    def _run():
        platform = get_platform()
        discovery = platform.discover(paper_path=path)
        if output is not None:
            output.write_text(discovery.model_dump_json(indent=2), encoding="utf-8")
            typer.echo(f"Discovery written to: {output}")
        else:
            echo_json(discovery)

    run_command(_run)
