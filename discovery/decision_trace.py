"""Build decision trace records for discovery pipeline stages."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from models.decision_trace import DecisionStageName, DecisionStageRecord, DecisionTrace
from models.research_resource_discovery import ResearchResourceDiscovery


def build_discovery_decision_trace(
    discovery: ResearchResourceDiscovery,
    *,
    pipeline_version: str = "1.2.4",
) -> DecisionTrace:
    """Record discovery-stage decisions from assembled artifact."""
    now = datetime.now(UTC)
    candidates = discovery.candidate_resources.candidates
    evidence_count = len(discovery.evidence.records)
    verification_count = len(discovery.verification.records)
    rank_lists = discovery.ranking.rank_lists
    selections = discovery.selection.selections
    primary_count = sum(1 for item in selections if item.primary_candidate_id)

    stages = [
        DecisionStageRecord(
            stage=DecisionStageName.REPOSITORY,
            inputs={
                "candidate_count": str(len(candidates)),
                "resource_need_count": str(len(rank_lists)),
            },
            outputs={
                "collected_candidate_ids": ",".join(item.candidate_id for item in candidates[:5]),
                "asset_count": str(len(discovery.research_assets.assets)),
            },
            decision_rule="collection:embedded_and_provider_merge",
            rationale="Collect candidates from analysis gaps and embedded resources.",
            recorded_at=discovery.provenance.stage_timestamps.get("candidate_collection"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.EVIDENCE,
            inputs={"candidate_count": str(len(candidates))},
            outputs={"evidence_count": str(evidence_count)},
            decision_rule="evidence:provider_merge",
            rationale="Gather supporting and refuting evidence per candidate.",
            recorded_at=discovery.provenance.stage_timestamps.get("evidence_collection"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.VERIFICATION,
            inputs={"evidence_count": str(evidence_count)},
            outputs={
                "verification_count": str(verification_count),
                "pass_count": str(
                    sum(1 for item in discovery.verification.records if item.status.value == "pass")
                ),
            },
            decision_rule="verification:dimension_gate",
            rationale="Verify identity, paper match, and artifact availability.",
            recorded_at=discovery.provenance.stage_timestamps.get("verification"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.RANKING,
            inputs={"verification_count": str(verification_count)},
            outputs={
                "rank_list_count": str(len(rank_lists)),
                "eligible_total": str(sum(len(item.eligible_candidate_ids) for item in rank_lists)),
            },
            decision_rule="ranking:verification_precedence",
            rationale="Rank eligible candidates per resource need.",
            recorded_at=discovery.provenance.stage_timestamps.get("ranking"),
        ),
        DecisionStageRecord(
            stage=DecisionStageName.SELECTION,
            inputs={"rank_list_count": str(len(rank_lists))},
            outputs={
                "primary_selection_count": str(primary_count),
                "gap_count": str(len(discovery.discovery_gaps.gaps)),
            },
            decision_rule="selection:verification_officiality_rank",
            rationale="Commit primary and fallback selections with explainable confidence.",
            recorded_at=discovery.provenance.stage_timestamps.get("selection"),
        ),
    ]
    return DecisionTrace(
        trace_id=f"trace-{uuid.uuid4()}",
        created_at=now,
        pipeline_version=pipeline_version,
        discovery_id=discovery.metadata.discovery_id,
        stages=stages,
    )
