"""Man1Lab CLI — thin Typer interface over the Platform Facade."""

from __future__ import annotations

import typer

from application import PLATFORM_VERSION
from interfaces.cli.commands import analyze, config, discover, doctor, execute, init, plan, reproduce, version

app = typer.Typer(
    name="man1lab",
    help="Man1Lab — autonomous research paper reproduction platform.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_option(value: bool) -> None:
    if value:
        typer.echo(PLATFORM_VERSION)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    show_version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_option,
        is_eager=True,
        help="Show the platform version and exit.",
    ),
) -> None:
    """Man1Lab platform command line interface."""
    del ctx, show_version


app.command("reproduce", help="Run the complete reproduction workflow.")(reproduce.command)
app.command("analyze", help="Run analysis (Reader) only.")(analyze.command)
app.command("discover", help="Run discovery only.")(discover.command)
app.command("plan", help="Run execution planning only.")(plan.command)
app.command(
    "execute",
    help="Execute implementation and runtime for an existing strategy.",
)(execute.command)
app.command("doctor", help="Validate runtime environment and prerequisites.")(doctor.command)
app.command("init", help="Initialize workspace directories and configuration templates.")(init.command)
app.command("config", help="Show effective runtime configuration.")(config.command)
app.command("version", help="Show the Man1Lab platform version.")(version.command)


if __name__ == "__main__":
    app()


def run_cli() -> None:
    """Console script entry point for setuptools."""
    app()
