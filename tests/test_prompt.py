import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prompt.builder import PromptBuilder
from prompt.exceptions import PromptNotFoundError
from prompt.loader import PromptLoader


class PromptLoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.temp_dir.name)
        agent_dir = self.prompts_dir / "reader"
        agent_dir.mkdir(parents=True)
        (agent_dir / "system.md").write_text("System prompt.", encoding="utf-8")
        self.loader = PromptLoader(prompts_dir=self.prompts_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_load_existing_file(self) -> None:
        content = self.loader.load("reader", "system")
        self.assertEqual(content, "System prompt.")

    def test_load_missing_prompt_raises(self) -> None:
        with self.assertRaises(PromptNotFoundError):
            self.loader.load("reader", "missing")


class PromptBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.temp_dir.name)
        reader_dir = self.prompts_dir / "reader"
        reader_dir.mkdir(parents=True)
        (reader_dir / "system.md").write_text("SYSTEM", encoding="utf-8")
        (reader_dir / "extraction.md").write_text("EXTRACTION", encoding="utf-8")
        (reader_dir / "schema.md").write_text("SCHEMA", encoding="utf-8")
        (reader_dir / "examples.md").write_text("EXAMPLES", encoding="utf-8")
        (reader_dir / "output.md").write_text("OUTPUT", encoding="utf-8")
        self.builder = PromptBuilder(PromptLoader(prompts_dir=self.prompts_dir))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_reader_prompt_combines_sections_in_order(self) -> None:
        prompt = self.builder.build_reader_prompt()
        system_index = prompt.index("SYSTEM")
        extraction_index = prompt.index("EXTRACTION")
        schema_index = prompt.index("SCHEMA")
        examples_index = prompt.index("EXAMPLES")
        output_index = prompt.index("OUTPUT")
        self.assertLess(system_index, extraction_index)
        self.assertLess(extraction_index, schema_index)
        self.assertLess(schema_index, examples_index)
        self.assertLess(examples_index, output_index)

    def test_build_planner_prompt_combines_sections_in_order(self) -> None:
        planner_dir = self.prompts_dir / "planner"
        planner_dir.mkdir(parents=True, exist_ok=True)
        (planner_dir / "system.md").write_text("PSYSTEM", encoding="utf-8")
        (planner_dir / "extraction.md").write_text("PEXTRACTION", encoding="utf-8")
        (planner_dir / "schema.md").write_text("PSCHEMA", encoding="utf-8")
        (planner_dir / "examples.md").write_text("PEXAMPLES", encoding="utf-8")
        prompt = self.builder.build_planner_prompt()
        self.assertLess(prompt.index("PSYSTEM"), prompt.index("PEXTRACTION"))
        self.assertLess(prompt.index("PEXTRACTION"), prompt.index("PSCHEMA"))
        self.assertLess(prompt.index("PSCHEMA"), prompt.index("PEXAMPLES"))

    def test_build_coder_prompt_uses_category_template(self) -> None:
        coder_dir = self.prompts_dir / "coder"
        coder_dir.mkdir(parents=True, exist_ok=True)
        (coder_dir / "system.md").write_text("CSYSTEM", encoding="utf-8")
        (coder_dir / "source.md").write_text("CSOURCE", encoding="utf-8")
        prompt = self.builder.build_coder_prompt("source")
        self.assertLess(prompt.index("CSYSTEM"), prompt.index("CSOURCE"))


if __name__ == "__main__":
    unittest.main()
