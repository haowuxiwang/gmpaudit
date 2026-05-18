"""Tests for agent/agents/risk_assessor.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agents.risk_assessor import risk_assessor_node


@pytest.mark.asyncio
class TestRiskAssessorNode:
    """Test risk_assessor_node with mocked LLM."""

    async def test_llm_success(self, sample_state, sample_regulations):
        """LLM returns valid findings JSON."""
        sample_state["matched_regulations"] = sample_regulations
        llm_findings = [
            {"title": "Missing record", "severity": "high", "type": "compliance_risk", "description": "test"}
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with patch("agent.agents.risk_assessor.get_llm", return_value=mock_llm), \
             patch("agent.agents.risk_assessor._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.risk_assessor._parse_llm_json", return_value=llm_findings):
            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert len(result["findings"]) > 0
        assert result["risk_score"] > 0
        assert result["risk_level"] == "high"

    async def test_llm_failure_degrades_gracefully(self, sample_state):
        """LLM fails, returns empty findings with running status (graceful degradation)."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with patch("agent.agents.risk_assessor.get_llm", return_value=mock_llm), \
             patch("agent.agents.risk_assessor._load_prompt", return_value=mock_prompt):
            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["status"] == "running"
        assert result["findings"] == []
        assert result["risk_score"] == 0
        assert result["risk_level"] == "not_assessed"

    async def test_finding_defaults_applied(self, sample_state):
        """Findings missing fields get default values."""
        incomplete_findings = [{"title": "Test finding"}]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with patch("agent.agents.risk_assessor.get_llm", return_value=mock_llm), \
             patch("agent.agents.risk_assessor._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.risk_assessor._parse_llm_json", return_value=incomplete_findings):
            result = await risk_assessor_node(sample_state)

        finding = result["findings"][0]
        assert finding["severity"] == "medium"  # default
        assert finding["type"] == "compliance"  # default
        assert finding["description"] == ""  # default

    async def test_risk_score_calculated(self, sample_state):
        """Risk score is calculated from findings."""
        findings = [
            {"title": "F1", "severity": "high", "type": "t", "description": "d"},
            {"title": "F2", "severity": "low", "type": "t", "description": "d"},
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with patch("agent.agents.risk_assessor.get_llm", return_value=mock_llm), \
             patch("agent.agents.risk_assessor._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.risk_assessor._parse_llm_json", return_value=findings):
            result = await risk_assessor_node(sample_state)

        # 1 high (20) + 1 low (5) = 25 deducted, score = 75
        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"

    async def test_empty_findings(self, sample_state):
        """LLM returns empty findings list."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with patch("agent.agents.risk_assessor.get_llm", return_value=mock_llm), \
             patch("agent.agents.risk_assessor._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.risk_assessor._parse_llm_json", return_value=[]):
            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["findings"] == []
        assert result["risk_score"] == 0
        assert result["risk_level"] == "not_assessed"
