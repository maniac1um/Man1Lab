"""In-memory artifact tracker for tests and pure engine runs."""



from __future__ import annotations



from datetime import UTC, datetime

from uuid import uuid4



from execution.errors import (
    ArtifactIntegrityError,
    ArtifactProducerMismatchError,
    ArtifactValidationError,
    UnsafeArtifactLocationError,
)

from execution.ports.executor import ArtifactCandidate

from models.execution_engine import (
    Artifact,

    ArtifactScope,

    ArtifactValidationState,

    OutputDeclaration,
    ExecutionTask,
    TaskExecutionResult,
)


_SUPPORTED_VALIDATION_RULES = frozenset({"presence", "digest"})


def _location_ref_safe(location_ref: str) -> bool:
    if not location_ref:
        return True
    normalized = location_ref.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized[:3]:
        return False
    parts = normalized.split("/")
    return ".." not in parts


def _verify_integrity(artifact: Artifact, declaration: OutputDeclaration) -> None:
    if declaration.validation_rule == "digest" and declaration.integrity_hint:
        if artifact.integrity_digest != declaration.integrity_hint:
            raise ArtifactIntegrityError(
                f"{declaration.logical_name}: digest mismatch "
                f"(expected {declaration.integrity_hint}, got {artifact.integrity_digest})"
            )
    if artifact.integrity_digest and declaration.integrity_hint:
        if artifact.integrity_digest != declaration.integrity_hint:
            raise ArtifactIntegrityError(
                f"{declaration.logical_name}: digest mismatch"
            )





