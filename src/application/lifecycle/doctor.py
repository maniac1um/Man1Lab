"""Environment validation lifecycle service."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from application.version import PLATFORM_VERSION
from configuration.models import AppSettings


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class DoctorReport:
    healthy: bool
    checks: list[DoctorCheck] = field(default_factory=list)


def run_doctor_checks(settings: AppSettings) -> DoctorReport:
    """Validate runtime environment and platform prerequisites."""
    checks: list[DoctorCheck] = []

    checks.append(_check_python_version())
    checks.append(_check_pixi())
    checks.append(_check_git())
    checks.append(_check_github_token())
    checks.append(_check_package_version())
    checks.append(_check_platform_info())

    checks.append(_check_directory("workspace", settings.workspace_root, create=True))
    checks.append(_check_directory("outputs", settings.outputs_dir, create=True))
    checks.append(_check_directory("logs", settings.logs_dir, create=True))
    checks.append(_check_directory("prompts", settings.prompts_dir, create=False))

    checks.append(_check_configuration(settings))
    checks.append(_check_write_permissions(settings))
    checks.append(_check_docling())
    checks.append(_check_mlflow())
    checks.append(_check_internet_connectivity())

    if settings.paper_path.exists():
        checks.append(
            DoctorCheck(
                name="paper",
                status="ok",
                message=f"Configured paper found: {settings.paper_path}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="paper",
                status="warn",
                message=f"Configured paper not found: {settings.paper_path}",
            )
        )

    healthy = all(check.status != "fail" for check in checks)
    return DoctorReport(healthy=healthy, checks=checks)


def _check_directory(name: str, path: Path, *, create: bool) -> DoctorCheck:
    if path.exists() and path.is_dir():
        if os.access(path, os.W_OK):
            return DoctorCheck(name=name, status="ok", message=f"Ready: {path}")
        return DoctorCheck(name=name, status="warn", message=f"Not writable: {path}")
    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return DoctorCheck(name=name, status="ok", message=f"Created: {path}")
        except OSError as exc:
            return DoctorCheck(name=name, status="fail", message=f"Cannot create {path}: {exc}")
    return DoctorCheck(name=name, status="fail", message=f"Missing: {path}")


def _check_python_version() -> DoctorCheck:
    version = platform.python_version()
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        return DoctorCheck(name="Python", status="ok", message=f"Python {version}")
    return DoctorCheck(
        name="Python",
        status="fail",
        message=f"Python {version} — requires 3.10+",
    )


def _check_pixi() -> DoctorCheck:
    if shutil.which("pixi") is None:
        return DoctorCheck(
            name="Pixi",
            status="warn",
            message="Pixi not found (optional; pip install is supported).",
        )
    try:
        result = subprocess.run(
            ["pixi", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        version = result.stdout.strip() or result.stderr.strip() or "installed"
        return DoctorCheck(name="Pixi", status="ok", message=version)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(name="Pixi", status="warn", message=str(exc))


def _check_git() -> DoctorCheck:
    if shutil.which("git") is None:
        return DoctorCheck(name="Git", status="warn", message="Git not found in PATH.")
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        version = result.stdout.strip() or "available"
        return DoctorCheck(name="Git", status="ok", message=version)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(name="Git", status="warn", message=str(exc))


def _check_github_token() -> DoctorCheck:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return DoctorCheck(name="GitHub Token", status="ok", message="GITHUB_TOKEN is set.")
    return DoctorCheck(
        name="GitHub Token",
        status="warn",
        message="GITHUB_TOKEN not set; GitHub discovery may be limited.",
    )


def _check_configuration(settings: AppSettings) -> DoctorCheck:
    if settings.llm.openai_api_key or settings.llm.anthropic_api_key:
        return DoctorCheck(name="Configuration", status="ok", message="LLM credentials configured.")
    return DoctorCheck(
        name="Configuration",
        status="warn",
        message="No LLM API keys configured; mock providers may be used.",
    )


def _check_write_permissions(settings: AppSettings) -> DoctorCheck:
    targets = (settings.workspace_root, settings.outputs_dir, settings.logs_dir)
    blocked = [str(path) for path in targets if path.exists() and not os.access(path, os.W_OK)]
    if blocked:
        return DoctorCheck(
            name="Write Permissions",
            status="fail",
            message=f"Not writable: {', '.join(blocked)}",
        )
    return DoctorCheck(name="Write Permissions", status="ok", message="Workspace paths are writable.")


def _check_docling() -> DoctorCheck:
    if importlib.util.find_spec("docling") is None:
        return DoctorCheck(
            name="Docling",
            status="warn",
            message="Docling not installed; pymupdf fallback may be used.",
        )
    return DoctorCheck(name="Docling", status="ok", message="Docling is available.")


def _check_mlflow() -> DoctorCheck:
    if importlib.util.find_spec("mlflow") is None:
        return DoctorCheck(name="MLflow", status="warn", message="MLflow not installed.")
    return DoctorCheck(name="MLflow", status="ok", message="MLflow is available.")


def _check_internet_connectivity() -> DoctorCheck:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=2):
            return DoctorCheck(name="Internet", status="ok", message="Network connectivity available.")
    except OSError:
        return DoctorCheck(
            name="Internet",
            status="warn",
            message="Could not verify network connectivity.",
        )


def _check_package_version() -> DoctorCheck:
    return DoctorCheck(
        name="Package Version",
        status="ok",
        message=f"man1lab {PLATFORM_VERSION}",
    )


def _check_platform_info() -> DoctorCheck:
    return DoctorCheck(
        name="Platform",
        status="ok",
        message=f"{platform.system()} {platform.release()} ({platform.machine()})",
    )
