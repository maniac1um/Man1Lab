"""Read-only resolver contracts for materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ResolvedReference:
    """Normalized workspace reference with provenance."""

    logical_name: str
    path: str
    source_kind: str
    source_id: str
    confidence: float = 1.0


@dataclass(frozen=True)
class MaterializationContext:
    """Application-provided workspace context for materialization."""

    workspace_root: str
    backend_kind: str = "local"


class RepositoryLocationResolver(Protocol):
    """Resolve repository bindings to workspace-relative locations."""

    def resolve_repository(
        self,
        binding_id: str,
        candidate_id: str | None = None,
    ) -> ResolvedReference | None: ...


class AssetLocationResolver(Protocol):
    """Resolve discovery assets to workspace-relative locations."""

    def resolve_asset(self, asset_id: str) -> ResolvedReference | None: ...


class EnvironmentLocationResolver(Protocol):
    """Resolve environment/requirements references."""

    def resolve_environment(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
    ) -> ResolvedReference | None: ...


class EntrypointResolver(Protocol):
    """Resolve verified entry script references for a node."""

    def resolve_entrypoint(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
        *,
        stage_kind: str,
    ) -> ResolvedReference | None: ...
