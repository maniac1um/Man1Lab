from __future__ import annotations

from datetime import datetime

from models.execution_strategy import (
    SCHEMA_VERSION,
    AdaptationPlan,
    AdaptationScope,
    AdaptationTrigger,
    AdaptationTriggerType,
    AnalysisModule,
    AnalysisReference,
    AuthorizationLevel,
    BindingRole,
    DecisionCategory,
    DecisionRecord,
    DiscoveryReference,
    ExcludedComponent,
    ExecutionStrategy,
    FallbackStrategy,
    GenerationIntent,
    GenerationPlan,
    GenerationPriority,
    GenerationScope,
    GenerationTarget,
    InputReferences,
    ManualAction,
    ModificationClass,
    PlanningInvocationReason,
    PlanningStatus,
    Provenance,
    RejectedPosture,
    ResourceBinding,
    ResourceBindings,
    ReuseComponent,
    ReuseExtent,
    ReuseMode,
    ReusePlan,
    RiskAssessment,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
    ScopeCommitment,
    Strategy,
    StrategyMetadata,
    StrategyPosture,
    UsageIntent,
)
from models.research_resource_discovery import DiscoveryStatus
from validation.exceptions import ExecutionStrategyValidationError


def validate_execution_strategy(data: dict) -> None:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError("Execution strategy data must be a dict")

    _require_dict(data, "metadata")
    _require_dict(data, "input_references")
    _require_dict(data, "strategy")
    _validate_schema_version(data.get("schema_version"))

    metadata = data["metadata"]
    _require_non_empty_string(metadata, "strategy_id", path="metadata")
    _validate_planning_status(metadata.get("status"), path="metadata.status")

    input_references = data["input_references"]
    _require_dict(input_references, "analysis_reference")
    _require_dict(input_references, "discovery_reference")
    analysis_reference = input_references["analysis_reference"]
    discovery_reference = input_references["discovery_reference"]
    _require_non_empty_string(
        analysis_reference, "analysis_content_hash", path="input_references.analysis_reference"
    )
    _require_non_empty_string(discovery_reference, "discovery_id", path="input_references.discovery_reference")
    _require_non_empty_string(
        discovery_reference, "discovery_content_hash", path="input_references.discovery_reference"
    )

    strategy = data["strategy"]
    _validate_strategy_posture(strategy.get("primary_posture"), path="strategy.primary_posture")
    _validate_scope_commitment(strategy.get("scope_commitment"), path="strategy.scope_commitment")
    _require_non_empty_string(strategy, "rationale", path="strategy")

    bindings = _binding_list(data)
    reuse_components = _reuse_component_list(data)
    risk_records = _risk_record_list(data)
    manual_actions = _manual_action_list(data)
    decision_records = _decision_record_list(data)
    generation_targets = _generation_target_list(data)
    authorized_modifications = _authorized_modification_list(data)

    _validate_binding_uniqueness(bindings)
    _validate_candidate_id_uniqueness(bindings)
    _validate_reuse_component_binding_uniqueness(reuse_components)
    _validate_risk_id_uniqueness(risk_records)
    _validate_manual_action_uniqueness(manual_actions)
    _validate_fallback_order_uniqueness(data)
    _validate_decision_id_uniqueness(decision_records)
    _validate_generation_target_uniqueness(generation_targets)
    _validate_authorized_modification_uniqueness(authorized_modifications)
    _validate_cross_references(data)
    _validate_metadata_counts(metadata, bindings, risk_records)
    _validate_conditional_fields(strategy, bindings)


