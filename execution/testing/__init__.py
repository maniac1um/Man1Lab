"""Test helpers for execution engine wiring."""

from __future__ import annotations

from execution.artifacts.in_memory import InMemoryArtifactTracker
from execution.backends.fake_executor import FakeExecutor, FakeExecutorRule
from execution.engine import ExecutionEngine
from execution.input_resolver.in_memory import InMemoryInputResolver
from execution.persistence.in_memory import InMemoryExecutionStore
from execution.reconciliation.in_memory import InMemoryReconciliationPort


def make_test_engine(
    *,
    executor: FakeExecutor | None = None,
    artifact_tracker: InMemoryArtifactTracker | None = None,
    input_resolver: InMemoryInputResolver | None = None,
    reconciliation: InMemoryReconciliationPort | None = None,
    default_rule: FakeExecutorRule | None = None,
    persistence: InMemoryExecutionStore | None = None,
) -> ExecutionEngine:
    tracker = artifact_tracker or InMemoryArtifactTracker()
    return ExecutionEngine(
        executor=executor or FakeExecutor(default_rule=default_rule),
        artifact_tracker=tracker,
        input_resolver=input_resolver or InMemoryInputResolver(tracker),
        reconciliation=reconciliation or InMemoryReconciliationPort(),
        persistence=persistence,
    )
