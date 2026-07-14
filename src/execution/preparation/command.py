"""CLI entrypoint for one bounded preparation operation."""

from __future__ import annotations

import argparse
from pathlib import Path

from execution.preparation.operations import execute_preparation
from models.execution_preparation import PreparationRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="man1lab-prepare")
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args(argv)
    request = PreparationRequest.model_validate_json(args.request_json)
    execute_preparation(request, workspace_root=Path.cwd())
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entrypoint
    raise SystemExit(main())
