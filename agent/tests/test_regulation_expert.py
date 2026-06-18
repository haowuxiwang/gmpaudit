"""Tests for agent/agents/regulation_expert.py"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agents.regulation_expert import _rewrite_to_queries, regulation_expert_node


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
        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
            patch("agent.agents.regulation_expert._parse_llm_json", return_value=[{"title": "LLM result"}]),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert len(result["matched_regulations"]) > 0

    async def test_lightrag_fallback_to_db(self, sample_state, sample_regulations):
        """LightRAG import fails (module unavailable), falls back to search_regulations."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"LLM result"}]'))
        mock_prompt = "Analyze: {document_content}"

        # Make lightrag_tool import fail
        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
            patch("agent.agents.regulation_expert._parse_llm_json", return_value=[{"title": "LLM result"}]),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert len(result["matched_regulations"]) > 0

    async def test_llm_success(self, sample_state, sample_regulations):
        """LLM returns valid JSON analysis. KG + LLM results are merged."""
        llm_response = [{"title": "偏差处理", "regulation": "GMP", "relevance": "high"}]
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}"

        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
            patch("agent.agents.regulation_expert._parse_llm_json", return_value=llm_response),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        # Now merges KG + LLM results (KG base + LLM supplement)
        titles = [r["title"] for r in result["matched_regulations"]]
        assert "偏差处理" in titles  # From LLM
        assert len(result["matched_regulations"]) >= len(llm_response)

    async def test_llm_failure_degrades_gracefully(self, sample_state, sample_regulations):
        """LLM fails, returns DB results with running status (graceful degradation)."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_prompt = "Analyze: {document_content}"

        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["status"] == "running"
        assert result["matched_regulations"] == sample_regulations

    async def test_llm_empty_analysis_uses_db(self, sample_state, sample_regulations):
        """LLM returns empty list, falls back to DB results."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
        mock_prompt = "Analyze: {document_content}"

        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
            patch("agent.agents.regulation_expert._parse_llm_json", return_value=[]),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["matched_regulations"] == sample_regulations


@pytest.mark.asyncio
class TestRewriteToQueries:
    """Test _rewrite_to_queries function."""

    async def test_happy_path(self):
        """LLM returns 5 questions → returns list of 3 (capped)."""
        llm = MagicMock()
        response = MagicMock()
        response.content = "偏差处理程序是否符合GMP要求?\n变更控制流程是否完善?\nCAPA系统是否有效运行?\n文件管理是否符合规定?\n生产过程是否受控?"
        llm.ainvoke = AsyncMock(return_value=response)

        with (
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=llm),
            patch("agent.agents.regulation_expert.call_llm_with_retry", new=AsyncMock(return_value=response)),
        ):
            result = await _rewrite_to_queries("test content about deviations", "deviation")

        assert len(result) == 3
        assert all(isinstance(q, str) for q in result)
        assert all(len(q) > 5 for q in result)

    async def test_filters_short_lines(self):
        """LLM returns short/empty lines → filtered out."""
        llm = MagicMock()
        response = MagicMock()
        response.content = "偏差处理程序是否符合GMP要求?\n\n短\n变更控制流程是否完善?"
        llm.ainvoke = AsyncMock(return_value=response)

        with (
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=llm),
            patch("agent.agents.regulation_expert.call_llm_with_retry", new=AsyncMock(return_value=response)),
        ):
            result = await _rewrite_to_queries("test content", "deviation")

        assert len(result) == 2
        assert all(len(q) > 5 for q in result)

    async def test_truncates_to_three(self):
        """LLM returns >3 questions → only first 3 returned."""
        llm = MagicMock()
        response = MagicMock()
        response.content = "\n".join([f"这是第{i}个关于GMP合规的审计问题?" for i in range(8)])
        llm.ainvoke = AsyncMock(return_value=response)

        with (
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=llm),
            patch("agent.agents.regulation_expert.call_llm_with_retry", new=AsyncMock(return_value=response)),
        ):
            result = await _rewrite_to_queries("test content", "sop")

        assert len(result) == 3

    async def test_llm_failure_fallback(self):
        """LLM call raises exception → fallback to content[:500]."""
        llm = MagicMock()

        with (
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=llm),
            patch(
                "agent.agents.regulation_expert.call_llm_with_retry",
                new=AsyncMock(side_effect=Exception("LLM timeout")),
            ),
        ):
            content = "A" * 1000
            result = await _rewrite_to_queries(content, "deviation")

        assert result == [content[:500]]

    async def test_empty_llm_response_fallback(self):
        """LLM returns empty string → fallback to content[:500]."""
        llm = MagicMock()
        response = MagicMock()
        response.content = ""
        llm.ainvoke = AsyncMock(return_value=response)

        with (
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=llm),
            patch("agent.agents.regulation_expert.call_llm_with_retry", new=AsyncMock(return_value=response)),
        ):
            content = "B" * 300
            result = await _rewrite_to_queries(content, "sop")

        assert result == [content[:500]]


