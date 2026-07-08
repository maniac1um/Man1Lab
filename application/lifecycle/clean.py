"""Workspace cleanup lifecycle service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from application.lifecycle.common import (
    collect_pycache_dirs,
    delete_path,
    is_never_delete,
    path_size,
    resolve_project_path,
)
from configuration.models import AppSettings


class CleanPolicy(str, Enum):
    SAFE = "safe"
    ALL = "all"


@dataclass(frozen=True)
class CleanupReport:
    policy: CleanPolicy
    deleted_paths: list[Path] = field(default_factory=list)
    skipped_paths: list[Path] = field(default_factory=list)
    missing_paths: list[Path] = field(default_factory=list)
    planned_paths: list[Path] = field(default_factory=list)
    bytes_removed: int = 0
    dry_run: bool = False
    successful: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def clean_workspace(
    settings: AppSettings,
    *,
    policy: CleanPolicy = CleanPolicy.SAFE,
    dry_run: bool = False,
    project_root: Path | None = None,
) -> CleanupReport:
    """Remove regeneratable workspace artifacts according to cleanup policy."""
    root = (project_root or Path.cwd()).resolve()
    deleted_paths: list[Path] = []
    skipped_paths: list[Path] = []
    missing_paths: list[Path] = []
    planned_paths: list[Path] = []
    warnings: list[str] = []
    errors: list[str] = []
    bytes_removed = 0

    targets = _cleanup_targets(settings, root, policy)
    targets.extend(collect_pycache_dirs(root))
    targets = _dedupe_paths(targets)

    for target in targets:
        if is_never_delete(target, root):
            skipped_paths.append(target)
            continue

        if not target.exists():
            missing_paths.append(target)
            continue

        planned_paths.append(target)
        reclaimable = path_size(target)

        if dry_run:
            bytes_removed += reclaimable
            continue

        try:
            removed = delete_path(target)
            deleted_paths.append(target)
            bytes_removed += removed
        except OSError as exc:
            errors.append(f"Failed to remove {target}: {exc}")

    successful = not errors
    return CleanupReport(
        policy=policy,
        deleted_paths=deleted_paths,
        skipped_paths=skipped_paths,
        missing_paths=missing_paths,
        planned_paths=planned_paths,
        bytes_removed=bytes_removed,
        dry_run=dry_run,
        successful=successful,
        warnings=warnings,
        errors=errors,
    )


def _cleanup_targets(settings: AppSettings, project_root: Path, policy: CleanPolicy) -> list[Path]:
    targets = [
        resolve_project_path(project_root, settings.outputs_dir),
        resolve_project_path(project_root, settings.logs_dir),
        project_root / "mlruns",
        project_root / ".pytest_cache",
        project_root / ".mypy_cache",
        project_root / ".ruff_cache",
        project_root / "workspace" / "cache",
        project_root / "workspace" / "tmp",
    ]

    if policy is CleanPolicy.ALL:
        targets.extend(
            [
                resolve_project_path(project_root, settings.workspace_root),
                project_root / "workspace" / "artifacts",
            ]
        )

    return targets


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered
