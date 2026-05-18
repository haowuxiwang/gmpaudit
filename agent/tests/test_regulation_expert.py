"""Tests for agent/agents/regulation_expert.py"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agents.regulation_expert import regulation_expert_node


@pytest.mark.asyncio
class TestRegulationExpertNode:
    """Test regulation_expert_node with mocked dependencies."""

    async def test_lightrag_success(self, sample_state, sample_regulations):
        """LightRAG returns results, no fallback to DB."""
        mock_lightrag = AsyncMock(return_value=sample_regulations)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"LLM result"}]'))
        mock_prompt = "Analyze: {document_content}"

        # lightrag_search is dynamically imported inside the function
        # We need to mock it in the module where it's defined
        mock_module = MagicMock()
        mock_module.lightrag_search = mock_lightrag
        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}), \
             patch("agent.agents.regulation_expert.get_llm", return_value=mock_llm), \
             patch("agent.agents.regulation_expert._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.regulation_expert._parse_llm_json", return_value=[{"title": "LLM result"}]):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert len(result["matched_regulations"]) > 0

    async def test_lightrag_fallback_to_db(self, sample_state, sample_regulations):
        """LightRAG import fails (module unavailable), falls back to search_regulations."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"LLM result"}]'))
        mock_prompt = "Analyze: {document_content}"

        # Make lightrag_tool import fail
        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}), \
             patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations), \
             patch("agent.agents.regulation_expert.get_llm", return_value=mock_llm), \
             patch("agent.agents.regulation_expert._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.regulation_expert._parse_llm_json", return_value=[{"title": "LLM result"}]):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert len(result["matched_regulations"]) > 0

    async def test_llm_success(self, sample_state, sample_regulations):
        """LLM returns valid JSON analysis."""
        llm_response = [{"title": "偏差处理", "regulation": "GMP", "relevance": "high"}]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}"

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}), \
             patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations), \
             patch("agent.agents.regulation_expert.get_llm", return_value=mock_llm), \
             patch("agent.agents.regulation_expert._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.regulation_expert._parse_llm_json", return_value=llm_response):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["matched_regulations"] == llm_response

    async def test_llm_failure_degrades_gracefully(self, sample_state, sample_regulations):
        """LLM fails, returns DB results with running status (graceful degradation)."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_prompt = "Analyze: {document_content}"

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}), \
             patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations), \
             patch("agent.agents.regulation_expert.get_llm", return_value=mock_llm), \
             patch("agent.agents.regulation_expert._load_prompt", return_value=mock_prompt):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["status"] == "running"
        assert result["matched_regulations"] == sample_regulations

    async def test_llm_empty_analysis_uses_db(self, sample_state, sample_regulations):
        """LLM returns empty list, falls back to DB results."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}"

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}), \
             patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations), \
             patch("agent.agents.regulation_expert.get_llm", return_value=mock_llm), \
             patch("agent.agents.regulation_expert._load_prompt", return_value=mock_prompt), \
             patch("agent.agents.regulation_expert._parse_llm_json", return_value=[]):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["matched_regulations"] == sample_regulations
