"""Tests for agent.state: merge_lists and AuditState."""

from agent.state import AuditState, merge_lists


class TestMergeLists:
    def test_both_empty(self):
        assert merge_lists([], []) == []

    def test_first_empty(self):
        assert merge_lists([], [1, 2]) == [1, 2]

    def test_second_empty(self):
        assert merge_lists([1, 2], []) == [1, 2]

    def test_basic_merge(self):
        assert merge_lists([1], [2, 3]) == [1, 2, 3]

    def test_single_elements(self):
        assert merge_lists(["a"], ["b"]) == ["a", "b"]

    def test_dict_items(self):
        a = [{"id": 1}]
        b = [{"id": 2}]
        result = merge_lists(a, b)
        assert result == [{"id": 1}, {"id": 2}]
        assert len(result) == 2


class TestAuditState:
    EXPECTED_KEYS = {
        "document_content",
        "document_name",
        "document_path",
        "document_type",
        "audit_focus",
        "matched_regulations",
        "regulation_summary",
        "regulation_checked",
        "findings",
        "risk_score",
        "risk_level",
        "risk_assessed",
        "report_markdown",
        "report_path",
        "report_generated",
        "report_source",
        "messages",
        "status",
    }

    def test_has_all_expected_keys(self):
        """AuditState TypedDict should declare all expected fields."""
        annotations = AuditState.__annotations__
        assert set(annotations.keys()) == self.EXPECTED_KEYS

    def test_messages_uses_merge_lists_reducer(self):
        """messages field should use Annotated[list, merge_lists]."""
        ann = AuditState.__annotations__["messages"]
        # Annotated[list, merge_lists] has __metadata__ containing merge_lists
        assert hasattr(ann, "__metadata__")
        assert merge_lists in ann.__metadata__

    def test_document_fields_are_str(self):
        for key in ("document_content", "document_name", "document_path", "document_type", "audit_focus"):
            assert AuditState.__annotations__[key] is str

    def test_list_fields_are_list(self):
        for key in ("matched_regulations", "findings"):
            ann = AuditState.__annotations__[key]
            # plain list or list[dict]
            assert ann is list or getattr(ann, "__origin__", None) is list

    def test_bool_fields(self):
        for key in ("regulation_checked", "risk_assessed", "report_generated"):
            assert AuditState.__annotations__[key] is bool

    def test_sample_state_fixture_completeness(self, sample_state):
        """sample_state fixture should cover all AuditState keys except optional ones."""
        required_keys = self.EXPECTED_KEYS - {"document_path", "report_source"}
        assert required_keys.issubset(set(sample_state.keys()))
