"""Explainable confidence composition models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class ConfidenceContribution(BaseModel):
    """Single evidence signal contributing to selection confidence."""

    model_config = ConfigDict(frozen=True)

    signal: str
    weight: float = 0.0
    score: float = 0.0
    contribution: float = 0.0
    summary: str = ""


class ExplainableConfidence(BaseModel):
    """Deterministic confidence with auditable evidence contributions."""

    model_config = ConfigDict(frozen=True)

    overall: float = 0.0
    contributions: list[ConfidenceContribution] = Field(default_factory=list)
    composition_rule: str = "weighted_sum_capped"
