"""Candidate merge policy for CollectionService.

Merge strategy (append-only):
1. Deduplicate by normalized URL when present.
2. Otherwise deduplicate by (provider, provider_native_id).
3. Keep the first candidate_id; record merged provenance in notes.
4. Union related_candidate_ids and addresses_needs from duplicates.
5. Never discard candidates or evidence-bearing references.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from models.research_resource_discovery import RepositoryCandidate

_TRACKING_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "ref")


def deduplication_key(candidate: RepositoryCandidate) -> tuple[str, ...]:
    """Stable key for merge: normalized URL first, else provider-native identity."""
    normalized = candidate.identity.normalized_url or normalize_url(candidate.url)
    if normalized:
        return ("url", normalized)
    native_id = candidate.identity.provider_native_id.strip()
    if native_id:
        return ("native", candidate.identity.provider.value, native_id)
    return ("candidate_id", candidate.candidate_id)


def normalize_url(url: str) -> str:
    """Canonicalize URLs for deduplication (strip tracking params, normalize host)."""
    text = url.strip()
    if not text:
        return ""

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/")

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(_TRACKING_QUERY_PREFIXES)
    ]
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.params,
            urlencode(filtered_query),
            "",
        )
    )
    return normalized.rstrip("/")


def merge_candidates(
    existing: list[RepositoryCandidate],
    incoming: list[RepositoryCandidate],
) -> list[RepositoryCandidate]:
    """Merge incoming candidates into existing list without discarding provenance."""
    merged = list(existing)
    index_by_key = {deduplication_key(candidate): index for index, candidate in enumerate(merged)}

    for candidate in incoming:
        key = deduplication_key(candidate)
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(candidate)
            continue

        keeper_index = index_by_key[key]
        keeper = merged[keeper_index]
        merged[keeper_index] = _merge_duplicate(keeper, candidate)

    return merged


def _merge_duplicate(
    keeper: RepositoryCandidate,
    duplicate: RepositoryCandidate,
) -> RepositoryCandidate:
    """Preserve append-only semantics: merge provenance into notes, keep first candidate_id."""
    duplicate_source = duplicate.collection_source.provider_name or "unknown"
    merge_note = f"merged duplicate from {duplicate_source}"
    notes = keeper.notes
    if merge_note not in notes:
        notes = f"{notes}; {merge_note}".strip("; ").strip()

    related = list(keeper.related_candidate_ids)
    if duplicate.candidate_id not in related:
        related.append(duplicate.candidate_id)

    addresses = list(keeper.addresses_needs)
    for need_id in duplicate.addresses_needs:
        if need_id not in addresses:
            addresses.append(need_id)

    return keeper.model_copy(
        update={
            "notes": notes,
            "related_candidate_ids": related,
            "addresses_needs": addresses,
        }
    )
