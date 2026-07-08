"""Adaptation engineering decision from facts, dimensions, strategy, bindings, and reuse."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_planning_runtime import (
    ResourceBindingSnapshot,
    ReusePlanSnapshot,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    AdaptationScope,
    AdaptationTrigger,
    AdaptationTriggerType,
    AuthorizationLevel,
    AuthorizedModification,
    BindingRole,
    ModificationClass,
    ReuseExtent,
    ReuseMode,
    StrategyPosture,
)
from models.research_resource_discovery import VerificationStatus
from providers.embedded.decision_foundation.common import (
    confidence_string,
    dimension_factor,
    map_dimension_confidence,
    provider_name_factor,
)
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts

_PROVIDER_NAME = "embedded_adaptation"

_SUPPORTING_LABELS = frozenset({"fallback_repository", "supporting_asset"})

_STANDARD_CONSTRAINTS = (
    "Do not redesign model architecture.",
    "Do not replace training objectives.",
    "Do not reinterpret paper methodology.",
    "Do not perform algorithm or architecture replacement.",
)


@dataclass(frozen=True)
class AdaptationDecision:
    adaptation_required: bool
    adaptation_scope: AdaptationScope
    authorized_modifications: tuple[AuthorizedModification, ...]
    adaptation_constraints: tuple[str, ...]
    adaptation_triggers: tuple[AdaptationTrigger, ...]
    adaptation_deferred: bool
    adaptation_rationale: str
    decision_notes: tuple[str, ...]
    provider_factors: tuple[str, ...]
    diagnostics: dict[str, str]
    warnings: tuple[str, ...]
    confidence: float


def decide_adaptation(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
) -> AdaptationDecision:
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        return _empty_adaptation(
            facts=facts,
            dimensions=dimensions,
            strategy=strategy,
            reuse_plan=reuse_plan,
            reason="Greenfield posture — no adaptation plan authorized.",
        )

    if reuse_plan.reuse_mode == ReuseMode.NOT_APPLICABLE or not reuse_plan.components_to_reuse:
        return _empty_adaptation(
            facts=facts,
            dimensions=dimensions,
            strategy=strategy,
            reuse_plan=reuse_plan,
            reason="Reuse not applicable — no adaptation authorized.",
        )

    binding_index = {binding.binding_id: binding for binding in bindings.bindings}
    notes = ["Evaluating reusable components for adaptation authorization."]
    warnings: list[str] = []
    triggers = _adaptation_triggers(facts)

    if reuse_plan.reuse_mode == ReuseMode.AS_IS:
        supporting = [
            component
            for component in reuse_plan.components_to_reuse
            if component.component_label in _SUPPORTING_LABELS
        ]
        if not supporting:
            notes.append("Reuse mode AS_IS with primary components only — adaptation not required.")
            return AdaptationDecision(
                adaptation_required=False,
                adaptation_scope=AdaptationScope.NONE,
                authorized_modifications=(),
                adaptation_constraints=_STANDARD_CONSTRAINTS,
                adaptation_triggers=triggers,
                adaptation_deferred=False,
                adaptation_rationale="Primary resources reusable as-is; no adaptation authorized.",
                decision_notes=tuple(notes),
                provider_factors=_provider_factors(dimensions, reuse_plan, AdaptationScope.NONE, 0),
                diagnostics=_diagnostics(strategy, reuse_plan, AdaptationScope.NONE, False, dimensions, 0),
                warnings=tuple(warnings),
                confidence=_confidence(dimensions, adaptation_required=False),
            )

        scope = AdaptationScope.MINIMAL
        modifications = _modifications_for_components(
            supporting,
            binding_index,
            scope=scope,
            official_repository=strategy.primary_posture == StrategyPosture.OFFICIAL_REPOSITORY,
        )
        notes.append(f"Supporting resources present — minimal adaptation authorized ({len(modifications)} modifications).")
        return AdaptationDecision(
            adaptation_required=True,
            adaptation_scope=scope,
            authorized_modifications=tuple(modifications),
            adaptation_constraints=_STANDARD_CONSTRAINTS,
            adaptation_triggers=triggers,
            adaptation_deferred=False,
            adaptation_rationale="Supporting resources require limited configuration adaptation.",
            decision_notes=tuple(notes),
            provider_factors=_provider_factors(dimensions, reuse_plan, scope, len(modifications)),
            diagnostics=_diagnostics(strategy, reuse_plan, scope, True, dimensions, len(modifications)),
            warnings=tuple(warnings),
            confidence=_confidence(dimensions, adaptation_required=True),
        )

    scope = _resolve_hybrid_scope(strategy, dimensions)
    modifications = _modifications_for_components(
        list(reuse_plan.components_to_reuse),
        binding_index,
        scope=scope,
        official_repository=strategy.primary_posture == StrategyPosture.OFFICIAL_REPOSITORY,
    )
    notes.append(
        f"Reuse mode {reuse_plan.reuse_mode.value} — adaptation authorized "
        f"with scope {scope.value} ({len(modifications)} modifications)."
    )
    if strategy.primary_posture == StrategyPosture.OFFICIAL_REPOSITORY:
        notes.append("Official repository posture — preferring minimal adaptation scope.")

    return AdaptationDecision(
        adaptation_required=True,
        adaptation_scope=scope,
        authorized_modifications=tuple(modifications),
        adaptation_constraints=_STANDARD_CONSTRAINTS,
        adaptation_triggers=triggers,
        adaptation_deferred=False,
        adaptation_rationale=(
            f"Hybrid reuse requires authorized engineering adaptation at {scope.value} scope."
        ),
        decision_notes=tuple(notes),
        provider_factors=_provider_factors(dimensions, reuse_plan, scope, len(modifications)),
        diagnostics=_diagnostics(strategy, reuse_plan, scope, True, dimensions, len(modifications)),
        warnings=tuple(warnings),
        confidence=_confidence(dimensions, adaptation_required=True),
    )


def _empty_adaptation(
    *,
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    reason: str,
) -> AdaptationDecision:
    notes = [reason, "No authorized modifications committed."]
    return AdaptationDecision(
        adaptation_required=False,
        adaptation_scope=AdaptationScope.NONE,
        authorized_modifications=(),
        adaptation_constraints=_STANDARD_CONSTRAINTS,
        adaptation_triggers=_adaptation_triggers(facts),
        adaptation_deferred=False,
        adaptation_rationale=reason,
        decision_notes=tuple(notes),
        provider_factors=_provider_factors(dimensions, reuse_plan, AdaptationScope.NONE, 0),
        diagnostics=_diagnostics(strategy, reuse_plan, AdaptationScope.NONE, False, dimensions, 0),
        warnings=(),
        confidence=_confidence(dimensions, adaptation_required=False),
    )


def _resolve_hybrid_scope(
    strategy: StrategyDecisionSnapshot,
    dimensions: DecisionDimensions,
) -> AdaptationScope:
    if strategy.primary_posture == StrategyPosture.OFFICIAL_REPOSITORY:
        return AdaptationScope.MINIMAL
    if dimensions.adaptation_requirement == DimensionLevel.HIGH:
        return AdaptationScope.MODERATE
    return AdaptationScope.MINIMAL


def _modifications_for_components(
    components,
    binding_index: dict[str, object],
    *,
    scope: AdaptationScope,
    official_repository: bool,
) -> list[AuthorizedModification]:
    modifications: list[AuthorizedModification] = []
    for component in components:
        binding = binding_index.get(component.binding_id)
        if binding is None:
            continue
        modifications.extend(
            _modifications_for_component(
                component,
                binding,
                scope=scope,
                official_repository=official_repository,
            )
        )
    return modifications


def _modifications_for_component(
    component,
    binding,
    *,
    scope: AdaptationScope,
    official_repository: bool,
) -> list[AuthorizedModification]:
    binding_id = component.binding_id
    label = component.component_label
    auth_level = (
        AuthorizationLevel.PLANNER_TASK
        if official_repository and label == "repository"
        else AuthorizationLevel.CODER_DISCRETION
    )

    if label == "repository":
        mods = [
            AuthorizedModification(
                modification_class=ModificationClass.CONFIG_PATCH,
                target_binding_id=binding_id,
                authorization_level=auth_level,
            ),
        ]
        if scope != AdaptationScope.NONE:
            mods.append(
                AuthorizedModification(
                    modification_class=ModificationClass.SCRIPT_PATCH,
                    target_binding_id=binding_id,
                    authorization_level=AuthorizationLevel.CODER_DISCRETION,
                )
            )
        if scope == AdaptationScope.MODERATE and component.reuse_extent != ReuseExtent.FULL:
            mods.append(
                AuthorizedModification(
                    modification_class=ModificationClass.DEPENDENCY_PIN,
                    target_binding_id=binding_id,
                    authorization_level=AuthorizationLevel.PLANNER_TASK,
                )
            )
        return mods

    if label == "checkpoint":
        return [
            AuthorizedModification(
                modification_class=ModificationClass.CONFIG_PATCH,
                target_binding_id=binding_id,
                authorization_level=AuthorizationLevel.PLANNER_TASK,
            ),
        ]

    if label == "dataset":
        return [
            AuthorizedModification(
                modification_class=ModificationClass.CONFIG_PATCH,
                target_binding_id=binding_id,
                authorization_level=AuthorizationLevel.PLANNER_TASK,
            ),
        ]

    if label in _SUPPORTING_LABELS or binding.role in {
        BindingRole.FALLBACK_REPOSITORY,
        BindingRole.SUPPORTING_ASSET,
    }:
        return [
            AuthorizedModification(
                modification_class=ModificationClass.CONFIG_PATCH,
                target_binding_id=binding_id,
                authorization_level=AuthorizationLevel.PLANNER_TASK,
            ),
            AuthorizedModification(
                modification_class=ModificationClass.SCRIPT_PATCH,
                target_binding_id=binding_id,
                authorization_level=AuthorizationLevel.PLANNER_TASK,
            ),
        ]

    return []


def _adaptation_triggers(facts: ObservedFacts) -> tuple[AdaptationTrigger, ...]:
    triggers: list[AdaptationTrigger] = []
    for gap in facts.required_resource_gaps:
        triggers.append(
            AdaptationTrigger(
                trigger_type=AdaptationTriggerType.DISCOVERY_GAP,
                description=f"Required resource gap: {gap.gap_type.value} ({gap.severity.value}).",
                related_discovery_gap_id=gap.gap_id,
            )
        )
    if (
        facts.selected_repository is not None
        and facts.selected_repository.verification_status == VerificationStatus.PARTIAL
    ):
        triggers.append(
            AdaptationTrigger(
                trigger_type=AdaptationTriggerType.VERIFICATION_PARTIAL,
                description="Repository verification is partial; adaptation may be required.",
            )
        )
    return tuple(triggers)


def _confidence(dimensions: DecisionDimensions, *, adaptation_required: bool) -> float:
    if not adaptation_required:
        return map_dimension_confidence(
            dimensions.resource_reliability,
            {
                DimensionLevel.HIGH: 0.9,
                DimensionLevel.MEDIUM: 0.8,
                DimensionLevel.LOW: 0.65,
                DimensionLevel.UNKNOWN: 0.5,
            },
        )
    return map_dimension_confidence(
        dimensions.adaptation_requirement,
        {
            DimensionLevel.HIGH: 0.75,
            DimensionLevel.MEDIUM: 0.7,
            DimensionLevel.LOW: 0.55,
            DimensionLevel.UNKNOWN: 0.5,
        },
    )


def _diagnostics(
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    scope: AdaptationScope,
    adaptation_required: bool,
    dimensions: DecisionDimensions,
    modification_count: int,
) -> dict[str, str]:
    return {
        "posture": strategy.primary_posture.value,
        "reuse_mode": reuse_plan.reuse_mode.value,
        "adaptation_scope": scope.value,
        "adaptation_required": str(adaptation_required).lower(),
        "adaptation_requirement": dimensions.adaptation_requirement.value,
        "confidence": confidence_string(_confidence(dimensions, adaptation_required=adaptation_required)),
        "authorized_modification_count": str(modification_count),
    }


def _provider_factors(
    dimensions: DecisionDimensions,
    reuse_plan: ReusePlanSnapshot,
    scope: AdaptationScope,
    modification_count: int,
) -> tuple[str, ...]:
    return (
        provider_name_factor(_PROVIDER_NAME),
        f"reuse_mode:{reuse_plan.reuse_mode.value}",
        f"adaptation_scope:{scope.value}",
        f"authorized_modifications:{modification_count}",
        dimension_factor("adaptation_requirement", dimensions.adaptation_requirement),
        dimension_factor("resource_reliability", dimensions.resource_reliability),
    )
