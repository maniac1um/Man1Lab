"""Deterministically project Discovery facts into typed execution evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from models.execution_evidence import (
    CheckpointExecutionEvidence,
    ConfigurationExecutionEvidence,
    ConfigurationMode,
    DatasetExecutionEvidence,
    ExecutionEvidenceBundle,
    ExecutionEvidenceIssue,
    PreparationSourceKind,
    RepositoryExecutionEvidence,
)
from models.research_resource_discovery import (
    EvidencePolarity,
    FetchStatus,
    ResearchResourceDiscovery,
    ResourceType,
)


def project_execution_evidence(
    discovery: ResearchResourceDiscovery,
    *,
    created_at: datetime | None = None,
) -> ExecutionEvidenceBundle:
    """Create a typed, side-effect-free projection of verified Discovery facts."""
    evidence_by_candidate: dict[str, dict[str, str]] = {}
    evidence_ids: dict[str, list[str]] = {}
    issues: list[ExecutionEvidenceIssue] = []
    conflicted: set[tuple[str, str]] = set()
    for record in discovery.evidence.records:
        if (
            record.polarity is not EvidencePolarity.SUPPORTS
            or record.evidence_source.fetch_status is not FetchStatus.SUCCESS
        ):
            continue
        values = evidence_by_candidate.setdefault(record.candidate_id, {})
        for key, value in record.observed_fact.extensions.items():
            conflict_key = (record.candidate_id, key)
            if conflict_key in conflicted:
                continue
            existing = values.get(key)
            if existing is not None and existing != value:
                values.pop(key, None)
                conflicted.add(conflict_key)
                issues.append(
                    ExecutionEvidenceIssue(
                        code="conflicting_execution_evidence",
                        message=f"conflicting verified values for {key}",
                        candidate_id=record.candidate_id,
                        field=key,
                    )
                )
                continue
            values[key] = value
        evidence_ids.setdefault(record.candidate_id, []).append(record.evidence_id)

    repositories: list[RepositoryExecutionEvidence] = []
    datasets: list[DatasetExecutionEvidence] = []
    checkpoints: list[CheckpointExecutionEvidence] = []
    configurations: list[ConfigurationExecutionEvidence] = []

    for candidate in sorted(discovery.candidate_resources.candidates, key=lambda item: item.candidate_id):
        facts = dict(candidate.extensions)
        facts.update(evidence_by_candidate.get(candidate.candidate_id, {}))
        ids = tuple(sorted(evidence_ids.get(candidate.candidate_id, ())))
        source_uri = facts.get("source_uri") or facts.get("repository_uri") or candidate.url or candidate.identity.normalized_url

        if candidate.resource_type in {ResourceType.OFFICIAL_REPOSITORY, ResourceType.COMMUNITY_REPOSITORY}:
            target = facts.get("prepared_repo_path") or facts.get("target_path") or f"repositories/{candidate.candidate_id}"
            source_kind = PreparationSourceKind.WORKSPACE if facts.get("prepared_repo_path") else PreparationSourceKind.GIT
            if source_kind is PreparationSourceKind.GIT and not _is_git_uri(source_uri):
                issues.append(ExecutionEvidenceIssue(code="unsupported_repository_source", message="repository requires a supported Git URI", candidate_id=candidate.candidate_id, field="source_uri"))
            repositories.append(
                RepositoryExecutionEvidence(
                    candidate_id=candidate.candidate_id,
                    source_kind=source_kind,
                    source_uri=source_uri,
                    revision=facts.get("revision") or facts.get("commit_sha", ""),
                    target_path=target,
                    entry_script=facts.get("entry_script", ""),
                    eval_script=facts.get("eval_script", ""),
                    comparison_script=facts.get("comparison_script", ""),
                    requirements_file=facts.get("requirements_file", ""),
                    config_path=facts.get("config_path", ""),
                    output_path=facts.get("output_path", ""),
                    manifest_paths=tuple(filter(None, facts.get("manifest_paths", "").split(","))),
                    evidence_ids=ids,
                    auth_reference=facts.get("auth_reference", ""),
                )
            )
        elif candidate.resource_type in {
            ResourceType.HUGGINGFACE_DATASET,
            ResourceType.DATASET_PORTAL,
            ResourceType.FIGSHARE_DATASET,
            ResourceType.ZENODO_RECORD,
        }:
            descriptor = _dataset_descriptor(candidate.candidate_id, source_uri, facts, ids)
            if descriptor is None:
                issues.append(ExecutionEvidenceIssue(code="missing_dataset_source", message="dataset source or target path is missing", candidate_id=candidate.candidate_id))
            else:
                datasets.append(descriptor)
        elif candidate.resource_type is ResourceType.CHECKPOINT:
            descriptor = _checkpoint_descriptor(candidate.candidate_id, source_uri, facts, ids)
            if descriptor is None:
                issues.append(ExecutionEvidenceIssue(code="missing_checkpoint_source", message="checkpoint source or target path is missing", candidate_id=candidate.candidate_id))
            else:
                checkpoints.append(descriptor)
        elif candidate.resource_type is ResourceType.CONFIGURATION:
            target = facts.get("config_path") or facts.get("target_path")
            if target:
                mode_text = facts.get("configuration_mode", ConfigurationMode.EXISTING_FILE.value)
                try:
                    mode = ConfigurationMode(mode_text)
                except ValueError:
                    issues.append(
                        ExecutionEvidenceIssue(
                            code="unsupported_configuration_mode",
                            message=f"unsupported configuration mode: {mode_text}",
                            candidate_id=candidate.candidate_id,
                            field="configuration_mode",
                        )
                    )
                    continue
                values: dict[str, str | int | float | bool] = {}
                if mode is ConfigurationMode.DETERMINISTIC_RENDER:
                    try:
                        decoded = json.loads(facts.get("configuration_values_json", "{}"))
                    except json.JSONDecodeError:
                        decoded = None
                    if not isinstance(decoded, dict) or not all(
                        isinstance(key, str) and isinstance(value, (str, int, float, bool))
                        for key, value in (decoded or {}).items()
                    ):
                        issues.append(
                            ExecutionEvidenceIssue(
                                code="invalid_configuration_values",
                                message="deterministic configuration values must be a scalar JSON object",
                                candidate_id=candidate.candidate_id,
                                field="configuration_values_json",
                            )
                        )
                        continue
                    values = decoded
                configurations.append(
                    ConfigurationExecutionEvidence(
                        candidate_id=candidate.candidate_id,
                        mode=mode,
                        source_path=facts.get("config_source_path", target),
                        target_path=target,
                        format=facts.get("config_format", "json"),
                        values=values,
                        evidence_ids=ids,
                    )
                )

    timestamp = created_at or datetime.now(UTC)
    fingerprint_payload = {
        "discovery_id": discovery.metadata.discovery_id,
        "repositories": [item.model_dump(mode="json") for item in repositories],
        "datasets": [item.model_dump(mode="json") for item in datasets],
        "checkpoints": [item.model_dump(mode="json") for item in checkpoints],
        "configurations": [item.model_dump(mode="json") for item in configurations],
    }
    digest = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return ExecutionEvidenceBundle(
        bundle_id=f"evidence-{digest}",
        discovery_id=discovery.metadata.discovery_id,
        analysis_content_hash=discovery.analysis_reference.analysis_content_hash,
        created_at=timestamp,
        repositories=tuple(repositories),
        datasets=tuple(datasets),
        checkpoints=tuple(checkpoints),
        configurations=tuple(configurations),
        issues=tuple(issues),
    )


def _dataset_descriptor(candidate_id: str, uri: str, facts: dict[str, str], ids: tuple[str, ...]) -> DatasetExecutionEvidence | None:
    target = facts.get("dataset_path") or facts.get("target_path")
    if not target:
        return None
    kind = PreparationSourceKind.WORKSPACE if facts.get("dataset_path") else PreparationSourceKind.HTTPS
    if kind is PreparationSourceKind.HTTPS and not uri.lower().startswith("https://"):
        return None
    return DatasetExecutionEvidence(candidate_id=candidate_id, source_kind=kind, source_uri=uri, revision=facts.get("revision", ""), target_path=target, checksum_sha256=facts.get("checksum_sha256", ""), archive_format=facts.get("archive_format", ""), evidence_ids=ids, auth_reference=facts.get("auth_reference", ""))


def _checkpoint_descriptor(candidate_id: str, uri: str, facts: dict[str, str], ids: tuple[str, ...]) -> CheckpointExecutionEvidence | None:
    target = facts.get("checkpoint_path") or facts.get("target_path")
    if not target:
        return None
    kind = PreparationSourceKind.WORKSPACE if facts.get("checkpoint_path") else PreparationSourceKind.HTTPS
    if kind is PreparationSourceKind.HTTPS and not uri.lower().startswith("https://"):
        return None
    return CheckpointExecutionEvidence(candidate_id=candidate_id, source_kind=kind, source_uri=uri, revision=facts.get("revision", ""), target_path=target, checksum_sha256=facts.get("checksum_sha256", ""), archive_format=facts.get("archive_format", ""), format=facts.get("checkpoint_format", ""), evidence_ids=ids, auth_reference=facts.get("auth_reference", ""))


def _is_git_uri(uri: str) -> bool:
    lowered = uri.lower()
    return lowered.startswith("https://") or lowered.startswith("ssh://") or lowered.startswith("git@")
