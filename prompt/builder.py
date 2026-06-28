from prompt.loader import PromptLoader


class PromptBuilder:
    def __init__(self, loader: PromptLoader) -> None:
        self._loader = loader

    def build_reader_prompt(self) -> str:
        sections = ("system", "extraction", "schema", "examples")
        parts = [self._loader.load("reader", section) for section in sections]
        return "\n\n".join(parts)
