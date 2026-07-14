"""Settings provider protocol and registry."""

from __future__ import annotations

from typing import Protocol

from configuration.models import AppSettings


class SettingsProvider(Protocol):
    def get_settings(self) -> AppSettings: ...


_provider: SettingsProvider | None = None


def get_settings_provider() -> SettingsProvider:
    if _provider is None:
        from configuration.legacy_provider import LegacySettingsProvider

        return LegacySettingsProvider()
    return _provider


def set_settings_provider(provider: SettingsProvider) -> None:
    global _provider
    _provider = provider
