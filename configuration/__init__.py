"""Man1Lab configuration package."""

from configuration.bootstrap import initialize_app_configuration
from configuration.legacy_provider import LegacySettingsProvider, get_settings
from configuration.models import AppSettings
from configuration.provider import SettingsProvider, get_settings_provider, set_settings_provider

__all__ = [
    "AppSettings",
    "LegacySettingsProvider",
    "SettingsProvider",
    "get_settings",
    "get_settings_provider",
    "initialize_app_configuration",
    "set_settings_provider",
]
