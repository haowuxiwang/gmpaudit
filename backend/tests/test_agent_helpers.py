"""Tests for app.utils.agent_helpers — build_initial_state and normalize_finding."""

import pytest

from app.models.finding import Finding, FindingType, SeverityLevel
from app.utils.agent_helpers import build_initial_state, normalize_finding


class TestBuildInitialState:
    def test_all_keys_present(self):
        state = build_initial_state("/path/to/doc.pdf", "deviation", focus="test focus", document_content="content")
        expected_keys = [
            "document_name", "document_path", "document_type", "audit_focus",
            "document_content", "matched_regulations", "regulation_summary",
            "regulation_checked", "findings", "risk_score", "risk_level",
            "risk_assessed", "report_markdown", "report_path", "report_generated",
            "report_source", "messages", "status",
        ]
        for key in expected_keys:
            assert key in state, f"Missing key: {key}"

    def test_document_name_defaults_to_path(self):
        state = build_initial_state("/path/to/doc.pdf", "deviation")
        assert state["document_name"] == "/path/to/doc.pdf"

    def test_document_name_explicit(self):
        state = build_initial_state("/path/to/doc.pdf", "deviation", document_name="custom_name.pdf")
        assert state["document_name"] == "custom_name.pdf"

    def test_empty_defaults(self):
        state = build_initial_state("/p", "t")
        assert state["matched_regulations"] == []
        assert state["findings"] == []
        assert state["risk_score"] == 0
        assert state["risk_level"] == ""
        assert state["report_markdown"] == ""
        assert state["messages"] == []
        assert state["status"] == "running"

    def test_focus_and_content_passed_through(self):
        state = build_initial_state("/p", "t", focus="GMP compliance", document_content="doc text")
        assert state["audit_focus"] == "GMP compliance"
        assert state["document_content"] == "doc text"


class TestNormalizeFinding:
    def test_severity_high(self):
        finding = normalize_finding({"severity": "high", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.HIGH

    def test_severity_critical_maps_to_high(self):
        finding = normalize_finding({"severity": "critical", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.HIGH

    def test_severity_medium(self):
        finding = normalize_finding({"severity": "medium", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.MEDIUM

    def test_severity_low(self):
        finding = normalize_finding({"severity": "low", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.LOW

    def test_severity_info_maps_to_low(self):
        finding = normalize_finding({"severity": "info", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.LOW

    def test_severity_unknown_defaults_to_medium(self):
        finding = normalize_finding({"severity": "unknown", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.MEDIUM

    def test_type_logic_flaw(self):
        finding = normalize_finding({"type": "logic_flaw", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.LOGIC_FLAW

    def test_type_compliance(self):
        finding = normalize_finding({"type": "compliance", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.COMPLIANCE_RISK

    def test_type_inconsistency(self):
        finding = normalize_finding({"type": "inconsistency", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.INCONSISTENCY

    def test_type_missing_info(self):
        finding = normalize_finding({"type": "missing_info", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.MISSING_INFO

    def test_type_best_practice(self):
        finding = normalize_finding({"type": "best_practice", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.BEST_PRACTICE

    def test_type_unknown_defaults_to_compliance_risk(self):
        finding = normalize_finding({"type": "something_else", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.COMPLIANCE_RISK

    def test_location_from_location_key(self):
        finding = normalize_finding({"location": "Section 3.1", "title": "T", "description": "D"}, task_id=1)
        assert finding.location == "Section 3.1"

    def test_location_fallback_to_source_section(self):
        finding = normalize_finding({"source_section": "Chapter 5", "title": "T", "description": "D"}, task_id=1)
        assert finding.location == "Chapter 5"

    def test_missing_title_defaults(self):
        finding = normalize_finding({"description": "D"}, task_id=1)
        assert finding.title == "Unknown finding"

    def test_missing_description_defaults(self):
        finding = normalize_finding({"title": "T"}, task_id=1)
        assert finding.description == ""

    def test_document_id_none(self):
        finding = normalize_finding({"title": "T", "description": "D"}, task_id=1, document_id=None)
        assert finding.document_id is None

    def test_document_id_set(self):
        finding = normalize_finding({"title": "T", "description": "D"}, task_id=1, document_id=42)
        assert finding.document_id == 42

    def test_task_id_set(self):
        finding = normalize_finding({"title": "T", "description": "D"}, task_id=99)
        assert finding.task_id == 99
