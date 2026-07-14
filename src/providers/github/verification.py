"""GitHub VerificationProvider — deterministic checks on collected evidence only."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DimensionResult,
    DiscoveryProvider,
    EvidenceRecord,
    EvidenceType,
    ProviderInvocationStatus,
    ProviderRecord,
    RepositoryCandidate,
    VerificationDimension,
    VerificationDimensionName,
    VerificationRecord,
    VerificationStatus,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from services.discovery.candidate_merge import normalize_url

_PROVIDER_NAME = "github_verification"
_PROVIDER_VERSION = "1.0.0"
_CONFIDENCE_PASS = "1.0"
_CONFIDENCE_PARTIAL = "0.6"
_CONFIDENCE_FAIL = "1.0"
_CONFIDENCE_SKIPPED = "0.0"


@dataclass(frozen=True)
class _DimensionCheck:
    check_name: str
    dimension: VerificationDimensionName
    result: DimensionResult
    summary: str
    evidence_ids: tuple[str, ...]
    blocking: bool = False


class GitHubVerificationProvider:
    """Verify GitHub candidates using existing GitHub evidence only — no network."""

    def verify(
        self,
        analysis: PaperReproductionAnalysis,
        collection_result: CollectionProviderResult,
        evidence_result: EvidenceProviderResult,
    ) -> VerificationProviderResult:
        del analysis
        now = datetime.now(UTC)
        evidence_by_candidate = _group_evidence(evidence_result.evidence_records)
        github_candidates = _github_candidates(collection_result.candidates)

        if not github_candidates:
            return VerificationProviderResult(
                provider_outcomes=[
                    ProviderRecord(
                        provider_name=_PROVIDER_NAME,
                        provider_version=_PROVIDER_VERSION,
                        invoked_at=now,
                        status=ProviderInvocationStatus.SKIPPED,
                    )
                ]
            )

        records: list[VerificationRecord] = []
        partial_count = 0
        failed_count = 0

        for candidate in github_candidates:
            record = _verify_candidate(
                candidate,
                evidence_by_candidate.get(candidate.candidate_id, []),
                verified_at=now,
            )
            records.append(record)
            if record.status == VerificationStatus.PARTIAL:
                partial_count += 1
            elif record.status == VerificationStatus.FAIL:
                failed_count += 1

        status = _provider_status(
            candidate_count=len(github_candidates),
            partial_count=partial_count,
            failed_count=failed_count,
        )
        return VerificationProviderResult(
            verification_records=records,
            provider_outcomes=[
                ProviderRecord(
                    provider_name=_PROVIDER_NAME,
                    provider_version=_PROVIDER_VERSION,
                    invoked_at=now,
                    status=status,
                    candidates_contributed=len(records),
                )
            ],
        )


def _github_candidates(candidates: list[RepositoryCandidate]) -> list[RepositoryCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.provider == DiscoveryProvider.GITHUB
        or candidate.identity.provider == DiscoveryProvider.GITHUB
    ]


def _group_evidence(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    grouped: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        grouped.setdefault(record.candidate_id, []).append(record)
    return grouped


def _github_metadata_evidence(records: list[EvidenceRecord]) -> EvidenceRecord | None:
    for record in records:
        if (
            record.evidence_type == EvidenceType.METADATA_EXTRACT
            and record.evidence_source.provider_name == "github"
        ):
            return record
    return None


def _github_readme_evidence(records: list[EvidenceRecord]) -> EvidenceRecord | None:
    for record in records:
        if (
            record.evidence_type == EvidenceType.README_CLAIM
            and record.evidence_source.provider_name == "github"
        ):
            return record
    return None


def _verify_candidate(
    candidate: RepositoryCandidate,
    evidence_records: list[EvidenceRecord],
    *,
    verified_at: datetime,
) -> VerificationRecord:
    metadata = _github_metadata_evidence(evidence_records)
    readme = _github_readme_evidence(evidence_records)

    if metadata is None:
        skipped_dimension = VerificationDimension(
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.FAIL,
            summary="Repository metadata evidence missing.",
            evidence_ids=[],
            details={
                "check": "repository_exists",
                "verification_reason": "repository metadata missing",
                "confidence": _CONFIDENCE_FAIL,
            },
        )
        return VerificationRecord(
            verification_id=_verification_id(candidate.candidate_id),
            candidate_id=candidate.candidate_id,
            status=VerificationStatus.FAIL,
            dimensions=[skipped_dimension],
            blocking_failures=["repository metadata missing"],
            verified_at=verified_at,
            verifier_version=_PROVIDER_VERSION,
        )

    metadata_fields = metadata.observed_fact.fields
    metadata_ids = (metadata.evidence_id,)
    readme_ids = (readme.evidence_id,) if readme is not None else ()

    checks = _build_checks(candidate, metadata_fields, metadata_ids, readme, readme_ids)
    dimensions = [_to_dimension(check) for check in checks]
    blocking_failures = [check.summary for check in checks if check.blocking and check.result == DimensionResult.FAIL]
    overall_status = _aggregate_status(checks)
    overall_confidence = _aggregate_confidence(overall_status)

    dimensions_with_overall = [
        dimension.model_copy(
            update={
                "details": {
                    **dimension.details,
                    "overall_status": overall_status.value,
                    "overall_confidence": overall_confidence,
                    "provider": _PROVIDER_NAME,
                }
            }
        )
        for dimension in dimensions
    ]

    return VerificationRecord(
        verification_id=_verification_id(candidate.candidate_id),
        candidate_id=candidate.candidate_id,
        status=overall_status,
        dimensions=dimensions_with_overall,
        blocking_failures=blocking_failures,
        verified_at=verified_at,
        verifier_version=_PROVIDER_VERSION,
    )


def _build_checks(
    candidate: RepositoryCandidate,
    metadata_fields: dict,
    metadata_ids: tuple[str, ...],
    readme: EvidenceRecord | None,
    readme_ids: tuple[str, ...],
) -> list[_DimensionCheck]:
    repository_url = str(metadata_fields.get("repository_url", ""))
    full_name = str(metadata_fields.get("full_name", ""))
    archived = _as_bool(metadata_fields.get("archived", False))
    license_value = str(metadata_fields.get("license", "")).strip()
    description = str(metadata_fields.get("description", "")).strip()
    topics = str(metadata_fields.get("topics", "")).strip()
    homepage = str(metadata_fields.get("homepage", "")).strip()
    default_branch = str(metadata_fields.get("default_branch", "")).strip()
    source_url = candidate.extensions.get("source_url", candidate.url)

    identity_match = _identity_matches(candidate, full_name)
    paper_match = _paper_url_matches(candidate, repository_url, source_url)

    checks = [
        _DimensionCheck(
            check_name="repository_exists",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS,
            summary="Repository metadata evidence present.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="repository_accessible",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS,
            summary="Repository metadata collected from GitHub API.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="paper_url_match",
            dimension=VerificationDimensionName.PAPER_MATCH,
            result=DimensionResult.PASS if paper_match else DimensionResult.FAIL,
            summary="Paper URL matches repository metadata."
            if paper_match
            else "Paper URL does not match repository metadata.",
            evidence_ids=metadata_ids,
            blocking=False,
        ),
        _DimensionCheck(
            check_name="repository_identity_match",
            dimension=VerificationDimensionName.IDENTITY_MATCH,
            result=DimensionResult.PASS if identity_match else DimensionResult.FAIL,
            summary="Repository identity matches candidate binding."
            if identity_match
            else "Repository identity does not match candidate binding.",
            evidence_ids=metadata_ids,
            blocking=not identity_match,
        ),
        _DimensionCheck(
            check_name="readme_present",
            dimension=VerificationDimensionName.ARTIFACT_AVAILABILITY,
            result=DimensionResult.PASS if readme is not None else DimensionResult.PARTIAL,
            summary="README evidence present." if readme is not None else "README evidence absent.",
            evidence_ids=readme_ids,
        ),
        _DimensionCheck(
            check_name="repository_archived",
            dimension=VerificationDimensionName.SCOPE_ALIGNMENT,
            result=DimensionResult.FAIL if archived else DimensionResult.PASS,
            summary="Repository is archived." if archived else "Repository is not archived.",
            evidence_ids=metadata_ids,
            blocking=archived,
        ),
        _DimensionCheck(
            check_name="repository_license_present",
            dimension=VerificationDimensionName.LICENSE,
            result=DimensionResult.PASS if license_value else DimensionResult.PARTIAL,
            summary="Repository license present." if license_value else "Repository license missing.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="repository_description_present",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS if description else DimensionResult.PARTIAL,
            summary="Repository description present."
            if description
            else "Repository description missing.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="repository_topics_present",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS if topics else DimensionResult.PARTIAL,
            summary="Repository topics present." if topics else "Repository topics missing.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="repository_homepage_present",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS if homepage else DimensionResult.PARTIAL,
            summary="Repository homepage present." if homepage else "Repository homepage missing.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="default_branch_present",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=DimensionResult.PASS if default_branch else DimensionResult.PARTIAL,
            summary="Default branch present." if default_branch else "Default branch missing.",
            evidence_ids=metadata_ids,
        ),
        _DimensionCheck(
            check_name="repository_metadata_completeness",
            dimension=VerificationDimensionName.REPOSITORY_HEALTH,
            result=_metadata_completeness_result(
                repository_url,
                full_name,
                description,
                license_value,
                topics,
                homepage,
                default_branch,
            ),
            summary=_metadata_completeness_summary(
                repository_url,
                full_name,
                description,
                license_value,
                topics,
                homepage,
                default_branch,
            ),
            evidence_ids=metadata_ids,
        ),
    ]
    return checks


def _to_dimension(check: _DimensionCheck) -> VerificationDimension:
    confidence = _confidence_for_result(check.result)
    return VerificationDimension(
        dimension=check.dimension,
        result=check.result,
        summary=check.summary,
        evidence_ids=list(check.evidence_ids),
        details={
            "check": check.check_name,
            "verification_reason": check.summary,
            "confidence": confidence,
        },
    )


def _metadata_completeness_result(
    repository_url: str,
    full_name: str,
    description: str,
    license_value: str,
    topics: str,
    homepage: str,
    default_branch: str,
) -> DimensionResult:
    required_present = bool(repository_url and full_name and default_branch)
    optional_present = sum(
        1 for value in (description, license_value, topics, homepage) if value
    )
    if required_present and optional_present >= 2:
        return DimensionResult.PASS
    if required_present:
        return DimensionResult.PARTIAL
    return DimensionResult.FAIL


def _metadata_completeness_summary(
    repository_url: str,
    full_name: str,
    description: str,
    license_value: str,
    topics: str,
    homepage: str,
    default_branch: str,
) -> str:
    result = _metadata_completeness_result(
        repository_url,
        full_name,
        description,
        license_value,
        topics,
        homepage,
        default_branch,
    )
    if result == DimensionResult.PASS:
        return "Repository metadata completeness sufficient."
    if result == DimensionResult.PARTIAL:
        return "Repository metadata partially complete."
    return "Repository metadata incomplete."


def _aggregate_status(checks: list[_DimensionCheck]) -> VerificationStatus:
    if any(check.result == DimensionResult.FAIL and check.blocking for check in checks):
        return VerificationStatus.FAIL
    if any(check.result == DimensionResult.FAIL for check in checks):
        return VerificationStatus.FAIL
    if any(check.result == DimensionResult.PARTIAL for check in checks):
        return VerificationStatus.PARTIAL
    return VerificationStatus.PASS


def _aggregate_confidence(status: VerificationStatus) -> str:
    if status == VerificationStatus.PASS:
        return _CONFIDENCE_PASS
    if status == VerificationStatus.PARTIAL:
        return _CONFIDENCE_PARTIAL
    if status == VerificationStatus.SKIPPED:
        return _CONFIDENCE_SKIPPED
    return _CONFIDENCE_FAIL


def _confidence_for_result(result: DimensionResult) -> str:
    if result == DimensionResult.PASS:
        return _CONFIDENCE_PASS
    if result == DimensionResult.PARTIAL:
        return _CONFIDENCE_PARTIAL
    if result == DimensionResult.FAIL:
        return _CONFIDENCE_FAIL
    return _CONFIDENCE_SKIPPED


def _identity_matches(candidate: RepositoryCandidate, full_name: str) -> bool:
    native_id = candidate.identity.provider_native_id.strip().casefold()
    return bool(native_id and full_name.casefold() == native_id)


def _paper_url_matches(
    candidate: RepositoryCandidate,
    repository_url: str,
    source_url: str,
) -> bool:
    candidate_url = normalize_url(candidate.url)
    metadata_url = normalize_url(repository_url)
    paper_url = normalize_url(source_url)
    urls = {url for url in (candidate_url, paper_url) if url}
    return bool(metadata_url and urls and metadata_url in urls)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _provider_status(
    *,
    candidate_count: int,
    partial_count: int,
    failed_count: int,
) -> ProviderInvocationStatus:
    if candidate_count == 0:
        return ProviderInvocationStatus.SKIPPED
    if failed_count == candidate_count:
        return ProviderInvocationStatus.FAILED
    if failed_count > 0 or partial_count > 0:
        return ProviderInvocationStatus.PARTIAL
    return ProviderInvocationStatus.SUCCESS


def _verification_id(candidate_id: str) -> str:
    digest = hashlib.sha256(f"github:{candidate_id}".encode("utf-8")).hexdigest()[:16]
    return f"github-verification-{digest}"
