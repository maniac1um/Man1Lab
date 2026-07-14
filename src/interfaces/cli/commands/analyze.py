"""analyze command — run analysis only."""

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
        help="Optional path to write analysis JSON.",
    ),
) -> None:
    """Extract PaperReproductionAnalysis from a paper."""
    path = resolve_paper_path(paper_path)

    def _run():
        platform = get_platform()
        analysis = platform.analyze(path)
        if output is not None:
            output.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
            typer.echo(f"Analysis written to: {output}")
        else:
            echo_json(analysis)

    run_command(_run)
