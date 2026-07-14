"""Merge policy for Execution Planning resource binding stage results."""

from __future__ import annotations

from models.execution_planning_runtime import ResourceBindingResult


def merge_resource_binding_results(
    existing: ResourceBindingResult,
    incoming: ResourceBindingResult,
) -> ResourceBindingResult:
    if _is_empty_binding(existing) and not _is_empty_binding(incoming):
        return incoming
    if not _is_empty_binding(existing):
        if not incoming.resource_bindings.bindings:
            return existing
        merged_bindings = list(existing.resource_bindings.bindings)
        seen = {binding.binding_id for binding in merged_bindings}
        for binding in incoming.resource_bindings.bindings:
            if binding.binding_id not in seen:
                merged_bindings.append(binding)
                seen.add(binding.binding_id)
        return existing.model_copy(
            update={
                "resource_bindings": existing.resource_bindings.model_copy(
                    update={"bindings": merged_bindings}
                )
            }
        )
    return incoming


def _is_empty_binding(result: ResourceBindingResult) -> bool:
    return not result.resource_bindings.bindings and not result.decision_notes
