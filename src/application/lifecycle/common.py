"""Shared lifecycle helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROTECTED_TOP_LEVEL_DIRS = frozenset({"conf", "docs", "tests", "prompts", "source"})
PROTECTED_RELATIVE_PATHS = frozenset(
    {
        Path(".git"),
        Path(".env"),
        Path("pyproject.toml"),
        Path("README.md"),
        Path("workspace") / "papers",
    }
)


def format_check_status(status: str) -> str:
    """Map internal status to display symbol."""
    return {
        "ok": "✓",
        "warn": "⚠",
        "fail": "✗",
    }.get(status, status)


def ensure_directory(path: Path) -> tuple[str, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if not os.access(path, os.W_OK):
            return "failed", f"Not writable: {path}"
        if path.exists():
            return "ready", f"Directory ready: {path}"
        return "created", f"Created directory: {path}"
    except OSError as exc:
        return "failed", f"Cannot create {path}: {exc}"


def resolve_project_path(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def is_never_delete(path: Path, project_root: Path) -> bool:
    """Return True when a path must never be removed by lifecycle cleanup."""
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return True

    if relative in PROTECTED_RELATIVE_PATHS:
        return True
    if relative.parts and relative.parts[0] in PROTECTED_TOP_LEVEL_DIRS:
        return True
    if len(relative.parts) >= 2 and relative.parts[:2] == ("workspace", "papers"):
        return True
    return False


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def delete_path(path: Path) -> int:
    size = path_size(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
    return size


def collect_pycache_dirs(project_root: Path) -> list[Path]:
    """Collect __pycache__ directories under project_root, skipping protected areas."""
    discovered: list[Path] = []
    git_dir = (project_root / ".git").resolve()

    for candidate in project_root.rglob("__pycache__"):
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if is_never_delete(resolved, project_root):
            continue
        try:
            resolved.relative_to(git_dir)
            continue
        except ValueError:
            pass
        discovered.append(resolved)

    return sorted(set(discovered))
