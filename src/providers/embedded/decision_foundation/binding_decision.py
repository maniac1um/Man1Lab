"""Resource binding decision from facts and dimensions."""

from __future__ import annotations

from dataclasses import dataclass

from models.execution_planning_runtime import StrategyDecisionSnapshot
from models.execution_strategy import (
    BindingRole,
    ResourceBinding,
    StrategyPosture,
    UsageIntent,
)
from models.research_resource_discovery import NeedCategory, VerificationStatus
from providers.embedded.decision_foundation.common import dimension_factor, provider_name_factor
from providers.embedded.decision_foundation.dimensions import DecisionDimensions, DimensionLevel
from providers.embedded.decision_foundation.facts import ObservedFacts, SelectedResourceFact

_PROVIDER_NAME = "embedded_resource_binding"


@dataclass(frozen=True)
class BindingDecision:
    bindings: tuple[ResourceBinding, ...]
    anchor_binding_id: str | None
    combination_rationale: str
    selection_alignment_summary: str
    decision_notes: str
    provider_factors: tuple[str, ...]
    diagnostics: dict[str, str]
    warnings: tuple[str, ...]


def decide_bindings(
    facts: ObservedFacts,
    dimensions: DecisionDimensions,
    strategy: StrategyDecisionSnapshot,
) -> BindingDecision:
    if strategy.primary_posture == StrategyPosture.GREENFIELD:
        return BindingDecision(
            bindings=(),
            anchor_binding_id=None,
            combination_rationale="Greenfield posture — no discovery resources bound.",
            selection_alignment_summary="No discovery selection alignment — greenfield posture.",
            decision_notes="Greenfield posture selected; skipping resource bindings.",
            provider_factors=_provider_factors(dimensions, bound_count=0),
            diagnostics={"posture": strategy.primary_posture.value},
            warnings=(),
        )

    bindings: list[ResourceBinding] = []
    notes: list[str] = ["Evaluating discovery selections for resource binding."]
    warnings: list[str] = []
    selection_ids: list[str] = []

    if facts.selected_repository is not None:
        binding = _bind_primary_if_usable(
            facts.selected_repository,
            role=BindingRole.PRIMARY_REPOSITORY,
            usage_intent=UsageIntent.EXECUTE_DIRECTLY,
            rationale=_repository_binding_rationale(facts.selected_repository),
            dimensions=dimensions,
        )
        if binding is not None:
            bindings.append(binding)
            selection_ids.append(facts.selected_repository.selection_id)
            notes.append(f"PRIMARY_REPOSITORY bound: {facts.selected_repository.candidate_id}")
        else:
            notes.append(
                f"Repository not bound as primary: verification="
                f"{facts.selected_repository.verification_status}"
            )
            warnings.append("Selected repository is not verified for primary binding.")

    if facts.selected_checkpoint is not None:
        binding = _bind_primary_if_verified(
            facts.selected_checkpoint,
            role=BindingRole.CHECKPOINT,
            usage_intent=UsageIntent.EXTRACT_ASSETS_FROM,
            rationale="Verified selected checkpoint bound as primary checkpoint.",
            dimensions=dimensions,
        )
        if binding is not None:
            bindings.append(binding)
            selection_ids.append(facts.selected_checkpoint.selection_id)
            notes.append(f"PRIMARY_CHECKPOINT bound: {facts.selected_checkpoint.candidate_id}")
        else:
            notes.append("Checkpoint selection not verified; skipped primary checkpoint binding.")

    if facts.selected_dataset is not None:
        binding = _bind_primary_if_verified(
            facts.selected_dataset,
            role=BindingRole.DATASET,
            usage_intent=UsageIntent.EXTRACT_ASSETS_FROM,
            rationale="Verified selected dataset bound as primary dataset.",
            dimensions=dimensions,
        )
        if binding is not None:
            bindings.append(binding)
            selection_ids.append(facts.selected_dataset.selection_id)
            notes.append(f"PRIMARY_DATASET bound: {facts.selected_dataset.candidate_id}")
        else:
            notes.append("Dataset selection not verified; skipped primary dataset binding.")

    for index, resource in enumerate(facts.supplementary_resources, start=1):
        if not _is_verified(resource):
            notes.append(f"Supplementary resource skipped (unverified): {resource.candidate_id}")
            continue
        role = (
            BindingRole.FALLBACK_REPOSITORY
            if resource.need_category == NeedCategory.CODE_REPOSITORY
            else BindingRole.SUPPORTING_ASSET
        )
        usage = (
            UsageIntent.FALLBACK_IF_PRIMARY_FAILS
            if role == BindingRole.FALLBACK_REPOSITORY
            else UsageIntent.REFERENCE_ONLY
        )
        bindings.append(
            ResourceBinding(
                binding_id=f"binding-supplementary-{index}-{resource.candidate_id}",
                candidate_id=resource.candidate_id,
                selection_id=resource.selection_id,
                resource_need_id=resource.need_id,
                role=role,
                usage_intent=usage,
                binding_rationale="Verified supplementary discovery selection.",
            )
        )
        notes.append(f"{role.value} bound: {resource.candidate_id}")

    anchor = bindings[0].binding_id if bindings else None
    if not bindings and strategy.primary_posture != StrategyPosture.GREENFIELD:
        warnings.append("No verified discovery selections available for binding.")

    alignment = (
        f"Aligned with discovery selections: {', '.join(sorted(set(selection_ids)))}"
        if selection_ids
        else "No verified discovery selections bound."
    )
    return BindingDecision(
        bindings=tuple(bindings),
        anchor_binding_id=anchor,
        combination_rationale="Bindings derived from verified discovery selections only.",
        selection_alignment_summary=alignment,
        decision_notes="\n".join(notes),
        provider_factors=_provider_factors(dimensions, bound_count=len(bindings)),
        diagnostics={
            "posture": strategy.primary_posture.value,
            "resource_sufficiency": dimensions.resource_sufficiency.value,
            "resource_reliability": dimensions.resource_reliability.value,
        },
        warnings=tuple(warnings),
    )


