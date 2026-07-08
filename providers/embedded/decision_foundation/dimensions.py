"""Decision dimensions — engineering evaluation without embedded rule logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.research_resource_discovery import VerificationStatus
from providers.embedded.decision_foundation.facts import ObservedFacts


class DimensionLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DecisionDimensions:
    resource_sufficiency: DimensionLevel
    resource_reliability: DimensionLevel
    engineering_commitment: DimensionLevel
    reuse_opportunity: DimensionLevel
    adaptation_requirement: DimensionLevel
    generation_requirement: DimensionLevel


def evaluate_dimensions(facts: ObservedFacts) -> DecisionDimensions:
    return DecisionDimensions(
        resource_sufficiency=_resource_sufficiency(facts),
        resource_reliability=_resource_reliability(facts),
        engineering_commitment=_engineering_commitment(facts),
        reuse_opportunity=_reuse_opportunity(facts),
        adaptation_requirement=_adaptation_requirement(facts),
        generation_requirement=_generation_requirement(facts),
    )


def _resource_sufficiency(facts: ObservedFacts) -> DimensionLevel:
    if not facts.required_resource_gaps:
        return DimensionLevel.HIGH
    if facts.blocking_discovery_gaps:
        return DimensionLevel.LOW
    return DimensionLevel.MEDIUM


def _resource_reliability(facts: ObservedFacts) -> DimensionLevel:
    if facts.repository_verified:
        return DimensionLevel.HIGH
    if facts.selected_repository and facts.selected_repository.verification_status == VerificationStatus.PARTIAL:
        return DimensionLevel.MEDIUM
    if facts.repository_available:
        return DimensionLevel.LOW
    return DimensionLevel.UNKNOWN


def _engineering_commitment(facts: ObservedFacts) -> DimensionLevel:
    if facts.repository_official and facts.repository_verified and not facts.required_resource_gaps:
        return DimensionLevel.LOW
    if facts.repository_usable and facts.required_resource_gaps:
        return DimensionLevel.MEDIUM
    return DimensionLevel.HIGH


def _reuse_opportunity(facts: ObservedFacts) -> DimensionLevel:
    if facts.repository_official and facts.repository_verified:
        return DimensionLevel.HIGH
    if facts.repository_usable:
        return DimensionLevel.MEDIUM
    return DimensionLevel.LOW


def _adaptation_requirement(facts: ObservedFacts) -> DimensionLevel:
    if facts.required_resource_gaps:
        return DimensionLevel.HIGH
    if facts.repository_usable and not facts.repository_verified:
        return DimensionLevel.MEDIUM
    return DimensionLevel.LOW


def _generation_requirement(facts: ObservedFacts) -> DimensionLevel:
    if not facts.repository_usable:
        return DimensionLevel.HIGH
    if facts.required_resource_gaps:
        return DimensionLevel.MEDIUM
    return DimensionLevel.LOW
