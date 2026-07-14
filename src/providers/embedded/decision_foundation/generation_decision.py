"""Generation engineering decision from facts, dimensions, and prior planning stages."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_planning_runtime import (
    AdaptationPlanSnapshot,
    ResourceBindingSnapshot,
    ReusePlanSnapshot,
    StrategyDecisionSnapshot,
)
from models.execution_strategy import (
    AnalysisModule,
    GenerationIntent,
    GenerationPriority,
    GenerationScope,
    GenerationTarget,
    ReuseMode,
    StrategyPosture,
)
from models.research_resource_discovery import DiscoveryGapType
from providers.embedded.decision_foundation.common import (
    confidence_string,
    dimension_factor,
    map_dimension_confidence,
    provider_name_factor,
)
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts

_PROVIDER_NAME = "embedded_generation"

_SUPPORTING_LABELS = frozenset({"fallback_repository", "supporting_asset"})

_STANDARD_CONSTRAINTS = (
    "Do not generate model implementation.",
    "Do not redesign algorithms or network architecture.",
    "Do not change training objectives.",
    "Do not reinterpret paper methodology.",
    "Do not restructure repository layout.",
)


@dataclass(frozen=True)
class GenerationDecision:
    generation_required: bool
    generation_scope: GenerationScope
    modules_to_generate: tuple[GenerationTarget, ...]
    generation_constraints: tuple[str, ...]
    generation_rationale: str
    reuse_fallback_after_generation: bool
    decision_notes: tuple[str, ...]
    provider_factors: tuple[str, ...]
    diagnostics: dict[str, str]
    warnings: tuple[str, ...]
    confidence: float


def decide_generation(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
    bindings: ResourceBindingSnapshot,
    reuse_plan: ReusePlanSnapshot,
    adaptation_plan: AdaptationPlanSnapshot,
) -> GenerationDecision:
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        targets = _greenfield_targets()
        notes = (
            "Greenfield posture — engineering artifact generation required.",
            f"Committed {len(targets)} generation targets for campaign scaffolding.",
        )
        return GenerationDecision(
            generation_required=True,
            generation_scope=GenerationScope.FULL_CODEBASE,
            modules_to_generate=targets,
            generation_constraints=_STANDARD_CONSTRAINTS,
            generation_rationale=(
                "Greenfield posture requires generation of configuration, launchers, "
                "and execution scaffolding."
            ),
            reuse_fallback_after_generation=False,
            decision_notes=notes,
            provider_factors=_provider_factors(dimensions, GenerationScope.FULL_CODEBASE, len(targets)),
            diagnostics=_diagnostics(strategy, reuse_plan, GenerationScope.FULL_CODEBASE, True, dimensions, len(targets)),
            warnings=(),
            confidence=_confidence(dimensions, generation_required=True),
        )

    if reuse_plan.reuse_mode == ReuseMode.AS_IS and not adaptation_plan.adaptation_required:
        notes = (
            "Reuse mode AS_IS with no adaptation required.",
            "No engineering artifact generation authorized.",
        )
        return _no_generation_decision(
            strategy=strategy,
            reuse_plan=reuse_plan,
            dimensions=dimensions,
            rationale="Official repository reusable as-is; no engineering artifact generation required.",
            notes=notes,
        )

    reused_labels = {component.component_label for component in reuse_plan.components_to_reuse}
    targets = _hybrid_missing_targets(facts, reuse_plan, reused_labels)
    if adaptation_plan.adaptation_required and _has_supporting_components(reuse_plan):
        targets = _merge_targets(targets, _supporting_integration_targets())

    if not targets:
        notes = ("No missing engineering artifacts identified after reuse and adaptation.",)
        return _no_generation_decision(
            strategy=strategy,
            reuse_plan=reuse_plan,
            dimensions=dimensions,
            rationale="Reusable components satisfy engineering artifact requirements.",
            notes=notes,
        )

    scope = _resolve_scope(strategy, reuse_plan, len(targets))
    notes = (
        "Evaluating reusable components for missing engineering artifacts.",
        f"Generation scope: {scope.value}.",
        f"Committed {len(targets)} generation targets.",
    )
    return GenerationDecision(
        generation_required=True,
        generation_scope=scope,
        modules_to_generate=targets,
        generation_constraints=_STANDARD_CONSTRAINTS,
        generation_rationale=(
            "Hybrid or partial reuse requires generation of missing engineering artifacts only."
        ),
        reuse_fallback_after_generation=bool(bindings.bindings),
        decision_notes=notes,
        provider_factors=_provider_factors(dimensions, scope, len(targets)),
        diagnostics=_diagnostics(strategy, reuse_plan, scope, True, dimensions, len(targets)),
        warnings=(),
        confidence=_confidence(dimensions, generation_required=True),
    )


def _no_generation_decision(
    *,
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    dimensions: DecisionDimensions,
    rationale: str,
    notes: tuple[str, ...],
) -> GenerationDecision:
    return GenerationDecision(
        generation_required=False,
        generation_scope=GenerationScope.NONE,
        modules_to_generate=(),
        generation_constraints=_STANDARD_CONSTRAINTS,
        generation_rationale=rationale,
        reuse_fallback_after_generation=False,
        decision_notes=notes,
        provider_factors=_provider_factors(dimensions, GenerationScope.NONE, 0),
        diagnostics=_diagnostics(strategy, reuse_plan, GenerationScope.NONE, False, dimensions, 0),
        warnings=(),
        confidence=_confidence(dimensions, generation_required=False),
    )


def _greenfield_targets() -> tuple[GenerationTarget, ...]:
    return (
        GenerationTarget(
            analysis_module=AnalysisModule.RESOURCES,
            generation_intent=GenerationIntent.REPLACE_MISSING_UPSTREAM,
            priority=GenerationPriority.BLOCKING,
        ),
        GenerationTarget(
            analysis_module=AnalysisModule.METHOD,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.BLOCKING,
        ),
        GenerationTarget(
            analysis_module=AnalysisModule.EVALUATION,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.BLOCKING,
        ),
        GenerationTarget(
            analysis_module=AnalysisModule.GOAL,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.BLOCKING,
        ),
    )


def _hybrid_missing_targets(
    facts: ObservedFacts,
    reuse_plan: ReusePlanSnapshot,
    reused_labels: set[str],
) -> tuple[GenerationTarget, ...]:
    targets: list[GenerationTarget] = []
    seen_modules: set[AnalysisModule] = set()

    if not facts.checkpoint_available and "checkpoint" not in reused_labels:
        targets.append(
            GenerationTarget(
                analysis_module=AnalysisModule.RESOURCES,
                generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
                priority=GenerationPriority.DEGRADED,
            )
        )
        seen_modules.add(AnalysisModule.RESOURCES)

    if not facts.dataset_available and "dataset" not in reused_labels:
        target = GenerationTarget(
            analysis_module=AnalysisModule.RESOURCES,
            generation_intent=GenerationIntent.REPLACE_MISSING_UPSTREAM,
            priority=GenerationPriority.DEGRADED,
        )
        if AnalysisModule.RESOURCES not in seen_modules:
            targets.append(target)
            seen_modules.add(AnalysisModule.RESOURCES)

    for gap in facts.required_resource_gaps:
        module, intent, priority = _gap_generation_target(gap.gap_type)
        if module in seen_modules:
            continue
        if module == AnalysisModule.RESOURCES and {"checkpoint", "dataset"} & reused_labels:
            if gap.gap_type in {
                DiscoveryGapType.CHECKPOINT_MISSING,
                DiscoveryGapType.DATASET_UNAVAILABLE,
            }:
                continue
        targets.append(
            GenerationTarget(
                analysis_module=module,
                generation_intent=intent,
                priority=priority,
            )
        )
        seen_modules.add(module)

    if reuse_plan.reuse_mode == ReuseMode.HYBRID_COMPONENTS and AnalysisModule.EVALUATION not in seen_modules:
        targets.append(
            GenerationTarget(
                analysis_module=AnalysisModule.EVALUATION,
                generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
                priority=GenerationPriority.DEGRADED,
            )
        )

    return tuple(targets)


def _supporting_integration_targets() -> tuple[GenerationTarget, ...]:
    return (
        GenerationTarget(
            analysis_module=AnalysisModule.RESOURCES,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.OPTIONAL,
        ),
        GenerationTarget(
            analysis_module=AnalysisModule.METHOD,
            generation_intent=GenerationIntent.STUB_FOR_INTEGRATION,
            priority=GenerationPriority.OPTIONAL,
        ),
    )


def _gap_generation_target(
    gap_type: DiscoveryGapType,
) -> tuple[AnalysisModule, GenerationIntent, GenerationPriority]:
    mapping: dict[DiscoveryGapType, tuple[AnalysisModule, GenerationIntent, GenerationPriority]] = {
        DiscoveryGapType.CHECKPOINT_MISSING: (
            AnalysisModule.RESOURCES,
            GenerationIntent.STUB_FOR_INTEGRATION,
            GenerationPriority.DEGRADED,
        ),
        DiscoveryGapType.CONFIG_MISSING: (
            AnalysisModule.RESOURCES,
            GenerationIntent.REPLACE_MISSING_UPSTREAM,
            GenerationPriority.BLOCKING,
        ),
        DiscoveryGapType.DATASET_UNAVAILABLE: (
            AnalysisModule.RESOURCES,
            GenerationIntent.STUB_FOR_INTEGRATION,
            GenerationPriority.DEGRADED,
        ),
        DiscoveryGapType.SCOPE_INSUFFICIENT: (
            AnalysisModule.EVALUATION,
            GenerationIntent.STUB_FOR_INTEGRATION,
            GenerationPriority.DEGRADED,
        ),
        DiscoveryGapType.FRAMEWORK_MISMATCH: (
            AnalysisModule.METHOD,
            GenerationIntent.STUB_FOR_INTEGRATION,
            GenerationPriority.DEGRADED,
        ),
    }
    return mapping.get(
        gap_type,
        (
            AnalysisModule.RESOURCES,
            GenerationIntent.STUB_FOR_INTEGRATION,
            GenerationPriority.OPTIONAL,
        ),
    )


def _has_supporting_components(reuse_plan: ReusePlanSnapshot) -> bool:
    return any(
        component.component_label in _SUPPORTING_LABELS
        for component in reuse_plan.components_to_reuse
    )


def _merge_targets(
    existing: tuple[GenerationTarget, ...],
    additional: tuple[GenerationTarget, ...],
) -> tuple[GenerationTarget, ...]:
    merged = list(existing)
    present = {(target.analysis_module, target.generation_intent) for target in existing}
    for target in additional:
        key = (target.analysis_module, target.generation_intent)
        if key not in present:
            merged.append(target)
            present.add(key)
    return tuple(merged)


def _resolve_scope(
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    target_count: int,
) -> GenerationScope:
    if strategy.primary_posture == StrategyPosture.HYBRID or reuse_plan.reuse_mode == ReuseMode.HYBRID_COMPONENTS:
        return GenerationScope.MISSING_MODULES
    if target_count <= 2:
        return GenerationScope.CONFIG_AND_SCRIPTS
    return GenerationScope.MISSING_MODULES


def _confidence(dimensions: DecisionDimensions, *, generation_required: bool) -> float:
    if not generation_required:
        return map_dimension_confidence(
            dimensions.reuse_opportunity,
            {
                DimensionLevel.HIGH: 0.9,
                DimensionLevel.MEDIUM: 0.85,
                DimensionLevel.LOW: 0.7,
                DimensionLevel.UNKNOWN: 0.5,
            },
        )
    return map_dimension_confidence(
        dimensions.generation_requirement,
        {
            DimensionLevel.HIGH: 0.65,
            DimensionLevel.MEDIUM: 0.7,
            DimensionLevel.LOW: 0.55,
            DimensionLevel.UNKNOWN: 0.5,
        },
    )


def _diagnostics(
    strategy: StrategyDecisionSnapshot,
    reuse_plan: ReusePlanSnapshot,
    scope: GenerationScope,
    generation_required: bool,
    dimensions: DecisionDimensions,
    target_count: int,
) -> dict[str, str]:
    return {
        "posture": strategy.primary_posture.value,
        "reuse_mode": reuse_plan.reuse_mode.value,
        "generation_scope": scope.value,
        "generation_required": str(generation_required).lower(),
        "generation_requirement": dimensions.generation_requirement.value,
        "confidence": confidence_string(_confidence(dimensions, generation_required=generation_required)),
        "generation_target_count": str(target_count),
    }


def _provider_factors(
    dimensions: DecisionDimensions,
    scope: GenerationScope,
    target_count: int,
) -> tuple[str, ...]:
    return (
        provider_name_factor(_PROVIDER_NAME),
        f"generation_scope:{scope.value}",
        f"generation_targets:{target_count}",
        dimension_factor("generation_requirement", dimensions.generation_requirement),
        dimension_factor("reuse_opportunity", dimensions.reuse_opportunity),
    )