def _bind_primary_if_verified(
    resource: SelectedResourceFact,
    *,
    role: BindingRole,
    usage_intent: UsageIntent,
    rationale: str,
    dimensions: DecisionDimensions,
) -> ResourceBinding | None:
    if not _is_verified(resource):
        return None
    return _bind_primary_if_usable(
        resource,
        role=role,
        usage_intent=usage_intent,
        rationale=rationale,
        dimensions=dimensions,
    )


def _bind_primary_if_usable(
    resource: SelectedResourceFact,
    *,
    role: BindingRole,
    usage_intent: UsageIntent,
    rationale: str,
    dimensions: DecisionDimensions,
) -> ResourceBinding | None:
    if not _is_usable(resource):
        return None
    if role == BindingRole.PRIMARY_REPOSITORY and dimensions.resource_reliability == DimensionLevel.LOW:
        return None
    return ResourceBinding(
        binding_id=f"binding-{role.value}-{resource.candidate_id}",
        candidate_id=resource.candidate_id,
        selection_id=resource.selection_id,
        resource_need_id=resource.need_id,
        role=role,
        usage_intent=usage_intent,
        binding_rationale=rationale,
    )


def _repository_binding_rationale(resource: SelectedResourceFact) -> str:
    if resource.verification_status == VerificationStatus.PARTIAL:
        return (
            "Partially verified selected repository bound as primary; "
            "adaptation stage may authorize remediation."
        )
    return "Verified selected official repository bound as primary."


def _is_usable(resource: SelectedResourceFact) -> bool:
    return resource.verification_status in {
        VerificationStatus.PASS,
        VerificationStatus.PARTIAL,
    }


def _is_verified(resource: SelectedResourceFact) -> bool:
    return resource.verification_status == VerificationStatus.PASS


def _provider_factors(dimensions: DecisionDimensions, *, bound_count: int) -> tuple[str, ...]:
    return (
        provider_name_factor(_PROVIDER_NAME),
        f"bindings:{bound_count}",
        dimension_factor("resource_sufficiency", dimensions.resource_sufficiency),
        dimension_factor("resource_reliability", dimensions.resource_reliability),
        dimension_factor("reuse_opportunity", dimensions.reuse_opportunity),
    )
