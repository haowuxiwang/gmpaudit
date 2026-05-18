"""Tests for agent/agents/report_writer.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agents.report_writer import (
    _format_findings,
    _generate_fallback_report,
    report_writer_node,
)


class TestFormatFindings:
    """Test _format_findings pure function."""

    def test_empty_findings(self):
        """Empty list returns default message."""
        assert _format_findings([]) == "No findings identified."

    def test_single_finding(self):
        """Single finding formatted correctly."""
        findings = [{"title": "Test", "severity": "high", "description": "Desc", "evidence": "Ev"}]
        result = _format_findings(findings)
        assert "Finding 1" in result
        assert "[HIGH]" in result
        assert "Test" in result
        assert "Desc" in result
        assert "Ev" in result

    def test_multiple_findings(self):
        """Multiple findings numbered correctly."""
        findings = [
            {"title": "F1", "severity": "high", "description": "d1"},
            {"title": "F2", "severity": "low", "description": "d2"},
        ]
        result = _format_findings(findings)
        assert "Finding 1" in result
        assert "Finding 2" in result

    def test_missing_fields_use_defaults(self):
        """Findings with missing fields use defaults."""
        findings = [{}]  # No severity, title, etc.
        result = _format_findings(findings)
        assert "[N/A]" in result
        assert "Untitled" in result

    def test_optional_fields(self):
        """Optional fields included when present."""
        findings = [{
            "title": "T", "severity": "low", "description": "d",
            "suggestion": "Fix it", "regulation_ref": "GMP Ch2"
        }]
        result = _format_findings(findings)
        assert "Fix it" in result
        assert "GMP Ch2" in result


class TestGenerateFallbackReport:
    """Test _generate_fallback_report pure function."""

    def test_basic_report_structure(self, sample_findings):
        """Fallback report has all required sections."""
        report = _generate_fallback_report(
            "test.txt", "deviation", 55, "high", "Summary", sample_findings
        )
        assert "# GMP Compliance Audit Report" in report
        assert "## 1. Audit Overview" in report
        assert "## 2. Regulation Basis" in report
        assert "## 3. Audit Findings" in report
        assert "## 4. Risk Assessment" in report
        assert "## 5. Recommendations" in report
        assert "## 6. Conclusion" in report

    def test_report_contains_doc_info(self):
        """Report includes document name and type."""
        report = _generate_fallback_report("my_doc.pdf", "sop", 100, "low", "", [])
        assert "my_doc.pdf" in report
        assert "sop" in report

    def test_report_contains_risk_info(self, sample_findings):
        """Report includes risk score and level."""
        report = _generate_fallback_report("t", "t", 55, "high", "", sample_findings)
        assert "55/100" in report
        assert "high" in report

    def test_report_contains_severity_counts(self, sample_findings):
        """Report shows severity breakdown."""
        report = _generate_fallback_report("t", "t", 0, "", "", sample_findings)
        assert "High severity: 1" in report
        assert "Medium severity: 1" in report
        assert "Low severity: 1" in report

    def test_report_with_no_findings(self):
        """Report works with empty findings."""
        report = _generate_fallback_report("t", "t", 100, "low", "No regs", [])
        assert "High severity: 0" in report
        assert "No regs" in report


@pytest.mark.asyncio
class TestReportWriterNode:
    """Test report_writer_node with mocked LLM and filesystem."""

    async def test_llm_success(self, sample_state, sample_findings):
        """LLM generates report successfully."""
        sample_state["findings"] = sample_findings
        sample_state["risk_score"] = 55
        sample_state["risk_level"] = "high"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# Test Report"))
        mock_prompt = "Generate: {document_name}\n{findings_text}"

        with patch("agent.agents.report_writer.get_llm", return_value=mock_llm), \
             patch("agent.agents.report_writer._load_prompt", return_value=mock_prompt), \
             patch("pathlib.Path.write_text"), \
             patch("pathlib.Path.mkdir"):
            result = await report_writer_node(sample_state)

        assert result["report_generated"] is True
        assert result["status"] == "completed"
        assert result["report_markdown"] == "# Test Report"

    async def test_llm_fallback(self, sample_state, sample_findings):
        """LLM fails, uses fallback report generator."""
        sample_state["findings"] = sample_findings
        sample_state["risk_score"] = 55
        sample_state["risk_level"] = "high"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_prompt = "Generate: {document_name}\n{findings_text}"

        with patch("agent.agents.report_writer.get_llm", return_value=mock_llm), \
             patch("agent.agents.report_writer._load_prompt", return_value=mock_prompt), \
             patch("pathlib.Path.write_text"), \
             patch("pathlib.Path.mkdir"):
            result = await report_writer_node(sample_state)

        assert result["report_generated"] is True
        assert "GMP Compliance Audit Report" in result["report_markdown"]

    async def test_file_save_failure(self, sample_state):
        """File save fails but report content still returned."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# Report"))
        mock_prompt = "Generate: {document_name}\n{findings_text}"

        with patch("agent.agents.report_writer.get_llm", return_value=mock_llm), \
             patch("agent.agents.report_writer._load_prompt", return_value=mock_prompt), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_text", side_effect=PermissionError("No write access")):
            result = await report_writer_node(sample_state)

        assert result["report_generated"] is True
        assert result["report_path"] == ""
        assert result["report_markdown"] == "# Report"

    async def test_report_path_set(self, sample_state):
        """Report path is set on successful save."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# Report"))
        mock_prompt = "Generate: {document_name}\n{findings_text}"

        with patch("agent.agents.report_writer.get_llm", return_value=mock_llm), \
             patch("agent.agents.report_writer._load_prompt", return_value=mock_prompt), \
             patch("pathlib.Path.write_text"), \
             patch("pathlib.Path.mkdir"):
            result = await report_writer_node(sample_state)

        assert result["report_generated"] is True
        assert result["report_path"] != ""
        assert ".md" in result["report_path"]
