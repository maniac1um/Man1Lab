"""Shared CLI helpers — facade delegation and exit codes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import typer

from application import Man1Lab

EXIT_SUCCESS = 0
EXIT_PLATFORM_FAILURE = 1
EXIT_INVALID_ARGUMENTS = 2

T = TypeVar("T")


def get_platform() -> Man1Lab:
    return Man1Lab()


def resolve_paper_path(paper_path: Path) -> Path:
    resolved = paper_path.expanduser().resolve()
    if not resolved.exists():
        typer.secho(f"Error: paper not found: {resolved}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_INVALID_ARGUMENTS)
    if resolved.suffix.lower() != ".pdf":
        typer.secho(f"Error: expected a PDF file: {resolved}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_INVALID_ARGUMENTS)
    return resolved


def resolve_existing_file(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        typer.secho(f"Error: {label} not found: {resolved}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_INVALID_ARGUMENTS)
    return resolved


def run_command(action: Callable[[], T]) -> T:
    try:
        return action()
    except typer.Exit:
        raise
    except (ValueError, FileNotFoundError) as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_INVALID_ARGUMENTS) from exc
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_PLATFORM_FAILURE) from exc


def echo_json(payload: object) -> None:
    if hasattr(payload, "model_dump_json"):
        typer.echo(payload.model_dump_json(indent=2))
    else:
        typer.echo(str(payload))
