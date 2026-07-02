import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from adapters.config_parser_settings import ConfigParserSettingsProvider
from adapters.factory import build_document_parser
from configuration.bootstrap import initialize_app_configuration
from configuration.legacy_provider import LegacySettingsProvider
from configuration.models import AppSettings
from configuration.provider import get_settings_provider, set_settings_provider


class LegacySettingsProviderTest(unittest.TestCase):
    def test_defaults_match_legacy_config_facade(self) -> None:
        settings = LegacySettingsProvider().get_settings()
        self.assertEqual(settings.workspace_root, config.WORKSPACE_ROOT)
        self.assertEqual(settings.parser.backend, config.PARSER_BACKEND)
        self.assertEqual(settings.workflow.max_review_iterations, config.MAX_REVIEW_ITERATIONS)


class HydraBootstrapTest(unittest.TestCase):
    def test_initialize_app_configuration_loads_conf(self) -> None:
        with patch.dict(os.environ, {"PARSER_BACKEND": "pymupdf"}, clear=False):
            settings = initialize_app_configuration()
        self.assertIsInstance(settings, AppSettings)
        self.assertEqual(config.PARSER_BACKEND, "pymupdf")
        self.assertEqual(settings.parser.backend, "pymupdf")
        self.assertEqual(settings.workspace_root, Path("workspace/tasks"))
        self.assertTrue(settings.tracking.enabled)
        self.assertEqual(settings.tracking.backend, "mlflow")

    def test_parser_settings_provider_uses_settings_provider(self) -> None:
        initialize_app_configuration()
        parser = build_document_parser(
            settings_provider=ConfigParserSettingsProvider(get_settings_provider())
        )
        settings = get_settings_provider().get_settings()
        self.assertIsNotNone(parser)
        self.assertIn(settings.parser.backend, {"docling", "pymupdf"})


class ConfigFacadeTest(unittest.TestCase):
    def test_apply_settings_updates_module_constants(self) -> None:
        settings = LegacySettingsProvider().get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            custom = AppSettings(
                workspace_root=Path(temp_dir) / "workspace",
                outputs_dir=Path(temp_dir) / "outputs",
                logs_dir=Path(temp_dir) / "logs",
                prompts_dir=Path("prompts"),
                paper_path=Path("custom.pdf"),
                parser=settings.parser,
                discovery=settings.discovery,
                execution_planning=settings.execution_planning,
                workflow=settings.workflow,
                llm=settings.llm,
                logging=settings.logging,
                tracking=settings.tracking,
            )
            config.apply_settings(custom)
            self.assertEqual(config.WORKSPACE_ROOT, custom.workspace_root)
            self.assertEqual(config.PAPER_PATH, Path("custom.pdf"))


if __name__ == "__main__":
    unittest.main()
