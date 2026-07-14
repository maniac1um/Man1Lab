"""Evidence merge policy for EvidenceService.

Merge strategy (append-only):
1. Deduplicate by (candidate_id, evidence_type, normalized URL, source_query).
2. Keep the first evidence_id.
3. Record merged provenance in raw_reference.
4. Union observed_fact.extensions from duplicates.
5. Never discard evidence records.
"""

from __future__ import annotations

from models.research_resource_discovery import EvidenceRecord
from services.discovery.candidate_merge import normalize_url


def deduplication_key(record: EvidenceRecord) -> tuple[str, ...]:
    url = str(record.observed_fact.fields.get("url", ""))
    source_query = str(record.observed_fact.fields.get("source_query", ""))
    normalized_url = normalize_url(url) if url else ""
    return (
        record.candidate_id,
        record.evidence_type.value,
        normalized_url,
        source_query,
    )


def merge_evidence(
    existing: list[EvidenceRecord],
    incoming: list[EvidenceRecord],
) -> list[EvidenceRecord]:
    """Merge incoming evidence into existing list without discarding records."""
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


def _merge_duplicate(keeper: EvidenceRecord, duplicate: EvidenceRecord) -> EvidenceRecord:
    provider_name = duplicate.evidence_source.provider_name or "unknown"
    merge_note = f"merged duplicate from {provider_name}"
    raw_reference = keeper.raw_reference or ""
    if merge_note not in raw_reference:
        raw_reference = f"{raw_reference}; {merge_note}".strip("; ").strip() or merge_note

    extensions = dict(keeper.observed_fact.extensions)
    for key, value in duplicate.observed_fact.extensions.items():
        if key not in extensions:
            extensions[key] = value

    observed_fact = keeper.observed_fact.model_copy(update={"extensions": extensions})
    return keeper.model_copy(update={"raw_reference": raw_reference, "observed_fact": observed_fact})
