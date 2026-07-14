"""Setuptools hook for bundling Hydra configuration and prompt resources."""

from __future__ import annotations

from pathlib import Path

from setuptools import setup


def _data_files(prefix: str, directory: str) -> list[tuple[str, list[str]]]:
    root = Path(directory)
    grouped: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            destination = str(Path(prefix) / path.relative_to(root).parent)
            grouped.setdefault(destination, []).append(str(path))
    return sorted(grouped.items())


setup(
    data_files=_data_files("share/man1lab/conf", "resources/conf")
    + _data_files("share/man1lab/prompts", "resources/prompts")
    + [("share/man1lab", [".env.example"])],
)
