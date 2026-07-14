"""Verification merge policy for VerificationService.

Merge strategy (append-only):
1. Deduplicate by candidate_id (one canonical verification record per candidate).
2. Keep the first verification_id.
3. Merge dimensions by dimension name; union evidence_ids and details.
4. Union blocking_failures without duplicates.
5. Prefer stronger aggregate status (pass > partial > skipped > fail > error).
6. Never discard valid verification records for distinct candidates.
"""

from __future__ import annotations

from models.research_resource_discovery import (
    VerificationDimension,
    VerificationRecord,
    VerificationStatus,
)

_STATUS_PRECEDENCE = {
    VerificationStatus.PASS: 5,
    VerificationStatus.PARTIAL: 4,
    VerificationStatus.SKIPPED: 3,
    VerificationStatus.FAIL: 2,
    VerificationStatus.ERROR: 1,
}


def deduplication_key(record: VerificationRecord) -> str:
    return record.candidate_id


def merge_verification(
    existing: list[VerificationRecord],
    incoming: list[VerificationRecord],
) -> list[VerificationRecord]:
    """Merge incoming verification records without discarding unique candidates."""
    merged = list(existing)
    index_by_key = {deduplication_key(record): index for index, record in enumerate(merged)}

    for record in incoming:
        key = deduplication_key(record)
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(record)
            continue

        keeper_index = index_by_key[key]
        keeper = merged[keeper_index]
        merged[keeper_index] = _merge_duplicate(keeper, record)

    return merged


def _merge_duplicate(keeper: VerificationRecord, duplicate: VerificationRecord) -> VerificationRecord:
    provider_name = duplicate.verifier_version or "unknown"
    merged_dimensions = _merge_dimensions(keeper.dimensions, duplicate.dimensions, provider_name)
    blocking_failures = list(keeper.blocking_failures)
    for failure in duplicate.blocking_failures:
        if failure not in blocking_failures:
            blocking_failures.append(failure)

    status = _prefer_status(keeper.status, duplicate.status)
    return keeper.model_copy(
        update={
            "status": status,
            "dimensions": merged_dimensions,
            "blocking_failures": blocking_failures,
        }
    )


def _merge_dimensions(
    keeper_dims: list[VerificationDimension],
    duplicate_dims: list[VerificationDimension],
    provider_name: str,
) -> list[VerificationDimension]:
    by_name = {dimension.dimension: dimension for dimension in keeper_dims}
    for dimension in duplicate_dims:
        existing = by_name.get(dimension.dimension)
        if existing is None:
            by_name[dimension.dimension] = dimension
            continue
        details = dict(existing.details)
        for key, value in dimension.details.items():
            details.setdefault(key, value)
        merge_note = f"merged duplicate from {provider_name}"
        if merge_note not in existing.summary:
            summary = f"{existing.summary}; {merge_note}".strip("; ").strip()
        else:
            summary = existing.summary
        evidence_ids = list(existing.evidence_ids)
        for evidence_id in dimension.evidence_ids:
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
        by_name[dimension.dimension] = existing.model_copy(
            update={
                "summary": summary or dimension.summary,
                "evidence_ids": evidence_ids,
                "details": details,
                "result": _prefer_dimension_result(existing.result, dimension.result),
            }
        )
    return list(by_name.values())


def _prefer_status(left: VerificationStatus, right: VerificationStatus) -> VerificationStatus:
    return left if _STATUS_PRECEDENCE[left] >= _STATUS_PRECEDENCE[right] else right


def _prefer_dimension_result(left, right):
    from models.research_resource_discovery import DimensionResult

    precedence = {
        DimensionResult.PASS: 5,
        DimensionResult.PARTIAL: 4,
        DimensionResult.NOT_APPLICABLE: 3,
        DimensionResult.INSUFFICIENT_EVIDENCE: 2,
        DimensionResult.FAIL: 1,
    }
    return left if precedence[left] >= precedence[right] else right
