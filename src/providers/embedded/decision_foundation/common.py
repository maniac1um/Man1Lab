"""Shared utilities for embedded decision foundation modules.

Contains formatting and helper functions only — no engineering decisions.
"""

from __future__ import annotations

from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel


def provider_name_factor(provider_name: str) -> str:
    return f"provider:{provider_name}"


def dimension_factor(dimension_name: str, level: DimensionLevel) -> str:
    return f"dimension:{dimension_name}:{level.value}"


def standard_dimension_factors(dimensions: DecisionDimensions) -> tuple[str, ...]:
    return (
        dimension_factor("resource_sufficiency", dimensions.resource_sufficiency),
        dimension_factor("resource_reliability", dimensions.resource_reliability),
        dimension_factor("engineering_commitment", dimensions.engineering_commitment),
        dimension_factor("reuse_opportunity", dimensions.reuse_opportunity),
        dimension_factor("adaptation_requirement", dimensions.adaptation_requirement),
        dimension_factor("generation_requirement", dimensions.generation_requirement),
    )


def map_dimension_confidence(level: DimensionLevel, mapping: dict[DimensionLevel, float]) -> float:
    return mapping[level]


def confidence_string(confidence: float) -> str:
    return str(confidence)


def decision_note_lines(*lines: str) -> tuple[str, ...]:
    return tuple(lines)
