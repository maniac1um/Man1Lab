"""Application configuration bootstrap."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from hydra import compose, initialize_config_dir

import config
from configuration.hydra_provider import HydraSettingsProvider
from configuration.models import AppSettings
from configuration.provider import set_settings_provider


def initialize_app_configuration() -> AppSettings:
    """Compose Hydra configuration and apply it to the legacy config facade."""
    load_dotenv()
    conf_dir = Path(__file__).resolve().parents[1] / "conf"
    with initialize_config_dir(config_dir=str(conf_dir), version_base=None):
        cfg = compose(config_name="config")
    provider = HydraSettingsProvider(cfg)
    settings = provider.get_settings()
    config.apply_settings(settings)
    set_settings_provider(provider)
    return settings