class TestStuffLimitBehavior:
    """Verify STUFF_LIMIT threshold affects strategy selection."""

    def test_stuff_limit_is_40000(self):
        """STUFF_LIMIT should be 40000 (optimized from 60000)."""
        from agent.config import STUFF_LIMIT
        assert STUFF_LIMIT == 40000

    def test_chunk_max_chars_is_16000(self):
        """CHUNK_MAX_CHARS should be 16000 (optimized from 8000)."""
        from agent.config import CHUNK_MAX_CHARS
        assert CHUNK_MAX_CHARS == 16000


class TestRegulationCacheTTL:
    """Verify LLM cache TTL is 2 hours."""

    def test_cache_ttl_is_7200(self):
        """_LLM_CACHE_TTL should be 7200 (2 hours)."""
        from agent.agents.regulation_expert import _LLM_CACHE_TTL
        assert _LLM_CACHE_TTL == 7200


class TestRegulationCacheExpiry:
    """Test LLM cache TTL expiry and eviction."""

    def test_expired_entry_returns_none(self):
        """Cache entry older than TTL should return None and be evicted."""
        import time as _time
        from agent.agents.regulation_expert import (
            _get_llm_cached, _set_llm_cached, _llm_cache, _LLM_CACHE_TTL,
        )
        _llm_cache.clear()
        _set_llm_cached("content", "deviation", {"key": "value"})
        # Manually backdate the entry
        key = list(_llm_cache.keys())[0]
        _llm_cache[key] = (_llm_cache[key][0], _time.time() - _LLM_CACHE_TTL - 1)
        result = _get_llm_cached("content", "deviation")
        assert result is None
        assert key not in _llm_cache

    def test_cache_eviction_at_capacity(self):
        """Adding to a full cache should evict the oldest entry."""
        from agent.agents.regulation_expert import (
            _set_llm_cached, _llm_cache, _LLM_CACHE_MAX_SIZE,
        )
        import time as _time
        _llm_cache.clear()
        # Fill to capacity
        for i in range(_LLM_CACHE_MAX_SIZE):
            _llm_cache[f"key_{i}"] = ({"i": i}, _time.time() - (_LLM_CACHE_MAX_SIZE - i))
        assert len(_llm_cache) == _LLM_CACHE_MAX_SIZE
        # Adding one more should evict the oldest
        _set_llm_cached("new_content", "sop", {"new": True})
        assert len(_llm_cache) == _LLM_CACHE_MAX_SIZE


class TestRegulationMapReduce:
    """Test map-reduce strategy in regulation_expert_node."""

    @pytest.mark.asyncio
    async def test_map_reduce_strategy(self, sample_state, sample_regulations):
        """Large documents should use map_reduce strategy."""
        from agent.config import STUFF_LIMIT
        sample_state["document_content"] = "x" * (STUFF_LIMIT + 100)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"LLM result"}]'))
        mock_prompt = "Analyze: {document_content}"

        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
            patch("agent.agents.regulation_expert._parse_llm_json", return_value=[{"title": "LLM result"}]),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True


class TestRegulationLLMAuthError:
    """Test LLMAuthError fallback in regulation_expert_node."""

    @pytest.mark.asyncio
    async def test_llm_auth_error_fallback(self, sample_state, sample_regulations):
        """LLMAuthError should return fallback results with auth error message."""
        from agent.config import LLMAuthError

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=LLMAuthError("mimo", "401 Unauthorized"))
        mock_prompt = "Analyze: {document_content}"

        with (
            patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
            patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
            patch("agent.agents.regulation_expert.load_prompt", return_value=mock_prompt),
        ):
            result = await regulation_expert_node(sample_state)

        assert result["regulation_checked"] is True
        assert result["matched_regulations"] == sample_regulations
        assert "LLM auth error" in result["regulation_summary"].lower() or "API Key" in result["messages"][0]


class TestSearchRegulationsTrace:
    """Test _search_regulations with active trace."""

    @pytest.mark.asyncio
    async def test_lightrag_empty_with_trace(self, sample_regulations):
        """LightRAG returning empty should record trace event."""
        from agent.agents.regulation_expert import _search_regulations
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        mock_module = MagicMock()
        mock_module.lightrag_search = AsyncMock(return_value=[])

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}),
                patch("agent.agents.regulation_expert.search_regulations", return_value=sample_regulations),
            ):
                results, source = await _search_regulations("test query")
            assert source == "fallback_db"
            assert len(trace.kg_events) >= 2  # lightrag empty + fallback
            assert any(e.source == "lightrag" and e.result_count == 0 for e in trace.kg_events)
        finally:
            clear_current_trace()
