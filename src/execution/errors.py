"""Domain errors for the execution engine capability."""


class ExecutionEngineError(Exception):
    """Base error for execution engine violations."""


class GraphValidationError(ExecutionEngineError):
    """Raised when an execution graph fails structural validation."""


class TaskDagValidationError(ExecutionEngineError):
    """Raised when a decomposed task DAG fails validation."""


class UnsupportedStageError(GraphValidationError):
    """Raised when a graph node cannot be mapped to a supported task type."""


class InvalidTransitionError(ExecutionEngineError):
    """Raised when a scheduler requests an illegal task status transition."""


class ResumeRejectedError(ExecutionEngineError):
    """Raised when resume preconditions are not satisfied."""


class ArtifactValidationError(ExecutionEngineError):
    """Raised when required artifacts fail validation."""


class PersistenceError(ExecutionEngineError):
    """Base error for execution persistence violations."""


class RunNotFoundError(PersistenceError):
    """Raised when a run snapshot cannot be loaded."""


class RunExistsError(PersistenceError):
    """Raised when creating a run that already exists."""


class IncompatibleSchemaError(PersistenceError):
    """Raised when persisted schema version is unsupported."""


class CorruptSnapshotError(PersistenceError):
    """Raised when a snapshot file is corrupt or unreadable."""


class InconsistentTraceError(PersistenceError):
    """Raised when trace and snapshot state disagree."""


class InvalidTransitionCommitError(PersistenceError):
    """Raised when a transition commit violates persistence invariants."""


class WriterConflictError(PersistenceError):
    """Raised when another writer holds the run lock."""


class PersistenceIOError(PersistenceError):
    """Raised when underlying storage I/O fails."""


class UnresolvedReconciliationError(PersistenceError):
    """Raised when persisted state requires reconciliation that cannot proceed."""


class MixedRevisionSnapshotError(PersistenceError):
    """Raised when snapshot files disagree on run_id or revision."""


class MalformedLockError(PersistenceError):
    """Raised when a writer lock file cannot be parsed and must not be overwritten."""


class UnsafeArtifactLocationError(ArtifactValidationError):
    """Raised when an artifact location violates workspace safety rules."""


class ArtifactIntegrityError(ArtifactValidationError):
    """Raised when artifact integrity verification fails."""


class ArtifactProducerMismatchError(ArtifactValidationError):
    """Raised when artifact producer identity does not match the expected scope."""
