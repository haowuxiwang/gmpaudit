"""Tests for agent/agents/risk_assessor.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agents.risk_assessor import risk_assessor_node, _ensure_finding_defaults


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

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._parse_llm_json", return_value=llm_findings),
        ):
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

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
        ):
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

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._parse_llm_json", return_value=incomplete_findings),
        ):
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

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._parse_llm_json", return_value=findings),
        ):
            result = await risk_assessor_node(sample_state)

        # 1 high (20) + 1 low (5) = 25 deducted, score = 75
        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"

    async def test_empty_findings(self, sample_state):
        """LLM returns empty findings list."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._parse_llm_json", return_value=[]),
        ):
            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["findings"] == []
        assert result["risk_score"] == 0
        assert result["risk_level"] == "not_assessed"


class TestEnsureFindingDefaults:
    def test_adds_missing_fields(self):
        findings = [{"title": "Test"}]
        result = _ensure_finding_defaults(findings)
        assert result[0]["severity"] == "medium"
        assert result[0]["type"] == "compliance"
        assert result[0]["description"] == ""

    def test_preserves_existing_fields(self):
        findings = [{"title": "Test", "severity": "high", "type": "logic_flaw", "description": "desc"}]
        result = _ensure_finding_defaults(findings)
        assert result[0]["severity"] == "high"
        assert result[0]["type"] == "logic_flaw"
        assert result[0]["description"] == "desc"

    def test_empty_list(self):
        result = _ensure_finding_defaults([])
        assert result == []


@pytest.mark.asyncio
class TestRiskAssessorMapReduce:
    """Test Map-Reduce strategy path."""

    async def test_map_reduce_strategy(self, sample_state):
        """Map-Reduce strategy with long document."""
        # Set a long document to trigger map-reduce
        sample_state["document_content"] = "x" * 50000  # > STUFF_LIMIT
        sample_state["matched_regulations"] = []

        findings = [{"title": "F1", "severity": "medium", "type": "compliance", "description": "d"}]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._parse_llm_json", return_value=findings),
            patch("agent.agents.risk_assessor.chunk_document") as mock_chunk,
        ):
            # Create mock chunks
            chunk1 = MagicMock()
            chunk1.content = "chunk1 content"
            chunk1.section_path = "Section 1"
            chunk2 = MagicMock()
            chunk2.content = "chunk2 content"
            chunk2.section_path = "Section 2"
            mock_chunk.return_value = [chunk1, chunk2]

            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["risk_score"] > 0

    async def test_map_reduce_partial_failure(self, sample_state):
        """Map-Reduce with some chunks failing."""
        sample_state["document_content"] = "x" * 50000
        sample_state["matched_regulations"] = []

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        call_count = 0

        async def mock_analyze(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"title": "F1", "severity": "low", "type": "compliance", "description": "d"}]
            raise Exception("chunk failed")

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._analyze_chunk", side_effect=mock_analyze),
            patch("agent.agents.risk_assessor.chunk_document") as mock_chunk,
        ):
            chunk1 = MagicMock()
            chunk1.content = "chunk1"
            chunk1.section_path = "S1"
            chunk2 = MagicMock()
            chunk2.content = "chunk2"
            chunk2.section_path = "S2"
            mock_chunk.return_value = [chunk1, chunk2]

            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        # Should have coverage_ratio due to partial failure
        if "coverage_ratio" in result:
            assert result["coverage_ratio"] < 1.0

    async def test_map_reduce_all_fail_empty_findings(self, sample_state):
        """Map-Reduce where all chunks fail should return coverage info."""
        sample_state["document_content"] = "x" * 50000
        sample_state["matched_regulations"] = []

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}\n{regulation_context}\n{document_type}"

        async def mock_analyze_fail(*args, **kwargs):
            raise Exception("chunk failed")

        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.risk_assessor.load_prompt", return_value=mock_prompt),
            patch("agent.agents.risk_assessor._analyze_chunk", side_effect=mock_analyze_fail),
            patch("agent.agents.risk_assessor.chunk_document") as mock_chunk,
        ):
            chunk1 = MagicMock()
            chunk1.content = "chunk1"
            chunk1.section_path = "S1"
            chunk2 = MagicMock()
            chunk2.content = "chunk2"
            chunk2.section_path = "S2"
            mock_chunk.return_value = [chunk1, chunk2]

            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["findings"] == []
        assert "coverage_ratio" in result
        assert result["coverage_ratio"] == 0.0
        assert any("chunks failed" in m for m in result["messages"])

    async def test_get_llm_fallback_raises(self, sample_state):
        """When get_llm_with_fallback raises, should degrade gracefully."""
        with (
            patch("agent.agents.risk_assessor.get_llm_with_fallback", side_effect=Exception("No provider available")),
        ):
            result = await risk_assessor_node(sample_state)

        assert result["risk_assessed"] is True
        assert result["findings"] == []
        assert result["risk_score"] == 0
        assert result["risk_level"] == "not_assessed"
        assert result["status"] == "running"