def normalize_execution_strategy(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError("Execution strategy data must be a dict")

    metadata = _normalize_metadata(data.get("metadata", {}))
    input_references = _normalize_input_references(data.get("input_references", {}))
    strategy = _normalize_strategy(data.get("strategy", {}))
    resource_bindings = _normalize_resource_bindings(data.get("resource_bindings", {}))
    reuse_plan = _normalize_reuse_plan(data.get("reuse_plan", {}))
    adaptation_plan = _normalize_adaptation_plan(data.get("adaptation_plan", {}))
    generation_plan = _normalize_generation_plan(data.get("generation_plan", {}))
    risk_assessment = _normalize_risk_assessment(data.get("risk_assessment", {}))
    provenance = _normalize_provenance(data.get("provenance", {}))
    schema_version = _normalize_schema_version(data.get("schema_version"))

    return {
        "metadata": metadata,
        "input_references": input_references,
        "strategy": strategy,
        "resource_bindings": resource_bindings,
        "reuse_plan": reuse_plan,
        "adaptation_plan": adaptation_plan,
        "generation_plan": generation_plan,
        "risk_assessment": risk_assessment,
        "provenance": provenance,
        "schema_version": schema_version,
    }


def build_execution_strategy(data: dict) -> ExecutionStrategy:
    validate_execution_strategy(data)
    normalized = normalize_execution_strategy(data)
    return ExecutionStrategy(
        metadata=StrategyMetadata(**normalized["metadata"]),
        input_references=InputReferences(
            analysis_reference=AnalysisReference(**normalized["input_references"]["analysis_reference"]),
            discovery_reference=DiscoveryReference(**normalized["input_references"]["discovery_reference"]),
        ),
        strategy=Strategy(**normalized["strategy"]),
        resource_bindings=ResourceBindings(**normalized["resource_bindings"]),
        reuse_plan=ReusePlan(**normalized["reuse_plan"]),
        adaptation_plan=AdaptationPlan(**normalized["adaptation_plan"]),
        generation_plan=GenerationPlan(**normalized["generation_plan"]),
        risk_assessment=RiskAssessment(**normalized["risk_assessment"]),
        provenance=Provenance(**normalized["provenance"]),
        schema_version=normalized["schema_version"],
    )


def _normalize_metadata(data: dict) -> dict:
    _require_dict_instance(data, "metadata")
    return {
        "strategy_id": _require_non_empty_string(data, "strategy_id", path="metadata"),
        "created_at": _normalize_datetime(data.get("created_at"), path="metadata.created_at"),
        "status": _normalize_planning_status(data.get("status"), path="metadata.status"),
        "summary": _normalize_optional_string(data.get("summary")),
        "reproduction_scope": _normalize_optional_string(data.get("reproduction_scope"), "unknown"),
        "invocation_reason": _normalize_planning_invocation_reason(
            data.get("invocation_reason"), path="metadata.invocation_reason"
        ),
        "strategy_posture": _normalize_strategy_posture(
            data.get("strategy_posture"),
            path="metadata.strategy_posture",
            default=StrategyPosture.MANUAL,
        ),
        "binding_count": _normalize_int(data.get("binding_count"), default=0),
        "blocking_risk_count": _normalize_int(data.get("blocking_risk_count"), default=0),
        "manual_action_required": bool(data.get("manual_action_required", False)),
    }


def _normalize_input_references(data: dict) -> dict:
    _require_dict_instance(data, "input_references")
    analysis_reference = data.get("analysis_reference", {})
    discovery_reference = data.get("discovery_reference", {})
    if not isinstance(analysis_reference, dict):
        raise ExecutionStrategyValidationError("Missing required field: input_references.analysis_reference")
    if not isinstance(discovery_reference, dict):
        raise ExecutionStrategyValidationError("Missing required field: input_references.discovery_reference")
    return {
        "analysis_reference": _normalize_analysis_reference(analysis_reference),
        "discovery_reference": _normalize_discovery_reference(discovery_reference),
    }


def _normalize_analysis_reference(data: dict) -> dict:
    gap_categories = data.get("analysis_gap_categories", [])
    if gap_categories is None:
        gap_categories = []
    if not isinstance(gap_categories, list):
        raise ExecutionStrategyValidationError(
            "Invalid field: input_references.analysis_reference.analysis_gap_categories must be a list"
        )
    return {
        "analysis_schema_version": _require_non_empty_string(
            data, "analysis_schema_version", path="input_references.analysis_reference"
        ),
        "paper_title": _require_non_empty_string(data, "paper_title", path="input_references.analysis_reference"),
        "arxiv_id": _normalize_optional_string(data.get("arxiv_id")),
        "analysis_content_hash": _require_non_empty_string(
            data, "analysis_content_hash", path="input_references.analysis_reference"
        ),
        "reproduction_scope": _normalize_optional_string(data.get("reproduction_scope"), "unknown"),
        "analysis_gap_categories": [
            _normalize_optional_string(item) for item in gap_categories if _normalize_optional_string(item)
        ],
    }


def _normalize_discovery_reference(data: dict) -> dict:
    selection_ids = data.get("selection_ids_used", [])
    if selection_ids is None:
        selection_ids = []
    if not isinstance(selection_ids, list):
        raise ExecutionStrategyValidationError(
            "Invalid field: input_references.discovery_reference.selection_ids_used must be a list"
        )
    return {
        "discovery_schema_version": _require_non_empty_string(
            data, "discovery_schema_version", path="input_references.discovery_reference"
        ),
        "discovery_id": _require_non_empty_string(data, "discovery_id", path="input_references.discovery_reference"),
        "discovery_content_hash": _require_non_empty_string(
            data, "discovery_content_hash", path="input_references.discovery_reference"
        ),
        "discovery_status": _normalize_discovery_status(
            data.get("discovery_status"), path="input_references.discovery_reference.discovery_status"
        ),
        "selection_ids_used": [
            _normalize_optional_string(item) for item in selection_ids if _normalize_optional_string(item)
        ],
        "unresolved_discovery_gap_count": _normalize_int(
            data.get("unresolved_discovery_gap_count"), default=0
        ),
    }


def _normalize_strategy(data: dict) -> dict:
    _require_dict_instance(data, "strategy")
    rejected = data.get("alternative_postures_rejected", [])
    if rejected is None:
        rejected = []
    if not isinstance(rejected, list):
        raise ExecutionStrategyValidationError("Invalid field: strategy.alternative_postures_rejected must be a list")
    deciding_factors = data.get("deciding_factors", [])
    if deciding_factors is None:
        deciding_factors = []
    if not isinstance(deciding_factors, list):
        raise ExecutionStrategyValidationError("Invalid field: strategy.deciding_factors must be a list")
    return {
        "primary_posture": _normalize_strategy_posture(
            data.get("primary_posture"), path="strategy.primary_posture"
        ),
        "scope_commitment": _normalize_scope_commitment(
            data.get("scope_commitment"), path="strategy.scope_commitment"
        ),
        "scope_narrowing_rationale": _normalize_optional_string(data.get("scope_narrowing_rationale")) or None,
        "rationale": _require_non_empty_string(data, "rationale", path="strategy"),
        "deciding_factors": [
            _normalize_optional_string(item) for item in deciding_factors if _normalize_optional_string(item)
        ],
        "confidence": _normalize_float(data.get("confidence"), default=0.0),
        "alternative_postures_rejected": [
            _normalize_rejected_posture(item, index) for index, item in enumerate(rejected)
        ],
    }


def _normalize_rejected_posture(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(
            f"Invalid rejected posture at strategy.alternative_postures_rejected[{index}]"
        )
    return {
        "posture": _normalize_strategy_posture(data.get("posture"), path="strategy.rejected_posture.posture"),
        "rejection_reason": _normalize_optional_string(data.get("rejection_reason")),
        "related_discovery_gap_id": _normalize_optional_string(data.get("related_discovery_gap_id")) or None,
    }


def _normalize_resource_bindings(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"bindings": [], "anchor_binding_id": None, "combination_rationale": ""}
    bindings = data.get("bindings", [])
    if bindings is None:
        bindings = []
    if not isinstance(bindings, list):
        raise ExecutionStrategyValidationError("Invalid field: resource_bindings.bindings must be a list")
    return {
        "bindings": [_normalize_resource_binding(item, index) for index, item in enumerate(bindings)],
        "anchor_binding_id": _normalize_optional_string(data.get("anchor_binding_id")) or None,
        "combination_rationale": _normalize_optional_string(data.get("combination_rationale")),
    }


def _normalize_resource_binding(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid resource binding at index {index}")
    return {
        "binding_id": _require_non_empty_string(data, "binding_id", path=f"resource_bindings.bindings[{index}]"),
        "candidate_id": _require_non_empty_string(
            data, "candidate_id", path=f"resource_bindings.bindings[{index}]"
        ),
        "selection_id": _normalize_optional_string(data.get("selection_id")) or None,
        "resource_need_id": _normalize_optional_string(data.get("resource_need_id")) or None,
        "role": _normalize_binding_role(data.get("role"), path=f"resource_bindings.bindings[{index}].role"),
        "usage_intent": _normalize_usage_intent(
            data.get("usage_intent"), path=f"resource_bindings.bindings[{index}].usage_intent"
        ),
        "binding_rationale": _normalize_optional_string(data.get("binding_rationale")),
        "overrides_discovery_selection": bool(data.get("overrides_discovery_selection", False)),
        "override_rationale": _normalize_optional_string(data.get("override_rationale")) or None,
    }


def _normalize_reuse_plan(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "reuse_mode": ReuseMode.NOT_APPLICABLE.value,
            "primary_reuse_binding_id": None,
            "components_to_reuse": [],
            "components_excluded": [],
            "reuse_assumptions": [],
            "reuse_limitations": [],
        }
    components = data.get("components_to_reuse", [])
    excluded = data.get("components_excluded", [])
    assumptions = data.get("reuse_assumptions", [])
    limitations = data.get("reuse_limitations", [])
    for field_name, value in (
        ("components_to_reuse", components),
        ("components_excluded", excluded),
        ("reuse_assumptions", assumptions),
        ("reuse_limitations", limitations),
    ):
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ExecutionStrategyValidationError(f"Invalid field: reuse_plan.{field_name} must be a list")
    return {
        "reuse_mode": _normalize_reuse_mode(data.get("reuse_mode"), path="reuse_plan.reuse_mode").value,
        "primary_reuse_binding_id": _normalize_optional_string(data.get("primary_reuse_binding_id")) or None,
        "components_to_reuse": [
            _normalize_reuse_component(item, index) for index, item in enumerate(components)
        ],
        "components_excluded": [
            _normalize_excluded_component(item, index) for index, item in enumerate(excluded)
        ],
        "reuse_assumptions": [
            _normalize_optional_string(item) for item in assumptions if _normalize_optional_string(item)
        ],
        "reuse_limitations": [
            _normalize_optional_string(item) for item in limitations if _normalize_optional_string(item)
        ],
    }


def _normalize_reuse_component(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid reuse component at index {index}")
    return {
        "binding_id": _require_non_empty_string(
            data, "binding_id", path=f"reuse_plan.components_to_reuse[{index}]"
        ),
        "component_label": _require_non_empty_string(
            data, "component_label", path=f"reuse_plan.components_to_reuse[{index}]"
        ),
        "reuse_extent": _normalize_reuse_extent(
            data.get("reuse_extent"), path=f"reuse_plan.components_to_reuse[{index}].reuse_extent"
        ).value,
    }


def _normalize_excluded_component(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid excluded component at index {index}")
    return {
        "candidate_id": _require_non_empty_string(
            data, "candidate_id", path=f"reuse_plan.components_excluded[{index}]"
        ),
        "exclusion_reason": _normalize_optional_string(data.get("exclusion_reason")),
    }


def _normalize_adaptation_plan(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "adaptation_required": False,
            "adaptation_scope": AdaptationScope.NONE.value,
            "authorized_modifications": [],
            "adaptation_constraints": [],
            "adaptation_triggers": [],
            "adaptation_deferred": False,
        }
    authorized = data.get("authorized_modifications", [])
    constraints = data.get("adaptation_constraints", [])
    triggers = data.get("adaptation_triggers", [])
    for field_name, value in (
        ("authorized_modifications", authorized),
        ("adaptation_constraints", constraints),
        ("adaptation_triggers", triggers),
    ):
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ExecutionStrategyValidationError(f"Invalid field: adaptation_plan.{field_name} must be a list")
    return {
        "adaptation_required": bool(data.get("adaptation_required", False)),
        "adaptation_scope": _normalize_adaptation_scope(
            data.get("adaptation_scope"), path="adaptation_plan.adaptation_scope"
        ).value,
        "authorized_modifications": [
            _normalize_authorized_modification(item, index) for index, item in enumerate(authorized)
        ],
        "adaptation_constraints": [
            _normalize_optional_string(item) for item in constraints if _normalize_optional_string(item)
        ],
        "adaptation_triggers": [
            _normalize_adaptation_trigger(item, index) for index, item in enumerate(triggers)
        ],
        "adaptation_deferred": bool(data.get("adaptation_deferred", False)),
    }


def _normalize_authorized_modification(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(
            f"Invalid authorized modification at adaptation_plan.authorized_modifications[{index}]"
        )
    return {
        "modification_class": _normalize_modification_class(
            data.get("modification_class"),
            path=f"adaptation_plan.authorized_modifications[{index}].modification_class",
        ).value,
        "target_binding_id": _normalize_optional_string(data.get("target_binding_id")) or None,
        "authorization_level": _normalize_authorization_level(
            data.get("authorization_level"),
            path=f"adaptation_plan.authorized_modifications[{index}].authorization_level",
        ).value,
    }


def _normalize_adaptation_trigger(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid adaptation trigger at index {index}")
    return {
        "trigger_type": _normalize_adaptation_trigger_type(
            data.get("trigger_type"), path=f"adaptation_plan.adaptation_triggers[{index}].trigger_type"
        ).value,
        "description": _normalize_optional_string(data.get("description")),
        "related_discovery_gap_id": _normalize_optional_string(data.get("related_discovery_gap_id")) or None,
    }


def _normalize_generation_plan(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "generation_required": False,
            "generation_scope": GenerationScope.NONE.value,
            "modules_to_generate": [],
            "generation_constraints": [],
            "generation_rationale": "",
            "reuse_fallback_after_generation": False,
        }
    modules = data.get("modules_to_generate", [])
    constraints = data.get("generation_constraints", [])
    if modules is None:
        modules = []
    if constraints is None:
        constraints = []
    if not isinstance(modules, list) or not isinstance(constraints, list):
        raise ExecutionStrategyValidationError("Invalid field: generation_plan list fields must be lists")
    return {
        "generation_required": bool(data.get("generation_required", False)),
        "generation_scope": _normalize_generation_scope(
            data.get("generation_scope"), path="generation_plan.generation_scope"
        ).value,
        "modules_to_generate": [
            _normalize_generation_target(item, index) for index, item in enumerate(modules)
        ],
        "generation_constraints": [
            _normalize_optional_string(item) for item in constraints if _normalize_optional_string(item)
        ],
        "generation_rationale": _normalize_optional_string(data.get("generation_rationale")),
        "reuse_fallback_after_generation": bool(data.get("reuse_fallback_after_generation", False)),
    }


def _normalize_generation_target(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid generation target at index {index}")
    return {
        "analysis_module": _normalize_analysis_module(
            data.get("analysis_module"),
            path=f"generation_plan.modules_to_generate[{index}].analysis_module",
        ).value,
        "generation_intent": _normalize_generation_intent(
            data.get("generation_intent"),
            path=f"generation_plan.modules_to_generate[{index}].generation_intent",
        ).value,
        "priority": _normalize_generation_priority(
            data.get("priority"), path=f"generation_plan.modules_to_generate[{index}].priority"
        ).value,
    }


def _normalize_risk_assessment(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "overall_confidence": 0.0,
            "blocking_risks": [],
            "degraded_risks": [],
            "informational_risks": [],
            "fallback_strategies": [],
            "accepted_discovery_gap_ids": [],
            "manual_actions_required": [],
            "abort_conditions": [],
        }

    def _list_field(name: str) -> list:
        value = data.get(name, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ExecutionStrategyValidationError(f"Invalid field: risk_assessment.{name} must be a list")
        return value

    blocking = _list_field("blocking_risks")
    degraded = _list_field("degraded_risks")
    informational = _list_field("informational_risks")
    fallbacks = _list_field("fallback_strategies")
    accepted_gaps = _list_field("accepted_discovery_gap_ids")
    manual_actions = _list_field("manual_actions_required")
    abort_conditions = _list_field("abort_conditions")

    return {
        "overall_confidence": _normalize_float(data.get("overall_confidence"), default=0.0),
        "blocking_risks": [_normalize_risk_record(item, index, "blocking") for index, item in enumerate(blocking)],
        "degraded_risks": [_normalize_risk_record(item, index, "degraded") for index, item in enumerate(degraded)],
        "informational_risks": [
            _normalize_risk_record(item, index, "informational") for index, item in enumerate(informational)
        ],
        "fallback_strategies": [
            _normalize_fallback_strategy(item, index) for index, item in enumerate(fallbacks)
        ],
        "accepted_discovery_gap_ids": [
            _normalize_optional_string(item) for item in accepted_gaps if _normalize_optional_string(item)
        ],
        "manual_actions_required": [
            _normalize_manual_action(item, index) for index, item in enumerate(manual_actions)
        ],
        "abort_conditions": [
            _normalize_optional_string(item) for item in abort_conditions if _normalize_optional_string(item)
        ],
    }


def _normalize_risk_record(data: dict, index: int, bucket: str) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid risk record in risk_assessment.{bucket}_risks[{index}]")
    return {
        "risk_id": _require_non_empty_string(data, "risk_id", path=f"risk_assessment.{bucket}_risks[{index}]"),
        "severity": _normalize_risk_severity(
            data.get("severity"), path=f"risk_assessment.{bucket}_risks[{index}].severity"
        ).value,
        "category": _normalize_risk_category(
            data.get("category"), path=f"risk_assessment.{bucket}_risks[{index}].category"
        ).value,
        "description": _normalize_optional_string(data.get("description")),
        "mitigation": _normalize_optional_string(data.get("mitigation")),
        "related_binding_id": _normalize_optional_string(data.get("related_binding_id")) or None,
        "related_discovery_gap_id": _normalize_optional_string(data.get("related_discovery_gap_id")) or None,
    }


def _normalize_fallback_strategy(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid fallback strategy at index {index}")
    binding_ids = data.get("fallback_binding_ids", [])
    if binding_ids is None:
        binding_ids = []
    if not isinstance(binding_ids, list):
        raise ExecutionStrategyValidationError(
            "Invalid field: risk_assessment.fallback_strategies.fallback_binding_ids must be a list"
        )
    return {
        "fallback_order": _normalize_int(data.get("fallback_order"), default=index + 1),
        "posture": _normalize_strategy_posture(
            data.get("posture"), path=f"risk_assessment.fallback_strategies[{index}].posture"
        ).value,
        "trigger_condition": _normalize_optional_string(data.get("trigger_condition")),
        "fallback_binding_ids": [
            _normalize_optional_string(item) for item in binding_ids if _normalize_optional_string(item)
        ],
    }


def _normalize_manual_action(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid manual action at index {index}")
    return {
        "action_id": _require_non_empty_string(
            data, "action_id", path=f"risk_assessment.manual_actions_required[{index}]"
        ),
        "description": _normalize_optional_string(data.get("description")),
        "blocks_planner": bool(data.get("blocks_planner", False)),
    }


def _normalize_provenance(data: dict) -> dict:
    if not isinstance(data, dict):
        return {
            "planning_run_id": "",
            "pipeline_version": "",
            "stage_timestamps": {},
            "degradation_notes": [],
            "configuration_fingerprint": "",
            "decision_trace": [],
            "rerun_of": None,
        }
    timestamps = data.get("stage_timestamps", {})
    notes = data.get("degradation_notes", [])
    trace = data.get("decision_trace", [])
    if timestamps is None:
        timestamps = {}
    if notes is None:
        notes = []
    if trace is None:
        trace = []
    if not isinstance(timestamps, dict):
        raise ExecutionStrategyValidationError("Invalid field: provenance.stage_timestamps must be a dict")
    if not isinstance(notes, list) or not isinstance(trace, list):
        raise ExecutionStrategyValidationError("Invalid field: provenance list fields must be lists")
    return {
        "planning_run_id": _normalize_optional_string(data.get("planning_run_id")),
        "pipeline_version": _normalize_optional_string(data.get("pipeline_version")),
        "stage_timestamps": {
            str(key): _normalize_datetime(value, path=f"provenance.stage_timestamps.{key}")
            for key, value in timestamps.items()
        },
        "degradation_notes": [
            _normalize_optional_string(item) for item in notes if _normalize_optional_string(item)
        ],
        "configuration_fingerprint": _normalize_optional_string(data.get("configuration_fingerprint")),
        "decision_trace": [_normalize_decision_record(item, index) for index, item in enumerate(trace)],
        "rerun_of": _normalize_optional_string(data.get("rerun_of")) or None,
    }


def _normalize_decision_record(data: dict, index: int) -> dict:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Invalid decision record at provenance.decision_trace[{index}]")
    inputs = data.get("inputs_consulted", [])
    if inputs is None:
        inputs = []
    if not isinstance(inputs, list):
        raise ExecutionStrategyValidationError("Invalid field: decision_record.inputs_consulted must be a list")
    return {
        "decision_id": _require_non_empty_string(
            data, "decision_id", path=f"provenance.decision_trace[{index}]"
        ),
        "decision_category": _normalize_decision_category(
            data.get("decision_category"),
            path=f"provenance.decision_trace[{index}].decision_category",
        ).value,
        "summary": _normalize_optional_string(data.get("summary")),
        "inputs_consulted": [
            _normalize_optional_string(item) for item in inputs if _normalize_optional_string(item)
        ],
        "timestamp": _normalize_optional_datetime(data.get("timestamp")),
    }


def _binding_list(data: dict) -> list[dict]:
    bindings = data.get("resource_bindings", {})
    if not isinstance(bindings, dict):
        return []
    items = bindings.get("bindings", [])
    return items if isinstance(items, list) else []


def _reuse_component_list(data: dict) -> list[dict]:
    reuse_plan = data.get("reuse_plan", {})
    if not isinstance(reuse_plan, dict):
        return []
    items = reuse_plan.get("components_to_reuse", [])
    return items if isinstance(items, list) else []


def _risk_record_list(data: dict) -> list[dict]:
    risk = data.get("risk_assessment", {})
    if not isinstance(risk, dict):
        return []
    records: list[dict] = []
    for bucket in ("blocking_risks", "degraded_risks", "informational_risks"):
        items = risk.get(bucket, [])
        if isinstance(items, list):
            records.extend(item for item in items if isinstance(item, dict))
    return records


def _manual_action_list(data: dict) -> list[dict]:
    risk = data.get("risk_assessment", {})
    if not isinstance(risk, dict):
        return []
    items = risk.get("manual_actions_required", [])
    return items if isinstance(items, list) else []


def _decision_record_list(data: dict) -> list[dict]:
    provenance = data.get("provenance", {})
    if not isinstance(provenance, dict):
        return []
    items = provenance.get("decision_trace", [])
    return items if isinstance(items, list) else []


def _generation_target_list(data: dict) -> list[dict]:
    generation_plan = data.get("generation_plan", {})
    if not isinstance(generation_plan, dict):
        return []
    items = generation_plan.get("modules_to_generate", [])
    return items if isinstance(items, list) else []


def _authorized_modification_list(data: dict) -> list[dict]:
    adaptation_plan = data.get("adaptation_plan", {})
    if not isinstance(adaptation_plan, dict):
        return []
    items = adaptation_plan.get("authorized_modifications", [])
    return items if isinstance(items, list) else []


def _validate_binding_uniqueness(bindings: list[dict]) -> None:
    seen: set[str] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            raise ExecutionStrategyValidationError(f"Invalid resource binding at index {index}")
        binding_id = binding.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid binding_id at index {index}")
        if binding_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate binding_id: {binding_id}")
        seen.add(binding_id)
        _validate_binding_role(binding.get("role"), path=f"resource_bindings.bindings[{index}].role")
        _validate_usage_intent(binding.get("usage_intent"), path=f"resource_bindings.bindings[{index}].usage_intent")


def _validate_candidate_id_uniqueness(bindings: list[dict]) -> None:
    seen: set[str] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            continue
        candidate_id = binding.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid candidate_id at bindings[{index}]")
        if candidate_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate candidate_id in bindings: {candidate_id}")
        seen.add(candidate_id)


def _validate_reuse_component_binding_uniqueness(components: list[dict]) -> None:
    seen: set[str] = set()
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            raise ExecutionStrategyValidationError(f"Invalid reuse component at index {index}")
        binding_id = component.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid reuse component binding_id at index {index}")
        if binding_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate reuse component binding_id: {binding_id}")
        seen.add(binding_id)
        label = component.get("component_label")
        if not isinstance(label, str) or not label.strip():
            raise ExecutionStrategyValidationError(f"Invalid component_label at reuse component index {index}")


def _validate_risk_id_uniqueness(records: list[dict]) -> None:
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ExecutionStrategyValidationError(f"Invalid risk record at index {index}")
        risk_id = record.get("risk_id")
        if not isinstance(risk_id, str) or not risk_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid risk_id at index {index}")
        if risk_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate risk_id: {risk_id}")
        seen.add(risk_id)
        _validate_risk_severity(record.get("severity"), path=f"risk_assessment.risks[{index}].severity")
        _validate_risk_category(record.get("category"), path=f"risk_assessment.risks[{index}].category")


def _validate_manual_action_uniqueness(actions: list[dict]) -> None:
    seen: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ExecutionStrategyValidationError(f"Invalid manual action at index {index}")
        action_id = action.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid action_id at index {index}")
        if action_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate action_id: {action_id}")
        seen.add(action_id)


def _validate_fallback_order_uniqueness(data: dict) -> None:
    risk = data.get("risk_assessment", {})
    if not isinstance(risk, dict):
        return
    fallbacks = risk.get("fallback_strategies", [])
    if not isinstance(fallbacks, list):
        return
    seen: set[int] = set()
    for index, fallback in enumerate(fallbacks):
        if not isinstance(fallback, dict):
            continue
        order = fallback.get("fallback_order")
        if not isinstance(order, int):
            raise ExecutionStrategyValidationError(f"Invalid fallback_order at index {index}")
        if order in seen:
            raise ExecutionStrategyValidationError(f"Duplicate fallback_order: {order}")
        seen.add(order)
        _validate_strategy_posture(fallback.get("posture"), path=f"risk_assessment.fallback_strategies[{index}].posture")


def _validate_decision_id_uniqueness(records: list[dict]) -> None:
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ExecutionStrategyValidationError(f"Invalid decision record at index {index}")
        decision_id = record.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ExecutionStrategyValidationError(f"Invalid decision_id at index {index}")
        if decision_id in seen:
            raise ExecutionStrategyValidationError(f"Duplicate decision_id: {decision_id}")
        seen.add(decision_id)
        _validate_decision_category(
            record.get("decision_category"), path=f"provenance.decision_trace[{index}].decision_category"
        )


def _validate_generation_target_uniqueness(targets: list[dict]) -> None:
    seen: set[str] = set()
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ExecutionStrategyValidationError(f"Invalid generation target at index {index}")
        module = target.get("analysis_module")
        if module is None or module == "":
            raise ExecutionStrategyValidationError(f"Missing analysis_module at generation target index {index}")
        normalized = _normalize_analysis_module(
            module, path=f"generation_plan.modules_to_generate[{index}].analysis_module"
        ).value
        if normalized in seen:
            raise ExecutionStrategyValidationError(f"Duplicate generation target analysis_module: {normalized}")
        seen.add(normalized)
        _validate_generation_intent(
            target.get("generation_intent"),
            path=f"generation_plan.modules_to_generate[{index}].generation_intent",
        )
        _validate_generation_priority(
            target.get("priority"), path=f"generation_plan.modules_to_generate[{index}].priority"
        )


def _validate_authorized_modification_uniqueness(modifications: list[dict]) -> None:
    seen: set[tuple[str, str | None]] = set()
    for index, modification in enumerate(modifications):
        if not isinstance(modification, dict):
            raise ExecutionStrategyValidationError(f"Invalid authorized modification at index {index}")
        mod_class = _normalize_modification_class(
            modification.get("modification_class"),
            path=f"adaptation_plan.authorized_modifications[{index}].modification_class",
        ).value
        target_binding_id = modification.get("target_binding_id")
        target_key = (
            _normalize_optional_string(target_binding_id) or None
            if target_binding_id is not None
            else None
        )
        key = (mod_class, target_key)
        if key in seen:
            raise ExecutionStrategyValidationError(
                f"Duplicate authorized modification: {mod_class} / {target_key}"
            )
        seen.add(key)
        _validate_authorization_level(
            modification.get("authorization_level"),
            path=f"adaptation_plan.authorized_modifications[{index}].authorization_level",
        )


def _validate_cross_references(data: dict) -> None:
    binding_ids = {
        binding.get("binding_id")
        for binding in _binding_list(data)
        if isinstance(binding, dict) and isinstance(binding.get("binding_id"), str)
    }

    resource_bindings = data.get("resource_bindings", {})
    if isinstance(resource_bindings, dict):
        anchor_id = resource_bindings.get("anchor_binding_id")
        if anchor_id and anchor_id not in binding_ids:
            raise ExecutionStrategyValidationError(
                f"resource_bindings.anchor_binding_id references unknown binding: {anchor_id}"
            )

    reuse_plan = data.get("reuse_plan", {})
    if isinstance(reuse_plan, dict):
        primary_reuse = reuse_plan.get("primary_reuse_binding_id")
        if primary_reuse and primary_reuse not in binding_ids:
            raise ExecutionStrategyValidationError(
                f"reuse_plan.primary_reuse_binding_id references unknown binding: {primary_reuse}"
            )
        for index, component in enumerate(reuse_plan.get("components_to_reuse", [])):
            if not isinstance(component, dict):
                continue
            binding_id = component.get("binding_id")
            if binding_id and binding_id not in binding_ids:
                raise ExecutionStrategyValidationError(
                    f"reuse_plan.components_to_reuse[{index}] references unknown binding: {binding_id}"
                )

    adaptation_plan = data.get("adaptation_plan", {})
    if isinstance(adaptation_plan, dict):
        for index, modification in enumerate(adaptation_plan.get("authorized_modifications", [])):
            if not isinstance(modification, dict):
                continue
            target_binding_id = modification.get("target_binding_id")
            if target_binding_id and target_binding_id not in binding_ids:
                raise ExecutionStrategyValidationError(
                    f"adaptation_plan.authorized_modifications[{index}] references unknown binding: "
                    f"{target_binding_id}"
                )
        for index, trigger in enumerate(adaptation_plan.get("adaptation_triggers", [])):
            if isinstance(trigger, dict):
                _validate_adaptation_trigger_type(
                    trigger.get("trigger_type"),
                    path=f"adaptation_plan.adaptation_triggers[{index}].trigger_type",
                )

    risk_assessment = data.get("risk_assessment", {})
    if isinstance(risk_assessment, dict):
        for bucket in ("blocking_risks", "degraded_risks", "informational_risks"):
            for index, record in enumerate(risk_assessment.get(bucket, [])):
                if not isinstance(record, dict):
                    continue
                related_binding_id = record.get("related_binding_id")
                if related_binding_id and related_binding_id not in binding_ids:
                    raise ExecutionStrategyValidationError(
                        f"risk_assessment.{bucket}[{index}] references unknown binding: {related_binding_id}"
                    )
        for index, fallback in enumerate(risk_assessment.get("fallback_strategies", [])):
            if not isinstance(fallback, dict):
                continue
            for binding_id in fallback.get("fallback_binding_ids", []):
                if binding_id and binding_id not in binding_ids:
                    raise ExecutionStrategyValidationError(
                        f"risk_assessment.fallback_strategies[{index}] references unknown binding: {binding_id}"
                    )


def _validate_metadata_counts(metadata: dict, bindings: list[dict], risk_records: list[dict]) -> None:
    binding_count = metadata.get("binding_count")
    if isinstance(binding_count, int) and binding_count != len(bindings):
        raise ExecutionStrategyValidationError("metadata.binding_count does not match bindings list length")
    blocking_risk_count = metadata.get("blocking_risk_count")
    if isinstance(blocking_risk_count, int):
        blocking = sum(
            1
            for record in risk_records
            if isinstance(record, dict) and record.get("severity") in {"blocking", RiskSeverity.BLOCKING.value}
        )
        if blocking_risk_count != blocking:
            raise ExecutionStrategyValidationError(
                "metadata.blocking_risk_count does not match blocking risk records"
            )


def _validate_conditional_fields(strategy: dict, bindings: list[dict]) -> None:
    scope_commitment = strategy.get("scope_commitment")
    if scope_commitment in {ScopeCommitment.NARROWED_SCOPE.value, "narrowed_scope"}:
        rationale = strategy.get("scope_narrowing_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ExecutionStrategyValidationError(
                "strategy.scope_narrowing_rationale required when scope_commitment is narrowed_scope"
            )

    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            continue
        if binding.get("overrides_discovery_selection") and not _normalize_optional_string(
            binding.get("override_rationale")
        ):
            raise ExecutionStrategyValidationError(
                f"resource_bindings.bindings[{index}].override_rationale required when override is true"
            )


def _validate_schema_version(value: object) -> None:
    _normalize_schema_version(value)


def _normalize_schema_version(value: object) -> str:
    if value is None or value == "":
        return SCHEMA_VERSION
    if not isinstance(value, str):
        raise ExecutionStrategyValidationError("Invalid field: schema_version must be a string")
    stripped = value.strip()
    if not stripped:
        raise ExecutionStrategyValidationError("Invalid field: schema_version must be non-empty")
    return stripped


def _normalize_enum(value: object, enum_cls, *, path: str, default=None):
    if value is None or value == "":
        if default is not None:
            return default
        raise ExecutionStrategyValidationError(f"Invalid field: {path}")
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str):
        raise ExecutionStrategyValidationError(f"Invalid field: {path}")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    for item in enum_cls:
        if item.value == normalized:
            return item
    raise ExecutionStrategyValidationError(f"Invalid value for {path}: {value!r}")


def _normalize_planning_status(value: object, *, path: str) -> PlanningStatus:
    return _normalize_enum(value, PlanningStatus, path=path, default=PlanningStatus.PARTIAL)


def _validate_planning_status(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_planning_status(value, path=path)


def _normalize_planning_invocation_reason(value: object, *, path: str) -> PlanningInvocationReason:
    return _normalize_enum(
        value, PlanningInvocationReason, path=path, default=PlanningInvocationReason.DISCOVERY_COMPLETE
    )


def _normalize_strategy_posture(value: object, *, path: str, default: StrategyPosture | None = None) -> StrategyPosture:
    return _normalize_enum(value, StrategyPosture, path=path, default=default)


def _validate_strategy_posture(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_strategy_posture(value, path=path)


def _normalize_scope_commitment(value: object, *, path: str) -> ScopeCommitment:
    return _normalize_enum(value, ScopeCommitment, path=path, default=ScopeCommitment.FULL_REPRODUCTION)


def _validate_scope_commitment(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_scope_commitment(value, path=path)


def _normalize_binding_role(value: object, *, path: str) -> BindingRole:
    return _normalize_enum(value, BindingRole, path=path)


def _validate_binding_role(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_binding_role(value, path=path)


def _normalize_usage_intent(value: object, *, path: str) -> UsageIntent:
    return _normalize_enum(value, UsageIntent, path=path, default=UsageIntent.EXECUTE_DIRECTLY)


def _validate_usage_intent(value: object, *, path: str) -> None:
    if value is None or value == "":
        return
    _normalize_usage_intent(value, path=path)


def _normalize_reuse_mode(value: object, *, path: str) -> ReuseMode:
    return _normalize_enum(value, ReuseMode, path=path, default=ReuseMode.NOT_APPLICABLE)


def _normalize_reuse_extent(value: object, *, path: str) -> ReuseExtent:
    return _normalize_enum(value, ReuseExtent, path=path, default=ReuseExtent.FULL)


def _normalize_adaptation_scope(value: object, *, path: str) -> AdaptationScope:
    return _normalize_enum(value, AdaptationScope, path=path, default=AdaptationScope.NONE)


def _normalize_modification_class(value: object, *, path: str) -> ModificationClass:
    return _normalize_enum(value, ModificationClass, path=path)


def _normalize_authorization_level(value: object, *, path: str) -> AuthorizationLevel:
    return _normalize_enum(value, AuthorizationLevel, path=path, default=AuthorizationLevel.PLANNER_TASK)


def _validate_authorization_level(value: object, *, path: str) -> None:
    if value is None or value == "":
        return
    _normalize_authorization_level(value, path=path)


def _normalize_adaptation_trigger_type(value: object, *, path: str) -> AdaptationTriggerType:
    return _normalize_enum(value, AdaptationTriggerType, path=path)


def _validate_adaptation_trigger_type(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_adaptation_trigger_type(value, path=path)


def _normalize_generation_scope(value: object, *, path: str) -> GenerationScope:
    return _normalize_enum(value, GenerationScope, path=path, default=GenerationScope.NONE)


def _normalize_analysis_module(value: object, *, path: str) -> AnalysisModule:
    return _normalize_enum(value, AnalysisModule, path=path)


def _normalize_generation_intent(value: object, *, path: str) -> GenerationIntent:
    return _normalize_enum(value, GenerationIntent, path=path)


def _validate_generation_intent(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_generation_intent(value, path=path)


def _normalize_generation_priority(value: object, *, path: str) -> GenerationPriority:
    return _normalize_enum(value, GenerationPriority, path=path, default=GenerationPriority.BLOCKING)


def _validate_generation_priority(value: object, *, path: str) -> None:
    if value is None or value == "":
        return
    _normalize_generation_priority(value, path=path)


def _normalize_risk_severity(value: object, *, path: str) -> RiskSeverity:
    return _normalize_enum(value, RiskSeverity, path=path)


def _validate_risk_severity(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_risk_severity(value, path=path)


def _normalize_risk_category(value: object, *, path: str) -> RiskCategory:
    return _normalize_enum(value, RiskCategory, path=path)


def _validate_risk_category(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_risk_category(value, path=path)


def _normalize_decision_category(value: object, *, path: str) -> DecisionCategory:
    return _normalize_enum(value, DecisionCategory, path=path)


def _validate_decision_category(value: object, *, path: str) -> None:
    if value is None or value == "":
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")
    _normalize_decision_category(value, path=path)


def _normalize_discovery_status(value: object, *, path: str) -> DiscoveryStatus:
    return _normalize_enum(value, DiscoveryStatus, path=path, default=DiscoveryStatus.SKIPPED)


def _require_dict(data: dict, field: str) -> None:
    if field not in data or not isinstance(data[field], dict):
        raise ExecutionStrategyValidationError(f"Missing required field: {field}")


def _require_dict_instance(data: dict, path: str) -> None:
    if not isinstance(data, dict):
        raise ExecutionStrategyValidationError(f"Missing required field: {path}")


def _require_non_empty_string(data: dict, field: str, *, path: str) -> str:
    if field not in data:
        raise ExecutionStrategyValidationError(f"Missing required field: {path}.{field}")
    value = data[field]
    if not isinstance(value, str):
        raise ExecutionStrategyValidationError(f"Invalid required field: {path}.{field}")
    stripped = value.strip()
    if not stripped:
        raise ExecutionStrategyValidationError(f"Invalid required field: {path}.{field}")
    return stripped


def _normalize_optional_string(value: object, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        return str(value).strip()
    return value.strip()


def _normalize_int(value: object, *, default: int) -> int:
    if value is None or value == "":
        return default
    if not isinstance(value, int):
        raise ExecutionStrategyValidationError("Expected an integer")
    return value


def _normalize_float(value: object, *, default: float) -> float:
    if value is None or value == "":
        return default
    if not isinstance(value, (int, float)):
        raise ExecutionStrategyValidationError("Expected a float")
    return float(value)


def _normalize_datetime(value: object, *, path: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ExecutionStrategyValidationError(f"Invalid datetime field: {path}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ExecutionStrategyValidationError(f"Invalid datetime field: {path}") from exc


def _normalize_optional_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return _normalize_datetime(value, path="datetime")
