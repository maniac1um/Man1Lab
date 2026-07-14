import json
import re

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


class ResponseParseError(ValueError):
    """Raised when an LLM response cannot be parsed as a JSON object."""


class ResponseParser:
    def parse(self, raw_response: str) -> dict:
        text = self._extract_json_text(raw_response)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResponseParseError(
                f"Failed to parse LLM response as JSON: {exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise ResponseParseError(
                f"Expected JSON object, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def _extract_json_text(raw_response: str) -> str:
        text = raw_response.strip()
        fence_match = _FENCE_PATTERN.search(text)
        if fence_match:
            return fence_match.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return text[start : end + 1]

        return text
