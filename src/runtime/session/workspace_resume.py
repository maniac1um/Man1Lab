"""Workspace resume utilities — load artifacts and diagnose missing stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.session.workspace import SessionWorkspace
from runtime.session.workspace_store import WorkspaceArtifactStore


@dataclass(frozen=True)
class WorkspaceArtifactStatus:
    """On-disk artifact presence for the session workspace."""

    analysis: bool
    discovery: bool
    planning: bool


@dataclass(frozen=True)
class WorkspaceDiagnostic:
    """Deterministic guidance when a stage cannot proceed."""

    message: str
    recommended_command: str
    missing: tuple[str, ...]


def artifact_status(workspace_root: Path) -> WorkspaceArtifactStatus:
    store = WorkspaceArtifactStore(workspace_root)
    return WorkspaceArtifactStatus(
        analysis=store.has_analysis(),
        discovery=store.has_discovery(),
        planning=store.has_strategy(),
    )


def hydrate_workspace_from_disk(workspace: SessionWorkspace) -> None:
    """Load persisted artifacts into the session workspace when references are absent."""
    if workspace.workspace_root is None:
        return
    store = WorkspaceArtifactStore(workspace.workspace_root)
    if workspace.current_analysis is None:
        workspace.current_analysis = store.load_analysis()
    if workspace.current_discovery is None:
        workspace.current_discovery = store.load_discovery()
    if workspace.current_strategy is None:
        workspace.current_strategy = store.load_strategy()
    if workspace.current_paper is None and workspace.current_analysis is not None:
        source = workspace.current_analysis.metadata.source_path
        if source is not None:
            workspace.current_paper = source


def diagnose_for_analyze(workspace_root: Path) -> WorkspaceDiagnostic | None:
    return None


def diagnose_for_discover(workspace_root: Path) -> WorkspaceDiagnostic | None:
    status = artifact_status(workspace_root)
    if status.analysis:
        return None
    return WorkspaceDiagnostic(
        message="Analysis artifact is missing from the workspace.",
        recommended_command="analyze <paper.pdf>",
        missing=("analysis",),
    )


def diagnose_for_plan(workspace_root: Path) -> WorkspaceDiagnostic | None:
    status = artifact_status(workspace_root)
    missing: list[str] = []
    if not status.analysis:
        missing.append("analysis")
    if not status.discovery:
        missing.append("discovery")
    if not missing:
        return None
    if "analysis" in missing:
        return WorkspaceDiagnostic(
            message="Analysis artifact is missing from the workspace.",
            recommended_command="analyze <paper.pdf>",
            missing=tuple(missing),
        )
    return WorkspaceDiagnostic(
        message="Discovery artifact is missing from the workspace.",
        recommended_command="discover",
        missing=tuple(missing),
    )


def diagnose_for_execute(workspace_root: Path) -> WorkspaceDiagnostic | None:
    store = WorkspaceArtifactStore(workspace_root)
    if store.has_execution_graph():
        return None
    status = artifact_status(workspace_root)
    missing: list[str] = []
    if not status.analysis:
        missing.append("analysis")
    if not status.discovery:
        missing.append("discovery")
    if not status.planning:
        missing.append("planning")
    missing.append("execution_graph")
    if "analysis" in missing:
        return WorkspaceDiagnostic(
            message="Execution graph is missing from the workspace.",
            recommended_command="analyze <paper.pdf>",
            missing=tuple(missing),
        )
    if "discovery" in missing:
        return WorkspaceDiagnostic(
            message="Execution graph is missing from the workspace.",
            recommended_command="discover",
            missing=tuple(missing),
        )
    if "planning" in missing:
        return WorkspaceDiagnostic(
            message="Execution graph is missing from the workspace.",
            recommended_command="plan",
            missing=tuple(missing),
        )
    return WorkspaceDiagnostic(
        message="Execution graph is missing from the workspace.",
        recommended_command="plan",
        missing=tuple(missing),
    )


def diagnose_for_plan_all(workspace_root: Path, *, has_paper: bool) -> WorkspaceDiagnostic | None:
    if has_paper:
        return None
    status = artifact_status(workspace_root)
    if status.analysis:
        return None
    return WorkspaceDiagnostic(
        message="No paper in session and no persisted analysis found.",
        recommended_command="analyze <paper.pdf>",
        missing=("paper", "analysis"),
    )


def render_diagnostic(diagnostic: WorkspaceDiagnostic) -> str:
    lines = [
        diagnostic.message,
        f"Missing: {', '.join(diagnostic.missing)}",
        f"Recommended: {diagnostic.recommended_command}",
    ]
    return "\n".join(lines)
