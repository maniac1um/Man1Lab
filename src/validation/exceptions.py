class PaperValidationError(ValueError):
    """Raised when extracted paper data fails validation."""


class AnalysisValidationError(ValueError):
    """Raised when extracted reproduction analysis data fails validation."""


class DiscoveryValidationError(ValueError):
    """Raised when discovery artifact data fails validation."""


class ExecutionStrategyValidationError(ValueError):
    """Raised when execution strategy artifact data fails validation."""


class TaskValidationError(ValueError):
    """Raised when extracted task data fails validation."""


class ReviewValidationError(ValueError):
    """Raised when extracted review data fails validation."""


class PatchValidationError(ValueError):
    """Raised when extracted patch plan data fails validation."""
