"""In-memory artifact tracker for tests and pure engine runs."""



from __future__ import annotations



from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

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

    def _workspace_relative_location(self, location_ref: str) -> str:
        if not location_ref or not self._workspace_root:
            return location_ref
        candidate = Path(location_ref)
        if not candidate.is_absolute():
            return location_ref.replace("\\", "/")
        root = Path(self._workspace_root).resolve()
        resolved = candidate.resolve()
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            return location_ref



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

        location_ref = self._workspace_relative_location(candidate.location_ref)
        if location_ref and not _location_ref_safe(location_ref):
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

            location_ref=location_ref,

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
        if not self._preparation_receipt_valid(artifact.location_ref):
            return False
        return True

    def _preparation_receipt_valid(self, location_ref: str) -> bool:
        if not location_ref or not self._workspace_root or not location_ref.endswith("_receipt.json"):
            return True
        receipt = (Path(self._workspace_root) / location_ref).resolve()
        root = Path(self._workspace_root).resolve()
        try:
            receipt.relative_to(root)
        except ValueError:
            return False
        if not receipt.is_file():
            return False
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            target = (root / str(payload["target_path"])).resolve()
            target.relative_to(root)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return False
        if not target.exists():
            return False
        expected = str(payload.get("checksum_sha256", ""))
        return not expected or _digest_path(target) == expected

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
                and self._preparation_receipt_valid(artifact.location_ref)
            ]
            if not matches:
                return False
            try:
                _verify_integrity(matches[0], declaration)
            except ArtifactIntegrityError:
                return False
        return True


def _digest_path(path: Path) -> str:
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(_digest_path(item).encode("ascii"))
    return digest.hexdigest()

