"""Atomic filesystem helpers for execution persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from execution.errors import CorruptSnapshotError, PersistenceIOError


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via temp file, flush, and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        data = json.dumps(payload, indent=2, default=str) + "\n"
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        raise PersistenceIOError(f"failed to write {path}: {exc}") from exc
    finally:
        if temp_path.exists() and not path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON object from path."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PersistenceIOError(f"failed to read {path}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorruptSnapshotError(f"corrupt JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CorruptSnapshotError(f"expected JSON object in {path}")
    return payload


def classify_stale_temps(directory: Path) -> tuple[Path, ...]:
    """Return temp files that are safe to remove."""
    if not directory.is_dir():
        return ()
    stale: list[Path] = []
    for temp in directory.glob("*.tmp"):
        final_name = temp.name[:-4] if temp.name.endswith(".tmp") else temp.stem
        final_path = temp.with_name(final_name)
        if final_path.is_file() or not final_path.exists():
            stale.append(temp)
    return tuple(stale)


def cleanup_stale_temps(directory: Path) -> None:
    """Remove leftover .tmp files from interrupted writes."""
    for temp in classify_stale_temps(directory):
        try:
            temp.unlink()
        except OSError:
            continue


def append_jsonl_line(path: Path, record: dict[str, Any]) -> None:
    """Append one complete JSONL record with flush."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, default=str) + "\n"
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise PersistenceIOError(f"failed to append {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read complete JSONL records; ignore partial trailing line."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PersistenceIOError(f"failed to read {path}: {exc}") from exc
    if not text:
        return []
    lines = text.splitlines()
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                continue
            raise CorruptSnapshotError(f"corrupt JSONL in {path} at line {index + 1}")
        if not isinstance(item, dict):
            raise CorruptSnapshotError(f"expected JSON object in {path} at line {index + 1}")
        records.append(item)
    return records