class InMemoryArtifactTracker:

    """Registers artifact metadata without filesystem persistence."""



    def __init__(self, *, workspace_root: str = "") -> None:

        self._artifacts: dict[str, Artifact] = {}
        self._workspace_root = workspace_root.replace("\\", "/").rstrip("/")



    def register_candidate(

        self,

        *,

        run_id: str,

        task_id: str,

        attempt_id: str,

        candidate: ArtifactCandidate,

        scope: ArtifactScope = ArtifactScope.RUNTIME_RUN,

    ) -> Artifact:

        artifact_id = f"art-{uuid4()}"

        if candidate.location_ref and not _location_ref_safe(candidate.location_ref):
            raise UnsafeArtifactLocationError(
                f"unsafe location_ref for {candidate.logical_name}: {candidate.location_ref}"
            )

        artifact = Artifact(

            artifact_id=artifact_id,

            logical_name=candidate.logical_name,

            artifact_type=candidate.artifact_type,

            producer_run_id=run_id,

            producer_task_id=task_id,

            producer_attempt_id=attempt_id,

            scope=scope,

            location_ref=candidate.location_ref,

            size_bytes=candidate.size_bytes,

            integrity_digest=candidate.integrity_digest,

            created_at=datetime.now(UTC),

            validation_state=ArtifactValidationState.PENDING,

        )

        self._artifacts[artifact_id] = artifact

        return artifact



    def validate_required_outputs(

        self,

        *,

        run_id: str,

        task_id: str,

        attempt_id: str,

        declarations: tuple[OutputDeclaration, ...],

    ) -> tuple[Artifact, ...]:

        attempt_artifacts = tuple(
            artifact
            for artifact in self._artifacts.values()
            if artifact.producer_run_id == run_id
            and artifact.producer_attempt_id == attempt_id
        )

        by_name = {artifact.logical_name: artifact for artifact in attempt_artifacts}

        validated: list[Artifact] = []

        missing: list[str] = []

        invalid: list[str] = []



        for declaration in declarations:

            if declaration.validation_rule not in _SUPPORTED_VALIDATION_RULES:

                raise ArtifactValidationError(

                    f"unsupported validation rule {declaration.validation_rule!r} for "

                    f"{declaration.logical_name}"

                )

            artifact = by_name.get(declaration.logical_name)

            if artifact is None:

                if declaration.required:

                    missing.append(declaration.logical_name)

                continue

            if artifact.artifact_type != declaration.artifact_type:

                invalid.append(

                    f"{declaration.logical_name}: expected type {declaration.artifact_type}, "

                    f"got {artifact.artifact_type}"

                )

                continue

            if artifact.scope != declaration.scope:

                invalid.append(

                    f"{declaration.logical_name}: expected scope {declaration.scope.value}, "

                    f"got {artifact.scope.value}"

                )

                continue

            if artifact.producer_run_id != run_id or artifact.producer_task_id != task_id:
                raise ArtifactProducerMismatchError(
                    f"{declaration.logical_name}: producer mismatch for task {task_id}"
                )

            if artifact.producer_attempt_id != attempt_id:
                raise ArtifactProducerMismatchError(
                    f"{declaration.logical_name}: producer attempt mismatch"
                )

            if artifact.location_ref and not _location_ref_safe(artifact.location_ref):
                raise UnsafeArtifactLocationError(
                    f"unsafe location_ref for {declaration.logical_name}"
                )

            if artifact.scope == ArtifactScope.EXTERNAL and not artifact.location_ref:
                invalid.append(f"{declaration.logical_name}: external artifact missing location_ref")
                continue

            try:
                _verify_integrity(artifact, declaration)
            except ArtifactIntegrityError:
                raise
            except ArtifactValidationError as exc:
                invalid.append(str(exc))
                continue

            if artifact.validation_state == ArtifactValidationState.INVALID:

                invalid.append(f"{declaration.logical_name}: invalidated")

                continue

            promoted = artifact.model_copy(update={"validation_state": ArtifactValidationState.VALID})

            self._artifacts[artifact.artifact_id] = promoted

            if declaration.required:

                validated.append(promoted)

            elif promoted.validation_state == ArtifactValidationState.VALID:

                validated.append(promoted)



        if missing:

            raise ArtifactValidationError(

                f"required outputs missing for task {task_id}: {', '.join(missing)}"

            )

        if invalid:

            raise ArtifactValidationError(

                f"required outputs invalid for task {task_id}: {', '.join(invalid)}"

            )

        return tuple(validated)



    def get_artifact(self, artifact_id: str) -> Artifact | None:

        return self._artifacts.get(artifact_id)



    def invalidate(self, artifact_id: str, *, reason: str = "") -> Artifact:

        existing = self._artifacts.get(artifact_id)

        if existing is None:

            raise ArtifactValidationError(f"unknown artifact: {artifact_id}")

        updated = existing.model_copy(

            update={

                "validation_state": ArtifactValidationState.INVALID,

                "metadata": {**existing.metadata, "invalidation_reason": reason},

            }

        )

        self._artifacts[artifact_id] = updated

        return updated



    def list_artifacts_for_task(

        self,

        task_id: str,

        *,

        run_id: str | None = None,

    ) -> tuple[Artifact, ...]:

        return tuple(

            artifact

            for artifact in self._artifacts.values()

            if artifact.producer_task_id == task_id

            and (run_id is None or artifact.producer_run_id == run_id)

        )



    def list_artifacts_for_attempt(

        self,

        *,

        run_id: str,

        task_id: str,

        attempt_id: str,

    ) -> tuple[Artifact, ...]:

        return tuple(

            artifact

            for artifact in self._artifacts.values()

            if artifact.producer_run_id == run_id

            and artifact.producer_task_id == task_id

            and artifact.producer_attempt_id == attempt_id

        )



    def artifact_still_valid(self, artifact_id: str) -> bool:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.validation_state != ArtifactValidationState.VALID:
            return False
        if artifact.location_ref and not _location_ref_safe(artifact.location_ref):
            return False
        return True

    def hydrate_artifacts(self, artifacts: tuple[Artifact, ...]) -> None:
        """Load persisted artifact manifests into the in-memory tracker."""
        for artifact in artifacts:
            self._artifacts[artifact.artifact_id] = artifact

    def all_artifacts(self) -> tuple[Artifact, ...]:
        return tuple(self._artifacts.values())

    def result_satisfies_required_outputs(
        self,
        *,
        run_id: str,
        task: ExecutionTask,
        result: TaskExecutionResult,
    ) -> bool:
        if result.run_id != run_id or result.task_id != task.id or not result.attempts:
            return False
        attempt_id = result.attempts[-1].attempt_id
        result_artifacts = {
            artifact_id: self._artifacts.get(artifact_id)
            for artifact_id in result.artifact_ids
        }
        for declaration in task.outputs:
            if not declaration.required:
                continue
            matches = [
                artifact
                for artifact in result_artifacts.values()
                if artifact is not None
                and artifact.producer_run_id == run_id
                and artifact.producer_task_id == task.id
                and artifact.producer_attempt_id == attempt_id
                and artifact.logical_name == declaration.logical_name
                and artifact.artifact_type == declaration.artifact_type
                and artifact.scope == declaration.scope
                and artifact.validation_state == ArtifactValidationState.VALID
                and (not artifact.location_ref or _location_ref_safe(artifact.location_ref))
            ]
            if not matches:
                return False
            try:
                _verify_integrity(matches[0], declaration)
            except ArtifactIntegrityError:
                return False
        return True

