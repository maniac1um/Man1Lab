"""Ranking merge policy for RankingService.

Merge strategy (append-only):
1. Deduplicate by rank_list_id (one canonical rank list per resource need).
2. Keep the first rank_list_id and resource_need.
3. Merge ordered_candidate_ids with stable union (keeper order first).
4. Merge scores; prefer higher total_score for duplicate candidate_ids.
5. Merge eligible_candidate_ids with stable union.
6. Append provenance notes to ranking_factors_summary.
7. Never discard rank lists for distinct resource needs.
"""

from __future__ import annotations

from models.research_resource_discovery import RankList, RankScore


def deduplication_key(rank_list: RankList) -> str:
    return rank_list.rank_list_id


def merge_rank_lists(existing: list[RankList], incoming: list[RankList]) -> list[RankList]:
    """Merge incoming rank lists without discarding lists for distinct needs."""
    merged = list(existing)
    index_by_key = {deduplication_key(rank_list): index for index, rank_list in enumerate(merged)}

    for rank_list in incoming:
        key = deduplication_key(rank_list)
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(rank_list)
            continue

        keeper_index = index_by_key[key]
        keeper = merged[keeper_index]
        merged[keeper_index] = _merge_duplicate(keeper, rank_list)

    return merged


def _merge_duplicate(keeper: RankList, duplicate: RankList) -> RankList:
    ordered_ids = _stable_union(keeper.ordered_candidate_ids, duplicate.ordered_candidate_ids)
    eligible_ids = _stable_union(keeper.eligible_candidate_ids, duplicate.eligible_candidate_ids)
    scores = dict(keeper.scores)
    for candidate_id, score in duplicate.scores.items():
        existing = scores.get(candidate_id)
        if existing is None or score.total_score > existing.total_score:
            scores[candidate_id] = score

    summary = keeper.ranking_factors_summary
    if duplicate.ranking_factors_summary and duplicate.ranking_factors_summary not in summary:
        summary = (
            f"{summary}; {duplicate.ranking_factors_summary}".strip("; ").strip()
            if summary
            else duplicate.ranking_factors_summary
        )

    return keeper.model_copy(
        update={
            "ordered_candidate_ids": ordered_ids,
            "eligible_candidate_ids": eligible_ids,
            "scores": scores,
            "ranking_factors_summary": summary,
        }
    )


def _stable_union(left: list[str], right: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for candidate_id in left + right:
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        merged.append(candidate_id)
    return merged


def merge_scores(
    left: dict[str, RankScore],
    right: dict[str, RankScore],
) -> dict[str, RankScore]:
    merged = dict(left)
    for candidate_id, score in right.items():
        existing = merged.get(candidate_id)
        if existing is None or score.total_score > existing.total_score:
            merged[candidate_id] = score
    return merged
