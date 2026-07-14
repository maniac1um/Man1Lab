"""Merge policy for Execution Planning risk assessment stage results."""

from __future__ import annotations

from models.execution_planning_runtime import RiskAssessmentResult


def merge_risk_results(existing: RiskAssessmentResult, incoming: RiskAssessmentResult) -> RiskAssessmentResult:
    if _is_empty_risk(existing) and not _is_empty_risk(incoming):
        return incoming
    if not _is_empty_risk(existing):
        return existing
    return incoming


def _is_empty_risk(result: RiskAssessmentResult) -> bool:
    return (
        result.risk_assessment.overall_confidence == 0.0
        and not result.risk_assessment.blocking_risks
        and not result.risk_assessment.degraded_risks
        and not result.decision_notes
    )
