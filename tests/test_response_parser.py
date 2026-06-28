import unittest

from llm.response_parser import ResponseParseError, ResponseParser


class ResponseParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ResponseParser()

    def test_parse_valid_json(self) -> None:
        data = self.parser.parse('{"title": "Test Paper", "abstract": "An abstract."}')
        self.assertEqual(data["title"], "Test Paper")
        self.assertEqual(data["abstract"], "An abstract.")

    def test_parse_json_inside_markdown_fence(self) -> None:
        raw = 'Here is the result:\n```json\n{"title": "Fenced"}\n```\nDone.'
        data = self.parser.parse(raw)
        self.assertEqual(data["title"], "Fenced")

    def test_parse_malformed_json_raises(self) -> None:
        with self.assertRaises(ResponseParseError):
            self.parser.parse('{"title": "broken"')

    def test_parse_non_object_json_raises(self) -> None:
        with self.assertRaises(ResponseParseError):
            self.parser.parse('["not", "an", "object"]')


if __name__ == "__main__":
    unittest.main()
