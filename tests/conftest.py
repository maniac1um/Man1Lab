"""Shared pytest hooks for the Man1Lab test suite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from models.research_resource_discovery import ProviderInvocationStatus, ProviderRecord
from ports.collection_provider import CollectionProviderResult
from ports.evidence_provider import EvidenceProviderResult

_EXECUTION_ENGINE_ONLY_TESTS = {
    "test_execution_engine_models.py",
    "test_execution_graph_validation.py",
    "test_execution_decomposition.py",
    "test_execution_scheduler.py",
    "test_execution_resume.py",
    "test_execution_ports.py",
    "test_execution_audit_remediation.py",
    "test_execution_second_audit_remediation.py",
    "test_execution_store.py",
    "test_execution_runtime_integration.py",
    "test_execution_local_runtime_integration.py",
    "test_local_executor.py",
}


@pytest.fixture(autouse=True)
def disable_live_github_collection_in_default_providers(request, monkeypatch):
    """Keep existing discovery tests offline while GitHub is registered by default."""
    if request.node.fspath.basename in {
        "test_github_collection_provider.py",
        "test_github_evidence_provider.py",
        "test_github_verification_provider.py",
        "test_github_ranking_provider.py",
        *_EXECUTION_ENGINE_ONLY_TESTS,
    }:
        return

    def _providers_without_live_github():
        from providers.embedded.embedded_resource_provider import EmbeddedResourceProvider
        from providers.noop.collection import NoOpCollectionProvider

        class _SkippedGitHubProvider:
            def collect(self, analysis):
                del analysis
                return CollectionProviderResult(
                    provider_outcomes=[
                        ProviderRecord(
                            provider_name="github",
                            provider_version="1.0.0",
                            invoked_at=datetime.now(UTC),
                            status=ProviderInvocationStatus.SKIPPED,
                        )
                    ]
                )

        return [
            EmbeddedResourceProvider(),
            _SkippedGitHubProvider(),
            NoOpCollectionProvider(),
        ]

    monkeypatch.setattr(
        "services.discovery.collection_service._default_providers",
        _providers_without_live_github,
    )


@pytest.fixture(autouse=True)
def disable_live_github_evidence_in_default_providers(request, monkeypatch):
    """Keep existing discovery tests offline while GitHub evidence is registered by default."""
    if request.node.fspath.basename in {
        "test_github_evidence_provider.py",
        "test_github_verification_provider.py",
        "test_github_ranking_provider.py",
        *_EXECUTION_ENGINE_ONLY_TESTS,
    }:
        return

    def _providers_without_live_github_evidence():
        from providers.embedded.embedded_evidence_provider import EmbeddedEvidenceProvider
        from providers.noop.noop_evidence_provider import NoOpEvidenceProvider

        class _SkippedGitHubEvidenceProvider:
            def collect(self, analysis, collection_result, candidates):
                del analysis, collection_result, candidates
                return EvidenceProviderResult(
                    provider_outcomes=[
                        ProviderRecord(
                            provider_name="github_evidence",
                            provider_version="1.0.0",
                            invoked_at=datetime.now(UTC),
                            status=ProviderInvocationStatus.SKIPPED,
                        )
                    ]
                )

        return [
            EmbeddedEvidenceProvider(),
            _SkippedGitHubEvidenceProvider(),
            NoOpEvidenceProvider(),
        ]

    monkeypatch.setattr(
        "services.discovery.evidence_service._default_providers",
        _providers_without_live_github_evidence,
    )


@pytest.fixture(autouse=True)
def disable_live_github_verification_in_default_providers(request, monkeypatch):
    """Keep existing discovery tests offline while GitHub verification is registered by default."""
    if request.node.fspath.basename in {
        "test_github_verification_provider.py",
        "test_github_ranking_provider.py",
        *_EXECUTION_ENGINE_ONLY_TESTS,
    }:
        return

    def _providers_without_live_github_verification():
        from providers.embedded.embedded_verification_provider import EmbeddedVerificationProvider
        from providers.noop.noop_verification_provider import NoOpVerificationProvider
        from ports.verification_provider import VerificationProviderResult

        class _SkippedGitHubVerificationProvider:
            def verify(self, analysis, collection_result, evidence_result):
                del analysis, collection_result, evidence_result
                return VerificationProviderResult(
                    provider_outcomes=[
                        ProviderRecord(
                            provider_name="github_verification",
                            provider_version="1.0.0",
                            invoked_at=datetime.now(UTC),
                            status=ProviderInvocationStatus.SKIPPED,
                        )
                    ]
                )

        return [
            EmbeddedVerificationProvider(),
            _SkippedGitHubVerificationProvider(),
            NoOpVerificationProvider(),
        ]

    monkeypatch.setattr(
        "services.discovery.verification_service._default_providers",
        _providers_without_live_github_verification,
    )


@pytest.fixture(autouse=True)
def disable_live_github_ranking_in_default_providers(request, monkeypatch):
    """Keep existing discovery tests offline while GitHub ranking is registered by default."""
    if request.node.fspath.basename in {
        "test_github_ranking_provider.py",
        *_EXECUTION_ENGINE_ONLY_TESTS,
    }:
        return

    def _providers_without_live_github_ranking():
        from providers.embedded.embedded_ranking_provider import EmbeddedRankingProvider
        from providers.noop.noop_ranking_provider import NoOpRankingProvider
        from ports.ranking_provider import RankingProviderResult

        class _SkippedGitHubRankingProvider:
            def rank(self, analysis, collection_result, evidence_result, verification_result):
                del analysis, collection_result, evidence_result, verification_result
                return RankingProviderResult(
                    provider_outcomes=[
                        ProviderRecord(
                            provider_name="github_ranking",
                            provider_version="1.0.0",
                            invoked_at=datetime.now(UTC),
                            status=ProviderInvocationStatus.SKIPPED,
                        )
                    ]
                )

        return [
            EmbeddedRankingProvider(),
            _SkippedGitHubRankingProvider(),
            NoOpRankingProvider(),
        ]

    monkeypatch.setattr(
        "services.discovery.ranking_service._default_providers",
        _providers_without_live_github_ranking,
    )
