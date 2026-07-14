from prompt.loader import PromptLoader


class PromptBuilder:
    def __init__(self, loader: PromptLoader) -> None:
        self._loader = loader

    def build_reader_prompt(self) -> str:
        sections = ("system", "extraction", "schema", "examples", "output")
        parts = [self._loader.load("reader", section) for section in sections]
        return "\n\n".join(parts)

    def build_planner_prompt(self) -> str:
        sections = ("system", "extraction", "schema", "examples")
        parts = [self._loader.load("planner", section) for section in sections]
        return "\n\n".join(parts)

    def build_coder_prompt(self, file_category: str) -> str:
        parts = [
            self._loader.load("coder", "system"),
            self._loader.load("coder", file_category),
        ]
        return "\n\n".join(parts)

    def build_reviewer_prompt(self) -> str:
        sections = ("system", "extraction", "schema", "examples")
        parts = [self._loader.load("reviewer", section) for section in sections]
        return "\n\n".join(parts)

    def build_patch_planner_prompt(self) -> str:
        sections = ("system", "extraction", "schema", "examples")
        parts = [self._loader.load("patch_planner", section) for section in sections]
        return "\n\n".join(parts)
