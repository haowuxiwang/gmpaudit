"""Tests for agent/tools/json_parser.py"""

from agent.tools.json_parser import parse_llm_json


class TestParseLlmJson:
    """Test parse_llm_json function."""

    def test_clean_json_array(self):
        """Valid JSON array parses correctly."""
        input_str = '[{"a": 1, "b": "hello"}]'
        result = parse_llm_json(input_str)
        assert result == [{"a": 1, "b": "hello"}]

    def test_clean_json_multiple_items(self):
        """Array with multiple objects."""
        input_str = '[{"id": 1}, {"id": 2}, {"id": 3}]'
        result = parse_llm_json(input_str)
        assert len(result) == 3
        assert result[0]["id"] == 1

    def test_fenced_json(self):
        """JSON wrapped in markdown code fences."""
        input_str = '```json\n[{"a": 1}]\n```'
        result = parse_llm_json(input_str)
        assert result == [{"a": 1}]

    def test_fenced_json_with_language_tag(self):
        """JSON with ```json tag."""
        input_str = '```json\n{"key": "value"}\n```'
        result = parse_llm_json(input_str)
        assert result == [{"key": "value"}]

    def test_single_object(self):
        """Single JSON object gets wrapped in list."""
        input_str = '{"name": "test", "value": 42}'
        result = parse_llm_json(input_str)
        assert result == [{"name": "test", "value": 42}]

    def test_nested_content_array(self):
        """JSON array embedded in surrounding text."""
        input_str = 'Here is the result:\n[{"finding": "test"}]\nEnd of output.'
        result = parse_llm_json(input_str)
        assert result == [{"finding": "test"}]

    def test_nested_content_object(self):
        """JSON object embedded in surrounding text."""
        input_str = 'Analysis complete:\n{"status": "ok"}\nDone.'
        result = parse_llm_json(input_str)
        assert result == [{"status": "ok"}]

    def test_invalid_input(self):
        """Non-JSON input returns empty list."""
        result = parse_llm_json("not json at all")
        assert result == []

    def test_empty_string(self):
        """Empty string returns empty list."""
        result = parse_llm_json("")
        assert result == []

    def test_whitespace_only(self):
        """Whitespace-only string returns empty list."""
        result = parse_llm_json("   \n\t  ")
        assert result == []

    def test_nested_json_structure(self):
        """Complex nested JSON parses correctly."""
        input_str = '[{"items": [{"id": 1}, {"id": 2}], "meta": {"total": 2}}]'
        result = parse_llm_json(input_str)
        assert len(result) == 1
        assert len(result[0]["items"]) == 2

    def test_json_with_special_characters(self):
        """JSON with unicode and special chars."""
        input_str = '[{"title": "偏差处理", "desc": "test\\"quote"}]'
        result = parse_llm_json(input_str)
        assert result[0]["title"] == "偏差处理"

    def test_trailing_commas_fixed_by_fix_common(self):
        """Trailing commas fixed by _fix_common_json_errors when regex extraction fails."""
        # Input with trailing commas that prevents direct parse and regex match
        input_str = 'Result: {"a": 1, "b": 2,} end'
        result = parse_llm_json(input_str)
        assert len(result) == 1
        assert result[0]["a"] == 1

    def test_whole_content_fixed_by_fix_common_comments(self):
        """Content with comments becomes valid JSON after _fix_common_json_errors."""
        # Multi-line comment prevents direct parse and regex extraction;
        # after _fix_common_json_errors removes comment, whole content is valid JSON
        input_str = '{/* GMP note */ "key": "value", "num": 42}'
        result = parse_llm_json(input_str)
        assert len(result) == 1
        assert result[0]["key"] == "value"

    def test_single_quotes_fixed(self):
        """Single quotes replaced by _fix_common_json_errors and extracted via regex."""
        # Single quotes prevent direct parse; regex on fixed content should match
        input_str = "analysis {'title': 'test', 'severity': 'high'} done"
        result = parse_llm_json(input_str)
        assert len(result) == 1
        assert result[0]["title"] == "test"
