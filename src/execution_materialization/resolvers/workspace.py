"""Workspace-scoped materialization resolvers."""

from __future__ import annotations

from pathlib import Path

from execution_materialization.ports import MaterializationContext, ResolvedReference
from models.research_resource_discovery import EvidenceRecord, ResearchResourceDiscovery


_EVIDENCE_EXTENSION_KEYS = frozenset(
    {
        "prepared_repo_path",
        "entry_script",
        "eval_script",
        "comparison_script",
        "config_path",
        "output_path",
        "requirements_file",
    }
)


def _normalize_relative(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip().lstrip("/")
    if not normalized:
        raise ValueError("path must be non-empty")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if ".." in parts:
        raise ValueError("path traversal is not allowed")
    return "/".join(parts)


def _within_workspace(workspace_root: Path, candidate: Path) -> bool:
    root = workspace_root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


class WorkspaceEvidenceIndex:
    """Read-only index over discovery evidence extensions."""

    def __init__(self, discovery: ResearchResourceDiscovery) -> None:
        self._by_candidate: dict[str, dict[str, str]] = {}
        for record in discovery.evidence.records:
            self._merge_record(record)

    def _merge_record(self, record: EvidenceRecord) -> None:
        extensions = {
            key: value
            for key, value in record.observed_fact.extensions.items()
            if key in _EVIDENCE_EXTENSION_KEYS and value
        }
        if not extensions:
            return
        bucket = self._by_candidate.setdefault(record.candidate_id, {})
        bucket.update(extensions)

    def extensions_for_candidate(self, candidate_id: str) -> dict[str, str]:
        return dict(self._by_candidate.get(candidate_id, {}))

    def extensions_for_asset(
        self,
        discovery: ResearchResourceDiscovery,
        asset_id: str,
    ) -> dict[str, str]:
        asset = next(
            (item for item in discovery.research_assets.assets if item.asset_id == asset_id),
            None,
        )
        if asset is None:
            return {}
        merged = dict(self.extensions_for_candidate(asset.candidate_id))
        for other in discovery.research_assets.assets:
            if other.asset_id == asset_id:
                continue
            if other.candidate_id == asset.candidate_id:
                merged.update(self.extensions_for_candidate(other.candidate_id))
        return merged


class WorkspaceRepositoryLocationResolver:
    """Resolve prepared repository paths from verified discovery evidence."""

    def __init__(
        self,
        context: MaterializationContext,
        discovery: ResearchResourceDiscovery,
        *,
        bindings_by_id: dict[str, str],
    ) -> None:
        self._workspace_root = Path(context.workspace_root)
        self._discovery = discovery
        self._bindings_by_id = bindings_by_id
        self._evidence = WorkspaceEvidenceIndex(discovery)

    def resolve_repository(
        self,
        binding_id: str,
        candidate_id: str | None = None,
    ) -> ResolvedReference | None:
        resolved_candidate = candidate_id or self._bindings_by_id.get(binding_id)
        if not resolved_candidate:
            return None
        extensions = self._evidence.extensions_for_candidate(resolved_candidate)
        repo_path = extensions.get("prepared_repo_path")
        if not repo_path:
            return None
        normalized = _normalize_relative(repo_path)
        absolute = (self._workspace_root / normalized).resolve()
        if not _within_workspace(self._workspace_root, absolute):
            return None
        return ResolvedReference(
            logical_name="repository",
            path=normalized,
            source_kind="evidence",
            source_id=resolved_candidate,
        )


class WorkspaceAssetLocationResolver:
    """Resolve asset-scoped paths from verified evidence."""

    def __init__(
        self,
        context: MaterializationContext,
        discovery: ResearchResourceDiscovery,
    ) -> None:
        self._workspace_root = Path(context.workspace_root)
        self._discovery = discovery
        self._evidence = WorkspaceEvidenceIndex(discovery)

    def resolve_asset(self, asset_id: str) -> ResolvedReference | None:
        extensions = self._evidence.extensions_for_asset(self._discovery, asset_id)
        for key in (
            "config_path",
            "output_path",
            "entry_script",
            "eval_script",
            "comparison_script",
            "requirements_file",
        ):
            value = extensions.get(key)
            if value:
                normalized = _normalize_relative(value)
                absolute = (self._workspace_root / normalized).resolve()
                if not _within_workspace(self._workspace_root, absolute):
                    return None
                return ResolvedReference(
                    logical_name=key,
                    path=normalized,
                    source_kind="evidence",
                    source_id=asset_id,
                )
        return None


class WorkspaceEnvironmentLocationResolver:
    """Resolve requirements file evidence for environment preparation."""

    def __init__(
        self,
        context: MaterializationContext,
        discovery: ResearchResourceDiscovery,
        *,
        bindings_by_id: dict[str, str],
    ) -> None:
        self._workspace_root = Path(context.workspace_root)
        self._discovery = discovery
        self._bindings_by_id = bindings_by_id
        self._evidence = WorkspaceEvidenceIndex(discovery)

    def resolve_environment(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
    ) -> ResolvedReference | None:
        for asset_id in asset_ids:
            extensions = self._evidence.extensions_for_asset(self._discovery, asset_id)
            requirements = extensions.get("requirements_file")
            if requirements:
                return self._resolved("requirements_file", requirements, asset_id)
        for binding_id in binding_ids:
            candidate_id = self._bindings_by_id.get(binding_id)
            if not candidate_id:
                continue
            extensions = self._evidence.extensions_for_candidate(candidate_id)
            requirements = extensions.get("requirements_file")
            if requirements:
                return self._resolved("requirements_file", requirements, candidate_id)
        return None

    def _resolved(self, logical_name: str, path_text: str, source_id: str) -> ResolvedReference:
        normalized = _normalize_relative(path_text)
        absolute = (self._workspace_root / normalized).resolve()
        if not _within_workspace(self._workspace_root, absolute):
            raise ValueError("resolved path escapes workspace")
        return ResolvedReference(
            logical_name=logical_name,
            path=normalized,
            source_kind="evidence",
            source_id=source_id,
        )


class WorkspaceEntrypointResolver:
    """Resolve entry scripts from verified evidence."""

    def __init__(
        self,
        context: MaterializationContext,
        discovery: ResearchResourceDiscovery,
        *,
        bindings_by_id: dict[str, str],
    ) -> None:
        self._workspace_root = Path(context.workspace_root)
        self._discovery = discovery
        self._bindings_by_id = bindings_by_id
        self._evidence = WorkspaceEvidenceIndex(discovery)

    def resolve_entrypoint(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
        *,
        stage_kind: str,
    ) -> ResolvedReference | None:
        key = {
            "evaluation": "eval_script",
            "comparison": "comparison_script",
        }.get(stage_kind, "entry_script")
        for asset_id in asset_ids:
            extensions = self._evidence.extensions_for_asset(self._discovery, asset_id)
            script = extensions.get(key)
            if script:
                return self._resolved(key, script, asset_id)
        for binding_id in binding_ids:
            candidate_id = self._bindings_by_id.get(binding_id)
            if not candidate_id:
                continue
            extensions = self._evidence.extensions_for_candidate(candidate_id)
            script = extensions.get(key)
            if script:
                return self._resolved(key, script, candidate_id)
        return None

    def resolve_config(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
    ) -> ResolvedReference | None:
        for asset_id in asset_ids:
            extensions = self._evidence.extensions_for_asset(self._discovery, asset_id)
            config_path = extensions.get("config_path")
            if config_path:
                return self._resolved("config_path", config_path, asset_id)
        for binding_id in binding_ids:
            candidate_id = self._bindings_by_id.get(binding_id)
            if not candidate_id:
                continue
            extensions = self._evidence.extensions_for_candidate(candidate_id)
            config_path = extensions.get("config_path")
            if config_path:
                return self._resolved("config_path", config_path, candidate_id)
        return None

    def resolve_output(
        self,
        binding_ids: tuple[str, ...],
        asset_ids: tuple[str, ...],
    ) -> ResolvedReference | None:
        for asset_id in asset_ids:
            extensions = self._evidence.extensions_for_asset(self._discovery, asset_id)
            output_path = extensions.get("output_path")
            if output_path:
                return self._resolved("output_path", output_path, asset_id)
        for binding_id in binding_ids:
            candidate_id = self._bindings_by_id.get(binding_id)
            if not candidate_id:
                continue
            extensions = self._evidence.extensions_for_candidate(candidate_id)
            output_path = extensions.get("output_path")
            if output_path:
                return self._resolved("output_path", output_path, candidate_id)
        return None

    def _resolved(self, logical_name: str, path_text: str, source_id: str) -> ResolvedReference:
        normalized = _normalize_relative(path_text)
        absolute = (self._workspace_root / normalized).resolve()
        if not _within_workspace(self._workspace_root, absolute):
            raise ValueError("resolved path escapes workspace")
        return ResolvedReference(
            logical_name=logical_name,
            path=normalized,
            source_kind="evidence",
            source_id=source_id,
        )
