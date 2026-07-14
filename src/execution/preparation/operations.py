"""Safe local preparation operations and receipt generation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from models.execution_preparation import PreparationOperation, PreparationRequest


def execute_preparation(request: PreparationRequest, *, workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    target = _workspace_path(root, request.target_path)
    receipt = _workspace_path(root, request.receipt_path)
    if request.operation is PreparationOperation.REPOSITORY:
        details = _prepare_repository(request, root, target)
    elif request.operation in {PreparationOperation.DATASET, PreparationOperation.CHECKPOINT}:
        details = _prepare_asset(request, root, target)
    elif request.operation is PreparationOperation.CONFIGURATION:
        details = _prepare_configuration(request, root, target)
    else:  # pragma: no cover - enum validation protects this branch
        raise ValueError(f"unsupported preparation operation: {request.operation}")
    payload = {
        "schema_version": "1.0",
        "operation": request.operation.value,
        "source_kind": request.source_kind,
        "source_uri": _redacted_uri(request.source_uri),
        "revision": request.revision,
        "target_path": request.target_path,
        "checksum_sha256": details.get("checksum_sha256", ""),
        "resolved_revision": details.get("resolved_revision", ""),
        "template_version": "1.0",
        "completed_at": datetime.now(UTC).isoformat(),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(receipt, payload)
    return receipt


def _prepare_repository(request: PreparationRequest, root: Path, target: Path) -> dict[str, str]:
    if request.source_kind == "workspace":
        if not target.is_dir():
            raise FileNotFoundError(f"prepared repository not found: {request.target_path}")
    elif request.source_kind == "git":
        if not request.source_uri:
            raise ValueError("Git repository source_uri is required")
        if target.exists():
            if not (target / ".git").is_dir():
                raise FileExistsError(f"repository target already exists and is not Git: {request.target_path}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent) as temp_dir:
                staged = Path(temp_dir) / "repository"
                subprocess.run(
                    ["git", "clone", "--", request.source_uri, str(staged)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if request.revision:
                    subprocess.run(
                        ["git", "-C", str(staged), "checkout", "--detach", request.revision],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                os.replace(staged, target)
    else:
        raise ValueError(f"unsupported repository source kind: {request.source_kind}")

    for relative in request.required_paths:
        required = _descendant(target, relative)
        if not required.exists():
            raise FileNotFoundError(f"required repository path missing: {relative}")
    revision = ""
    if (target / ".git").exists():
        completed = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        revision = completed.stdout.strip()
        if request.revision:
            expected = subprocess.run(
                ["git", "-C", str(target), "rev-parse", request.revision],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            if revision != expected:
                raise ValueError("prepared repository revision mismatch")
    return {"resolved_revision": revision}


def _prepare_asset(request: PreparationRequest, root: Path, target: Path) -> dict[str, str]:
    if request.source_kind == "workspace":
        if not target.exists():
            raise FileNotFoundError(f"prepared asset not found: {request.target_path}")
        actual = _digest_path(target)
        if request.checksum_sha256 and actual.lower() != request.checksum_sha256.lower():
            raise ValueError("prepared asset checksum mismatch")
    elif request.source_kind == "https":
        if not request.source_uri.lower().startswith("https://"):
            raise ValueError("only HTTPS asset downloads are supported")
        if target.exists():
            raise FileExistsError(f"asset target already exists: {request.target_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as temp_dir:
            downloaded = Path(temp_dir) / "download"
            with urllib.request.urlopen(request.source_uri, timeout=60) as response, downloaded.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            _verify_checksum(downloaded, request.checksum_sha256)
            if request.archive_format:
                staged = Path(temp_dir) / "extracted"
                staged.mkdir()
                _extract_archive(downloaded, staged, request.archive_format)
                os.replace(staged, target)
            else:
                os.replace(downloaded, target)
    else:
        raise ValueError(f"unsupported asset source kind: {request.source_kind}")
    return {"checksum_sha256": _digest_path(target)}


def _prepare_configuration(request: PreparationRequest, root: Path, target: Path) -> dict[str, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if request.source_kind == "workspace":
        source = _workspace_path(root, request.source_path or request.target_path)
        if not source.is_file():
            raise FileNotFoundError(f"configuration source not found: {request.source_path}")
        if source != target:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temp = Path(handle.name)
            try:
                shutil.copyfile(source, temp)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
    elif request.source_kind == "deterministic_render":
        if request.configuration_format != "json":
            raise ValueError("only deterministic JSON rendering is supported")
        _atomic_json(target, request.configuration_values)
    else:
        raise ValueError(f"unsupported configuration source kind: {request.source_kind}")
    return {"checksum_sha256": _sha256_file(target)}


def _extract_archive(source: Path, destination: Path, archive_format: str) -> None:
    normalized = archive_format.lower()
    if normalized == "zip":
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                _safe_archive_member(destination, member.filename)
            archive.extractall(destination)
        return
    if normalized in {"tar", "tar.gz", "tgz"}:
        mode = "r:gz" if normalized in {"tar.gz", "tgz"} else "r:"
        with tarfile.open(source, mode) as archive:
            for member in archive.getmembers():
                _safe_archive_member(destination, member.name)
                if member.issym() or member.islnk():
                    raise ValueError("archive links are not allowed")
            archive.extractall(destination, filter="data")
        return
    raise ValueError(f"unsupported archive format: {archive_format}")


def _safe_archive_member(root: Path, name: str) -> None:
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"archive member escapes destination: {name}") from exc


def _workspace_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {relative}") from exc
    return path


def _descendant(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"required path escapes repository: {relative}") from exc
    return candidate


def _verify_checksum(path: Path, expected: str) -> None:
    if expected and _sha256_file(path).lower() != expected.lower():
        raise ValueError("download checksum mismatch")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_path(path: Path) -> str:
    if path.is_file():
        return _sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(_sha256_file(item).encode("ascii"))
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _redacted_uri(uri: str) -> str:
    if "@" in uri and "://" in uri:
        scheme, rest = uri.split("://", 1)
        return f"{scheme}://{rest.split('@', 1)[-1]}"
    return uri
