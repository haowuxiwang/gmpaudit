"""Integration tests for the LangGraph audit workflow."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.graph import build_audit_graph, parse_document_node
from agent.state import AuditState


class TestParseDocumentNode:
    """Test parse_document_node function."""

    def test_parse_existing_file(self):
        """Parse a real test document."""
        state = {
            "document_name": "tests/fixtures/sample_deviation.txt",
            "document_type": "unknown",
        }
        result = parse_document_node(state)

        assert result["document_content"] != ""
        assert result["document_type"] == "deviation"  # Should detect from content
        assert result["regulation_checked"] is False
        assert result["risk_assessed"] is False
        assert result["report_generated"] is False
        assert result["status"] == "running"

    def test_parse_nonexistent_file(self):
        """File not found returns error."""
        state = {
            "document_name": "nonexistent_file.txt",
            "document_type": "unknown",
        }
        result = parse_document_node(state)

        assert result["status"] == "error"
        assert "not found" in result["messages"][0].lower()

    def test_detect_deviation_type(self):
        """Detect deviation document type from content."""
        state = {
            "document_name": "tests/fixtures/sample_deviation.txt",
            "document_type": "unknown",
        }
        result = parse_document_node(state)

        assert result["document_type"] == "deviation"

    def test_preserves_known_type(self):
        """Preserve document type if already set."""
        state = {
            "document_name": "tests/fixtures/sample_deviation.txt",
            "document_type": "sop",
        }
        result = parse_document_node(state)

        assert result["document_type"] == "sop"


@pytest.mark.asyncio
class TestBuildAuditGraph:
    """Test the complete audit graph."""

    async def test_graph_compiles(self):
        """Graph compiles without errors."""
        graph = build_audit_graph()
        assert graph is not None

    async def test_full_pipeline_with_mocks(self, sample_findings):
        """Full pipeline runs with mocked LLM calls."""
        # Mock all LLM-dependent nodes
        mock_reg_result = {
            "matched_regulations": [{"title": "Test Regulation"}],
            "regulation_summary": "Test summary",
            "regulation_checked": True,
            "messages": ["Regulation Expert: found 1 relevant clauses"],
        }
        mock_risk_result = {
            "findings": sample_findings,
            "risk_score": 55,
            "risk_level": "high",
            "risk_assessed": True,
            "messages": ["Risk Assessor: identified 3 findings"],
        }
        mock_report_result = {
            "report_markdown": "# Test Report",
            "report_path": "/tmp/test_report.md",
            "report_generated": True,
            "status": "completed",
            "messages": ["Report Writer: report saved"],
        }

        # Build graph with mocked nodes
        with patch("agent.graph.regulation_expert_node", AsyncMock(return_value=mock_reg_result)), \
             patch("agent.graph.risk_assessor_node", AsyncMock(return_value=mock_risk_result)), \
             patch("agent.graph.report_writer_node", AsyncMock(return_value=mock_report_result)), \
             patch("agent.graph.parse_file", return_value="Test document content about 偏差处理"):
            graph = build_audit_graph()

            initial_state = {
                "document_name": "test.txt",
                "document_type": "unknown",
                "document_content": "",
                "audit_focus": "",
                "next_agent": "",
                "supervisor_reasoning": "",
                "matched_regulations": [],
                "regulation_summary": "",
                "regulation_checked": False,
                "findings": [],
                "risk_score": 0,
                "risk_level": "",
                "risk_assessed": False,
                "report_markdown": "",
                "report_path": "",
                "report_generated": False,
                "messages": [],
                "iteration": 0,
                "status": "",
            }

            result = await graph.ainvoke(initial_state)

            # Verify pipeline completed
            assert result["status"] == "completed"
            assert result["regulation_checked"] is True
            assert result["risk_assessed"] is True
            assert result["report_generated"] is True
            assert result["iteration"] > 0


@pytest.mark.asyncio
class TestSupervisorRouting:
    """Test supervisor routing in the graph context."""

    async def test_error_state_stops_pipeline(self):
        """Error state in document parsing stops pipeline."""
        with patch("agent.graph.parse_file", side_effect=Exception("Parse error")):
            graph = build_audit_graph()

            initial_state = {
                "document_name": "bad_file.txt",
                "document_type": "unknown",
                "document_content": "",
                "audit_focus": "",
                "next_agent": "",
                "supervisor_reasoning": "",
                "matched_regulations": [],
                "regulation_summary": "",
                "regulation_checked": False,
                "findings": [],
                "risk_score": 0,
                "risk_level": "",
                "risk_assessed": False,
                "report_markdown": "",
                "report_path": "",
                "report_generated": False,
                "messages": [],
                "iteration": 0,
                "status": "",
            }

            result = await graph.ainvoke(initial_state)

            # Pipeline should stop with error
            assert result["status"] == "error"
