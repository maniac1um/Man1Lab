"""execute command — run implementation and runtime from a strategy."""

from __future__ import annotations

from pathlib import Path

import typer

from interfaces.cli.common import get_platform, resolve_existing_file, run_command


def command(
    strategy_path: Path = typer.Option(
        ...,
        "--strategy",
        "-s",
        help="Path to ExecutionStrategy JSON.",
    ),
    analysis_path: Path = typer.Option(
        ...,
        "--analysis",
        "-a",
        help="Path to PaperReproductionAnalysis JSON.",
    ),
) -> None:
    """Run Planner → Coder → Runner for a committed strategy."""
    strategy_file = resolve_existing_file(strategy_path, label="strategy file")
    analysis_file = resolve_existing_file(analysis_path, label="analysis file")

    def _run():
        platform = get_platform()
        result = platform.execute_from_paths(strategy_file, analysis_file)
        typer.echo(f"Execution status: {result.execution_result.status}")
        typer.echo(f"Workspace: {result.workspace.root_path}")

    run_command(_run)
