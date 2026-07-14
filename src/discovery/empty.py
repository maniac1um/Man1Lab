"""Empty discovery artifact for disabled discovery or NoOp runs."""

from __future__ import annotations

from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import (
    DiscoveryGap,
    DiscoveryGaps,
    DiscoveryGapType,
    GapSeverity,
    RecommendedAction,
    ResearchResourceDiscovery,
    SelectionResult,
)
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult
from ports.verification_provider import VerificationProviderResult
from discovery.workflow import ResearchResourceDiscoveryBuilder
from models.research_resource_discovery import RankingResult


def build_empty_discovery(analysis: PaperReproductionAnalysis) -> ResearchResourceDiscovery:
    """Produce a valid empty discovery artifact without running provider stages."""
    gaps = [
        DiscoveryGap(
            gap_id=f"gap-{index}",
            gap_type=_map_gap_type(gap.category.value),
            severity=GapSeverity.BLOCKING,
            description=f"Discovery disabled or unavailable: {gap.description}",
            related_analysis_gap_index=index,
            recommended_action=RecommendedAction.MANUAL_INPUT,
        )
        for index, gap in enumerate(analysis.reproduction_gaps)
    ]
    if not gaps:
        gaps.append(
            DiscoveryGap(
                gap_id="gap-discovery-disabled",
                gap_type=DiscoveryGapType.PROVIDER_UNAVAILABLE,
                severity=GapSeverity.INFORMATIONAL,
                description="Discovery disabled — no candidates collected.",
                recommended_action=RecommendedAction.MANUAL_INPUT,
            )
        )
    return ResearchResourceDiscoveryBuilder.build(
        analysis=analysis,
        collection=CollectionProviderResult(),
        evidence=EvidenceProviderResult(),
        verification=VerificationProviderResult(),
        ranking=RankingResult(),
        selection=SelectionResult(),
        discovery_gaps=DiscoveryGaps(
            gaps=gaps,
            analysis_gaps_remaining=[gap.category.value for gap in analysis.reproduction_gaps],
        ),
    )


def _map_gap_type(category: str) -> DiscoveryGapType:
    mapping = {
        "repository": DiscoveryGapType.NO_OFFICIAL_REPOSITORY,
        "checkpoint": DiscoveryGapType.CHECKPOINT_MISSING,
        "config": DiscoveryGapType.CONFIG_MISSING,
        "dataset_link": DiscoveryGapType.DATASET_UNAVAILABLE,
    }
    return mapping.get(category, DiscoveryGapType.OTHER)
