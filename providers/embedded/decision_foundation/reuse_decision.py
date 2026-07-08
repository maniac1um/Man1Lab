"""Reuse engineering decision from facts, dimensions, and resource bindings."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_planning_runtime import ResourceBindingSnapshot, StrategyDecisionSnapshot
from models.execution_strategy import (
    BindingRole,
    ExcludedComponent,
    ReuseComponent,
    ReuseExtent,
    ReuseMode,
    StrategyPosture,
    UsageIntent,
)
from models.research_resource_discovery import VerificationStatus
from providers.embedded.decision_foundation.common import (
    confidence_string,
    dimension_factor,
    map_dimension_confidence,
    provider_name_factor,
)
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts, SelectedResourceFact

_PROVIDER_NAME = "embedded_reuse"

_PRIMARY_ROLES = {
    BindingRole.PRIMARY_REPOSITORY,
    BindingRole.CHECKPOINT,
    BindingRole.DATASET,
}
_SUPPORTING_ROLES = {
    BindingRole.FALLBACK_REPOSITORY,
    BindingRole.SUPPORTING_ASSET,
}


@dataclass(frozen=True)
class ReuseDecision:
    reuse_mode: ReuseMode
    primary_reuse_binding_id: str | None
    components_to_reuse: tuple[ReuseComponent, ...]
    components_excluded: tuple[ExcludedComponent, ...]
    reuse_assumptions: tuple[str, ...]
    reuse_limitations: tuple[str, ...]
    decision_notes: tuple[str, ...]
    provider_factors: tuple[str, ...]
    diagnostics: dict[str, str]
    warnings: tuple[str, ...]
    confidence: float


def decide_reuse(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    bindings: ResourceBindingSnapshot,
    strategy: StrategyDecisionSnapshot,
) -> ReuseDecision:
    if strategy.primary_posture == StrategyPosture.GREENFIELD or not bindings.bindings:
        return _not_applicable_decision(
            facts=facts,
            dimensions=dimensions,
            strategy=strategy,
            reason="Greenfield posture or no bindings — reuse not applicable.",
        )

    bound_candidate_ids = {binding.candidate_id for binding in bindings.bindings}
    components: list[ReuseComponent] = []
    notes: list[str] = ["Evaluating bound resources for reuse eligibility."]
    limitations: list[str] = []
    warnings: list[str] = []

    for binding in bindings.bindings:
        if not _binding_reusable(binding):
            notes.append(
                f"Binding skipped for reuse: {binding.binding_id} "
                f"(role={binding.role.value}, intent={binding.usage_intent.value})"
            )
            continue
        extent = _reuse_extent(binding.role)
        label = _component_label(binding.role)
        components.append(
            ReuseComponent(
                binding_id=binding.binding_id,
                component_label=label,
                reuse_extent=extent,
            )
        )
        notes.append(f"Reuse committed: {label} ({binding.binding_id})")
        if extent != ReuseExtent.FULL:
            limitations.append(
                f"{label} bound with {extent.value} reuse; may require adaptation downstream."
            )
        elif dimensions.adaptation_requirement != DimensionLevel.LOW:
            limitations.append(
                f"{label} eligible for direct reuse; adaptation requirement="
                f"{dimensions.adaptation_requirement.value} deferred to adaptation stage."
            )

    excluded = _excluded_components(facts, bound_candidate_ids)
    for item in excluded:
        notes.append(f"Excluded from reuse: {item.candidate_id} — {item.exclusion_reason}")

    if not components:
        return _not_applicable_decision(
            facts=facts,
            dimensions=dimensions,
            strategy=strategy,
            reason="No bound resources eligible for reuse.",
            excluded=excluded,
            warnings=tuple(warnings),
        )

    reuse_mode = _resolve_reuse_mode(strategy, components, bindings)
    primary_id = _primary_reuse_binding(bindings, components)
    assumptions = _reuse_assumptions(strategy, components, dimensions)

    if dimensions.reuse_opportunity == DimensionLevel.LOW:
        warnings.append("Reuse opportunity dimension is low; reuse commitments are conservative.")

    return ReuseDecision(
        reuse_mode=reuse_mode,
        primary_reuse_binding_id=primary_id,
        components_to_reuse=tuple(components),
        components_excluded=excluded,
        reuse_assumptions=assumptions,
        reuse_limitations=tuple(limitations),
        decision_notes=tuple(notes),
        provider_factors=_provider_factors(dimensions, reuse_mode, len(components)),
        diagnostics={
            "posture": strategy.primary_posture.value,
            "reuse_mode": reuse_mode.value,
            "reuse_opportunity": dimensions.reuse_opportunity.value,
            "adaptation_requirement": dimensions.adaptation_requirement.value,
            "confidence": confidence_string(_confidence(dimensions)),
            "reusable_component_count": str(len(components)),
        },
        warnings=tuple(warnings),
        confidence=_confidence(dimensions),
    )


def _not_applicable_decision(
    *,
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    reason: str,
    excluded: tuple[ExcludedComponent, ...] | None = None,
    warnings: tuple[str, ...] = (),
) -> ReuseDecision:
    resolved_excluded = excluded if excluded is not None else _excluded_components(facts, set())
    notes = [reason, "Reuse mode set to not_applicable."]
    for item in resolved_excluded:
        notes.append(f"Excluded: {item.candidate_id} — {item.exclusion_reason}")
    return ReuseDecision(
        reuse_mode=ReuseMode.NOT_APPLICABLE,
        primary_reuse_binding_id=None,
        components_to_reuse=(),
        components_excluded=resolved_excluded,
        reuse_assumptions=(),
        reuse_limitations=("No reusable bindings committed.",),
        decision_notes=tuple(notes),
        provider_factors=_provider_factors(dimensions, ReuseMode.NOT_APPLICABLE, 0),
        diagnostics={
            "posture": strategy.primary_posture.value,
            "reuse_mode": ReuseMode.NOT_APPLICABLE.value,
            "reuse_opportunity": dimensions.reuse_opportunity.value,
            "confidence": confidence_string(_confidence(dimensions)),
            "reusable_component_count": "0",
        },
        warnings=warnings,
        confidence=_confidence(dimensions),
    )


def _binding_reusable(binding) -> bool:
    if binding.role in _PRIMARY_ROLES | _SUPPORTING_ROLES:
        return True
    return binding.usage_intent in {
        UsageIntent.EXECUTE_DIRECTLY,
        UsageIntent.EXTRACT_ASSETS_FROM,
        UsageIntent.FALLBACK_IF_PRIMARY_FAILS,
    }


def _reuse_extent(role: BindingRole) -> ReuseExtent:
    if role in _PRIMARY_ROLES:
        return ReuseExtent.FULL
    if role == BindingRole.FALLBACK_REPOSITORY:
        return ReuseExtent.PARTIAL
    if role == BindingRole.SUPPORTING_ASSET:
        return ReuseExtent.ENTRYPOINT_ONLY
    return ReuseExtent.PARTIAL


def _component_label(role: BindingRole) -> str:
    return {
        BindingRole.PRIMARY_REPOSITORY: "repository",
        BindingRole.CHECKPOINT: "checkpoint",
        BindingRole.DATASET: "dataset",
        BindingRole.FALLBACK_REPOSITORY: "fallback_repository",
        BindingRole.SUPPORTING_ASSET: "supporting_asset",
    }.get(role, role.value)


def _resolve_reuse_mode(
    strategy: StrategyDecisionSnapshot,
    components: list[ReuseComponent],
    bindings: ResourceBindingSnapshot,
) -> ReuseMode:
    if strategy.primary_posture == StrategyPosture.HYBRID:
        return ReuseMode.HYBRID_COMPONENTS
    primary_roles = {
        binding.role
        for binding in bindings.bindings
        if binding.binding_id in {component.binding_id for component in components}
    }
    if BindingRole.PRIMARY_REPOSITORY in primary_roles and len(components) == 1:
        return ReuseMode.AS_IS
    if BindingRole.PRIMARY_REPOSITORY in primary_roles:
        return ReuseMode.AS_IS
    if any(role in _SUPPORTING_ROLES for role in primary_roles):
        return ReuseMode.HYBRID_COMPONENTS
    return ReuseMode.AS_IS


def _primary_reuse_binding(
    bindings: ResourceBindingSnapshot,
    components: list[ReuseComponent],
) -> str | None:
    if bindings.anchor_binding_id:
        reusable_ids = {component.binding_id for component in components}
        if bindings.anchor_binding_id in reusable_ids:
            return bindings.anchor_binding_id
    for binding in bindings.bindings:
        if binding.role == BindingRole.PRIMARY_REPOSITORY:
            return binding.binding_id
    return components[0].binding_id if components else None


def _reuse_assumptions(
    strategy: StrategyDecisionSnapshot,
    components: list[ReuseComponent],
    dimensions: DecisionDimensions,
) -> tuple[str, ...]:
    assumptions = [
        f"Reuse aligned with {strategy.primary_posture.value} posture.",
        f"Reuse opportunity dimension: {dimensions.reuse_opportunity.value}.",
    ]
    labels = sorted({component.component_label for component in components})
    assumptions.append(f"Committed reuse components: {', '.join(labels)}.")
    return tuple(assumptions)


def _excluded_components(
    facts: ObservedFacts,
    bound_candidate_ids: set[str],
) -> tuple[ExcludedComponent, ...]:
    excluded: list[ExcludedComponent] = []
    for resource in (
        facts.selected_repository,
        facts.selected_checkpoint,
        facts.selected_dataset,
    ):
        if resource is not None and resource.candidate_id not in bound_candidate_ids:
            excluded.append(
                ExcludedComponent(
                    candidate_id=resource.candidate_id,
                    exclusion_reason=_exclusion_reason(resource),
                )
            )
    for resource in facts.supplementary_resources:
        if resource.candidate_id not in bound_candidate_ids:
            excluded.append(
                ExcludedComponent(
                    candidate_id=resource.candidate_id,
                    exclusion_reason=_exclusion_reason(resource),
                )
            )
    return tuple(excluded)


def _exclusion_reason(resource: SelectedResourceFact) -> str:
    status = resource.verification_status
    if status is None:
        return "No verification record; resource not bound for reuse."
    if status == VerificationStatus.FAIL:
        return "Verification failed; resource not bound for reuse."
    if status == VerificationStatus.PARTIAL:
        return "Partial verification; not eligible for primary reuse."
    return "Discovery selection not included in active bindings."


def _confidence(dimensions: DecisionDimensions) -> float:
    return map_dimension_confidence(
        dimensions.reuse_opportunity,
        {
            DimensionLevel.HIGH: 0.9,
            DimensionLevel.MEDIUM: 0.75,
            DimensionLevel.LOW: 0.5,
            DimensionLevel.UNKNOWN: 0.5,
        },
    )


def _provider_factors(
    dimensions: DecisionDimensions,
    reuse_mode: ReuseMode,
    component_count: int,
) -> tuple[str, ...]:
    return (
        provider_name_factor(_PROVIDER_NAME),
        f"reuse_mode:{reuse_mode.value}",
        f"reusable_components:{component_count}",
        dimension_factor("reuse_opportunity", dimensions.reuse_opportunity),
        dimension_factor("adaptation_requirement", dimensions.adaptation_requirement),
        dimension_factor("resource_reliability", dimensions.resource_reliability),
    )
