"""Tests for agent/tools/lightrag_tool.py — cache, helpers, search, index build."""

import asyncio
import hashlib
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.tools.lightrag_tool as lightrag_mod
from agent.tools.lightrag_tool import (
    _cache_key,
    _extract_keywords_locally,
    _extract_title,
    _get_cached,
    _set_cached,
    _query_cache,
    _QUERY_CACHE_MAX_SIZE,
    _QUERY_CACHE_TTL,
    get_cache_stats,
    get_lightrag,
    lightrag_search,
    reset_lightrag,
    build_index,
    preload_embedding_model,
)
from agent.tools.lightrag_tool import _get_embedding_func, _get_llm_func, _get_llm_client


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------
class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("query", "local")
        k2 = _cache_key("query", "local")
        assert k1 == k2

    def test_different_query_different_key(self):
        k1 = _cache_key("query1", "local")
        k2 = _cache_key("query2", "local")
        assert k1 != k2

    def test_different_method_different_key(self):
        k1 = _cache_key("query", "local")
        k2 = _cache_key("query", "global")
        assert k1 != k2

    def test_returns_md5_hex(self):
        k = _cache_key("test", "mix")
        expected = hashlib.md5("mix:test".encode()).hexdigest()
        assert k == expected


# ---------------------------------------------------------------------------
# _get_cached / _set_cached
# ---------------------------------------------------------------------------
class TestCacheGetSet:
    def setup_method(self):
        _query_cache.clear()

    def test_miss_returns_none(self):
        assert _get_cached("nonexistent", "local") is None

    def test_hit_returns_result(self):
        result = [{"title": "test"}]
        _set_cached("query", "local", result)
        assert _get_cached("query", "local") == result

    def test_ttl_expired_returns_none(self):
        result = [{"title": "old"}]
        key = _cache_key("old_query", "local")
        _query_cache[key] = (result, time.time() - _QUERY_CACHE_TTL - 1)
        assert _get_cached("old_query", "local") is None
        # Entry should be evicted
        assert key not in _query_cache

    def test_lru_eviction_at_capacity(self):
        # Fill cache to capacity
        for i in range(_QUERY_CACHE_MAX_SIZE):
            _set_cached(f"q{i}", "local", [{"i": i}])
        assert len(_query_cache) == _QUERY_CACHE_MAX_SIZE

        # Add one more — oldest should be evicted
        _set_cached("new_query", "local", [{"new": True}])
        assert len(_query_cache) == _QUERY_CACHE_MAX_SIZE
        assert _get_cached("new_query", "local") == [{"new": True}]

    def test_get_cached_increments_hit_counter(self):
        _set_cached("hit_query", "local", [{"r": 1}])
        # Access via module reference
        import agent.tools.lightrag_tool as mod
        before = mod._cache_hits
        _get_cached("hit_query", "local")
        assert mod._cache_hits == before + 1


# ---------------------------------------------------------------------------
# get_cache_stats
# ---------------------------------------------------------------------------
class TestGetCacheStats:
    def setup_method(self):
        _query_cache.clear()

    def test_empty_cache(self):
        stats = get_cache_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == _QUERY_CACHE_MAX_SIZE
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0

    def test_after_set_and_get(self):
        _set_cached("q", "local", [{"r": 1}])
        _get_cached("q", "local")
        stats = get_cache_stats()
        assert stats["size"] == 1


# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------
class TestExtractTitle:
    def test_heading_like_first_line(self):
        content = "偏差处理程序\n这是详细内容"
        assert _extract_title(content, "偏差") == "偏差处理程序"

    def test_first_line_too_long(self):
        content = "A" * 100 + "\nShort line"
        title = _extract_title(content, "query")
        # Should fall back to first sentence or truncation
        assert len(title) <= 80

    def test_first_line_ends_with_period(self):
        content = "这是一句话。\n更多内容"
        title = _extract_title(content, "query")
        # First line ends with 。 — falls back to first sentence extraction
        assert "。" not in title or title.endswith("...")

    def test_truncation_fallback(self):
        content = "A" * 200
        title = _extract_title(content, "q")
        assert len(title) <= 63  # 60 + "..."

    def test_short_content_no_ellipsis(self):
        content = "Short"
        title = _extract_title(content, "q")
        assert "..." not in title


# ---------------------------------------------------------------------------
# _extract_keywords_locally
# ---------------------------------------------------------------------------
class TestExtractKeywordsLocally:
    def test_returns_nonempty_lists(self):
        hl, ll = _extract_keywords_locally("偏差处理程序是否符合GMP要求")
        assert len(hl) > 0
        assert len(ll) > 0
        assert all(isinstance(k, str) for k in hl)
        assert all(isinstance(k, str) for k in ll)

    def test_extracts_chinese_gmp_terms(self):
        hl, ll = _extract_keywords_locally("偏差调查根本原因分析CAPA纠正预防措施")
        all_keywords = hl + ll
        assert len(all_keywords) >= 2
        assert all(len(k) > 1 for k in all_keywords)

    def test_hl_keywords_max_5(self):
        query = "这是一个关于质量管理体系建设和GMP合规性审查以及偏差处理和变更控制和CAPA系统的长查询"
        hl, _ = _extract_keywords_locally(query)
        assert len(hl) <= 5

    def test_ll_keywords_max_8(self):
        query = "这是一个关于质量管理体系建设和GMP合规性审查以及偏差处理和变更控制和CAPA系统的非常长的查询包含很多关键词"
        _, ll = _extract_keywords_locally(query)
        assert len(ll) <= 8

    def test_empty_query_fallback(self):
        hl, ll = _extract_keywords_locally("")
        assert len(hl) > 0
        assert len(ll) > 0

    def test_short_query_fallback(self):
        hl, ll = _extract_keywords_locally("GMP")
        assert len(hl) > 0
        assert len(ll) > 0

    def test_no_jieba_fallback(self, monkeypatch):
        """If jieba is not available, should still return results via regex fallback."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jieba":
                raise ImportError("mocked jieba not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        hl, ll = _extract_keywords_locally("偏差处理 SOP合规 风险评估")
        assert isinstance(hl, list)
        assert isinstance(ll, list)


# ---------------------------------------------------------------------------
# reset_lightrag
# ---------------------------------------------------------------------------
class TestResetLightrag:
    def test_resets_singleton(self):
        import agent.tools.lightrag_tool as mod

        mod._lightrag_instance = MagicMock()
        reset_lightrag()
        assert mod._lightrag_instance is None


# ---------------------------------------------------------------------------
# get_lightrag (singleton)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetLightrag:
    async def test_returns_same_instance(self):
        """Two calls should return the same object."""
        import agent.tools.lightrag_tool as mod

        mock_rag = MagicMock()
        mock_rag.initialize_storages = AsyncMock()

        mock_lightrag_cls = MagicMock(return_value=mock_rag)

        mod._lightrag_instance = None
        try:
            with (
                patch("agent.tools.lightrag_tool.WORKING_DIR") as mock_dir,
                patch.dict("sys.modules", {"lightrag": MagicMock(), "lightrag.LightRAG": mock_lightrag_cls}),
            ):
                mock_dir.mkdir = MagicMock()
                mock_dir.__truediv__ = lambda self, x: MagicMock()
                mock_dir.exists.return_value = True

                with patch("agent.tools.lightrag_tool._get_embedding_func", return_value=MagicMock()):
                    with patch("agent.tools.lightrag_tool._get_llm_func", return_value=MagicMock()):
                        with patch("lightrag.LightRAG", mock_lightrag_cls, create=True):
                            # Directly set the singleton for the test
                            mod._lightrag_instance = mock_rag
                            r1 = await mod.get_lightrag()
                            r2 = await mod.get_lightrag()
                            assert r1 is r2 is mock_rag
        finally:
            mod._lightrag_instance = None

    async def test_initializes_lightrag_from_scratch(self):
        """get_lightrag() should initialize LightRAG when singleton is None."""
        import agent.tools.lightrag_tool as mod

        mock_rag = MagicMock()
        mock_rag.initialize_storages = AsyncMock()
        mock_lightrag_module = MagicMock()
        mock_lightrag_module.LightRAG = MagicMock(return_value=mock_rag)

        old_instance = mod._lightrag_instance
        mod._lightrag_instance = None
        try:
            with (
                patch("agent.tools.lightrag_tool.WORKING_DIR") as mock_dir,
                patch("agent.tools.lightrag_tool._get_embedding_func", return_value=MagicMock()),
                patch("agent.tools.lightrag_tool._get_llm_func", return_value=MagicMock()),
                patch.dict("sys.modules", {"lightrag": mock_lightrag_module}),
            ):
                mock_dir.mkdir = MagicMock()
                result = await mod.get_lightrag()

            assert result is mock_rag
            mock_rag.initialize_storages.assert_awaited_once()
            assert mod._lightrag_instance is mock_rag
        finally:
            mod._lightrag_instance = old_instance


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestBuildIndex:
    async def test_missing_input_dir_raises(self):
        with patch("agent.tools.lightrag_tool.INPUT_DIR") as mock_dir:
            mock_dir.is_dir.return_value = False
            with pytest.raises(FileNotFoundError, match="Input directory not found"):
                await build_index()

    async def test_no_files_raises(self, tmp_path):
        empty_dir = tmp_path / "empty_input"
        empty_dir.mkdir()
        with patch("agent.tools.lightrag_tool.INPUT_DIR", empty_dir):
            with pytest.raises(FileNotFoundError, match="No .txt or .md files"):
                await build_index()

    async def test_skips_empty_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "empty.txt").write_text("   \n  ", encoding="utf-8")

        mock_rag = MagicMock()
        mock_rag.ainsert = AsyncMock()

        with (
            patch("agent.tools.lightrag_tool.INPUT_DIR", input_dir),
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            await build_index()

        # ainsert should NOT be called for empty file
        mock_rag.ainsert.assert_not_called()

    async def test_indexes_nonempty_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "reg1.txt").write_text("GMP regulation content here", encoding="utf-8")
        (input_dir / "reg2.md").write_text("# Markdown regulation", encoding="utf-8")

        mock_rag = MagicMock()
        mock_rag.ainsert = AsyncMock()

        with (
            patch("agent.tools.lightrag_tool.INPUT_DIR", input_dir),
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            await build_index()

        assert mock_rag.ainsert.call_count == 2

    async def test_force_rebuild_clears_index(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "reg.txt").write_text("Content", encoding="utf-8")

        mock_rag = MagicMock()
        mock_rag.ainsert = AsyncMock()

        import agent.tools.lightrag_tool as mod
        mod._lightrag_instance = MagicMock()  # pre-set

        with (
            patch("agent.tools.lightrag_tool.INPUT_DIR", input_dir),
            patch("agent.tools.lightrag_tool.WORKING_DIR") as mock_wd,
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
            patch("agent.tools.lightrag_tool.reset_lightrag") as mock_reset,
            patch("agent.tools.lightrag_tool.shutil.rmtree") as mock_rmtree,
        ):
            mock_wd.exists.return_value = True
            await build_index(force_rebuild=True)

        mock_rmtree.assert_called_once()
        mock_reset.assert_called_once()


# ---------------------------------------------------------------------------
# lightrag_search
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestLightragSearch:
    def setup_method(self):
        _query_cache.clear()

    async def test_cache_hit(self):
        """Cached result should be returned without calling RAG."""
        _set_cached("cached query", "local", [{"title": "cached"}])
        result = await lightrag_search("cached query", method="local")
        assert result == [{"title": "cached"}]

    async def test_empty_result(self):
        """Empty RAG result returns empty list and caches it."""
        mock_rag = MagicMock()
        mock_rag.aquery = AsyncMock(return_value="")

        with (
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            result = await lightrag_search("new query", method="local")

        assert result == []
        # Should be cached now
        assert _get_cached("new query", "local") == []

    async def test_success_with_result(self):
        """Non-empty RAG result wraps in expected format."""
        mock_rag = MagicMock()
        mock_rag.aquery = AsyncMock(return_value="GMP要求企业建立偏差处理程序。任何偏差都应当记录并说明。")

        with (
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            result = await lightrag_search("偏差处理", method="mix")

        assert len(result) == 1
        assert result[0]["regulation"] == "GMP法规知识库"
        assert "偏差" in result[0]["content"]
        assert result[0]["relevance"] == "知识图谱语义匹配"

    async def test_invalid_method_defaults_to_mix(self):
        """Invalid method should default to 'mix' mode."""
        mock_rag = MagicMock()
        mock_rag.aquery = AsyncMock(return_value="Some result")

        with (
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            await lightrag_search("test", method="invalid_mode")

        # Should have been called with QueryParam(mode="mix", ...)
        call_args = mock_rag.aquery.call_args
        param = call_args[1]["param"] if "param" in call_args[1] else call_args[0][1]
        assert param.mode == "mix"

    async def test_exception_propagates(self):
        """Exceptions from RAG should propagate."""
        mock_rag = MagicMock()
        mock_rag.aquery = AsyncMock(side_effect=RuntimeError("RAG broken"))

        with (
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
            pytest.raises(RuntimeError, match="RAG broken"),
        ):
            await lightrag_search("fail query", method="local")

    async def test_caches_successful_result(self):
        """Successful search result should be cached for subsequent calls."""
        mock_rag = MagicMock()
        mock_rag.aquery = AsyncMock(return_value="Result content about GMP")

        with (
            patch("agent.tools.lightrag_tool.get_lightrag", new_callable=AsyncMock, return_value=mock_rag),
        ):
            await lightrag_search("cache_test_q", method="global")

        cached = _get_cached("cache_test_q", "global")
        assert cached is not None
        assert len(cached) == 1
        assert "Result content" in cached[0]["content"]


# ---------------------------------------------------------------------------
# _get_llm_client
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetLlmClient:
    async def test_creates_client(self):
        from agent.tools.lightrag_tool import _get_llm_client, _llm_client

        import agent.tools.lightrag_tool as mod
        old_client = mod._llm_client
        mod._llm_client = None
        try:
            client = await _get_llm_client()
            assert client is not None
            assert not client.is_closed
            # Second call returns same client
            client2 = await _get_llm_client()
            assert client2 is client
        finally:
            # Cleanup: close the client we created
            if mod._llm_client and not mod._llm_client.is_closed:
                await mod._llm_client.aclose()
            mod._llm_client = old_client

    async def test_recreates_closed_client(self):
        from agent.tools.lightrag_tool import _get_llm_client

        import agent.tools.lightrag_tool as mod
        old_client = mod._llm_client
        closed_client = MagicMock()
        closed_client.is_closed = True
        mod._llm_client = closed_client
        try:
            client = await _get_llm_client()
            assert client is not None
            assert not client.is_closed
        finally:
            if mod._llm_client and not mod._llm_client.is_closed:
                await mod._llm_client.aclose()
            mod._llm_client = old_client


# ---------------------------------------------------------------------------
# _get_embedding_func
# ---------------------------------------------------------------------------
class TestGetEmbeddingFunc:
    def test_returns_embedding_func(self):
        """_get_embedding_func should return an EmbeddingFunc-like object."""
        with patch.dict("sys.modules", {
            "lightrag": MagicMock(),
            "lightrag.utils": MagicMock(),
        }):
            mock_embedding_func = MagicMock()
            with patch("lightrag.utils.EmbeddingFunc", return_value=mock_embedding_func):
                result = _get_embedding_func()
                assert result is mock_embedding_func


# ---------------------------------------------------------------------------
# preload_embedding_model
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestPreloadEmbeddingModel:
    async def test_already_loaded(self):
        """If model is already loaded, should return immediately."""
        import agent.tools.lightrag_tool as mod
        old_model = mod._embedding_model
        mod._embedding_model = MagicMock()
        try:
            # Should not raise, should return quickly
            await preload_embedding_model()
        finally:
            mod._embedding_model = old_model

    async def test_first_load(self):
        """First call should load the model."""
        import agent.tools.lightrag_tool as mod
        old_model = mod._embedding_model
        mod._embedding_model = None
        try:
            mock_model = MagicMock()
            with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
                await preload_embedding_model()
            assert mod._embedding_model is mock_model
        finally:
            mod._embedding_model = old_model

    async def test_load_failure_is_safe(self):
        """If model loading fails, should not crash."""
        import agent.tools.lightrag_tool as mod
        old_model = mod._embedding_model
        mod._embedding_model = None
        try:
            with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("no model")):
                # Should not raise
                await preload_embedding_model()
            # Model should remain None
            assert mod._embedding_model is None
        finally:
            mod._embedding_model = old_model

    async def test_double_check_in_lock(self):
        """If model loads between outer check and lock, inner check should return."""
        import agent.tools.lightrag_tool as mod
        old_model = mod._embedding_model
        mod._embedding_model = None

        class FakeLock:
            """Lock that sets _embedding_model on acquire to simulate race condition."""
            async def __aenter__(self):
                # Simulate another coroutine loading the model
                mod._embedding_model = MagicMock()
                return self
            async def __aexit__(self, *args):
                pass

        try:
            with patch.object(mod, "_embedding_lock", FakeLock()):
                await preload_embedding_model()
            # Should have returned without loading (model set by FakeLock)
            assert mod._embedding_model is not None
        finally:
            mod._embedding_model = old_model


# ---------------------------------------------------------------------------
# _get_embedding_func — inner embed function (lines 60-71)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestEmbeddingFuncInner:
    async def test_embed_loads_model_and_encodes(self):
        """embed() should load model and return embeddings when model is None."""
        import numpy as np
        import agent.tools.lightrag_tool as mod
        from agent.tools.lightrag_tool import _get_embedding_func

        old_model = mod._embedding_model
        mod._embedding_model = None

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 1024, [0.2] * 1024])

        try:
            with (
                patch("sentence_transformers.SentenceTransformer", return_value=mock_model),
                patch.dict("sys.modules", {"lightrag": MagicMock(), "lightrag.utils": MagicMock()}),
            ):
                # Patch EmbeddingFunc to just capture the func
                captured_func = {}

                class FakeEmbeddingFunc:
                    def __init__(self, **kwargs):
                        captured_func.update(kwargs)
                        captured_func["func"] = kwargs.get("func")

                with patch("lightrag.utils.EmbeddingFunc", FakeEmbeddingFunc):
                    emb_func = _get_embedding_func()

                # Call the captured embed function
                result = await captured_func["func"](["test text 1", "test text 2"])
                assert result.shape == (2, 1024)
                mock_model.encode.assert_called_once()
                assert mod._embedding_model is mock_model
        finally:
            mod._embedding_model = old_model


# ---------------------------------------------------------------------------
# _get_llm_func
# ---------------------------------------------------------------------------
class TestGetLlmFunc:
    def test_returns_callable(self):
        from agent.tools.lightrag_tool import _get_llm_func
        func = _get_llm_func()
        assert callable(func)


# ---------------------------------------------------------------------------
# _get_llm_func().llm_complete — non-Anthropic path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestLlmCompleteOpenAI:
    async def test_successful_call(self):
        """OpenAI-compatible provider returns content from response."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test LLM response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "test-key",
                "model": "test-model",
            }),
        ):
            result = await llm_complete("Test prompt")

        assert result == "Test LLM response"

    async def test_empty_content_recovers_from_reasoning(self):
        """Empty content falls back to reasoning_content field."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "", "reasoning_content": "Reasoning output here"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="deepseek"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "key",
                "model": "deepseek-r1",
            }),
        ):
            result = await llm_complete("Test prompt")

        assert result == "Reasoning output here"

    async def test_auth_error_wraps_as_llmautherror(self):
        """401/403 responses should raise LLMAuthError."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.config import LLMAuthError

        llm_complete = _get_llm_func()

        mock_request = httpx.Request("POST", "https://api.test.com/v1/chat/completions")
        mock_response_obj = httpx.Response(status_code=401, request=mock_request, text="Unauthorized")
        http_error = httpx.HTTPStatusError("401", request=mock_request, response=mock_response_obj)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(side_effect=http_error)

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "bad-key",
                "model": "test-model",
            }),
            pytest.raises(LLMAuthError),
        ):
            await llm_complete("Test prompt")

    async def test_empty_model_falls_back_to_default(self):
        """Empty model name should fall back to provider default."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "",  # empty
            }),
        ):
            result = await llm_complete("Test prompt")

        assert result == "OK"
        # Verify model was set to default
        call_json = mock_client.post.call_args[1]["json"]
        assert call_json["model"] == "mimo-v2.5-pro"

    async def test_injects_chinese_system_prompt_for_extraction(self):
        """Entity/relationship extraction prompts get Chinese system prompt."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "entities extracted"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "test-model",
            }),
        ):
            await llm_complete("Extract entity and relationship from text")

        call_json = mock_client.post.call_args[1]["json"]
        system_msg = call_json["messages"][0]
        assert system_msg["role"] == "system"
        assert "GMP" in system_msg["content"]

    async def test_history_messages_passed(self):
        """History messages should be included in the request."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        history = [
            {"role": "user", "content": "prev question"},
            {"role": "assistant", "content": "prev answer"},
        ]

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "test-model",
            }),
        ):
            await llm_complete("Follow up", history_messages=history)

        call_json = mock_client.post.call_args[1]["json"]
        messages = call_json["messages"]
        # 2 history + user = 3 (no system prompt since "Follow up" has no entity/relationship)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "prev question"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "prev answer"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "Follow up"


# ---------------------------------------------------------------------------
# _get_llm_func().llm_complete — Anthropic path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestLlmCompleteAnthropic:
    async def test_anthropic_path_success(self):
        """Anthropic provider should use LangChain adapter."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "Anthropic response"
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        mock_llm._model = "claude-sonnet"

        with (
            patch("agent.config.get_default_provider", return_value="anthropic"),
            patch("agent.config.get_llm_with_fallback", return_value=mock_llm),
        ):
            result = await llm_complete("Test prompt", system_prompt="System instruction")

        assert result == "Anthropic response"
        # Verify messages were built correctly
        call_args = mock_llm.ainvoke.call_args[0][0]
        from langchain_core.messages import SystemMessage
        assert any(isinstance(m, SystemMessage) for m in call_args)

    async def test_anthropic_history_messages(self):
        """Anthropic path should convert history messages to LangChain format."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "Response"
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        mock_llm._model = "claude-sonnet"

        history = [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ]

        with (
            patch("agent.config.get_default_provider", return_value="anthropic"),
            patch("agent.config.get_llm_with_fallback", return_value=mock_llm),
        ):
            result = await llm_complete("Follow up", history_messages=history)

        call_args = mock_llm.ainvoke.call_args[0][0]
        from langchain_core.messages import HumanMessage, AIMessage
        assert any(isinstance(m, HumanMessage) for m in call_args)
        assert any(isinstance(m, AIMessage) for m in call_args)

    async def test_anthropic_error_traced(self):
        """Anthropic errors should be traced and re-raised."""
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("API error"))
        mock_llm._model = "claude-sonnet"

        with (
            patch("agent.config.get_default_provider", return_value="anthropic"),
            patch("agent.config.get_llm_with_fallback", return_value=mock_llm),
            pytest.raises(RuntimeError, match="API error"),
        ):
            await llm_complete("Test")


# ---------------------------------------------------------------------------
# _get_llm_func().llm_complete — retry / non-retryable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestLlmCompleteRetry:
    async def test_retryable_error_retries(self):
        """429/5xx errors should trigger retry."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_request = httpx.Request("POST", "https://api.test.com/v1/chat/completions")
        error_resp = httpx.Response(status_code=429, request=mock_request, text="Rate limited")
        http_error = httpx.HTTPStatusError("429", request=mock_request, response=error_resp)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "OK after retry"}}]
        }
        success_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=[http_error, success_response])
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "test-model",
            }),
            patch("agent.tools.lightrag_tool.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await llm_complete("Test")

        assert result == "OK after retry"
        assert mock_client.post.call_count == 2

    async def test_non_retryable_error_raises(self):
        """400 errors should raise immediately without retry."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func

        llm_complete = _get_llm_func()

        mock_request = httpx.Request("POST", "https://api.test.com/v1/chat/completions")
        error_resp = httpx.Response(status_code=400, request=mock_request, text="Bad request")
        http_error = httpx.HTTPStatusError("400", request=mock_request, response=error_resp)

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "test-model",
            }),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await llm_complete("Test")

        assert mock_client.post.call_count == 1  # no retry

    async def test_timeout_retries(self):
        """Timeout errors should trigger retry."""
        from agent.tools.lightrag_tool import _get_llm_func
        import httpx

        llm_complete = _get_llm_func()

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "OK after timeout"}}]
        }
        success_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=[httpx.TimeoutException("timeout"), success_response])
        mock_client.is_closed = False

        with (
            patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm_config", return_value={
                "base_url": "https://api.test.com/v1",
                "api_key": "key",
                "model": "test-model",
            }),
            patch("agent.tools.lightrag_tool.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await llm_complete("Test")

        assert result == "OK after timeout"


# ---------------------------------------------------------------------------
# Trace integration in llm_complete
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestLlmCompleteTrace:
    async def test_trace_recorded_on_success(self):
        """Successful LLM call should record a trace event."""
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm_complete = _get_llm_func()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Traced response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
                patch("agent.config.get_default_provider", return_value="mimo"),
                patch("agent.config.get_llm_config", return_value={
                    "base_url": "https://api.test.com/v1",
                    "api_key": "key",
                    "model": "test-model",
                }),
            ):
                result = await llm_complete("Traced prompt")

            assert result == "Traced response"
            assert len(trace.llm_events) == 1
            event = trace.llm_events[0]
            assert event.success is True
            assert event.provider == "mimo"
            assert event.node == "lightrag"
        finally:
            clear_current_trace()

    async def test_trace_recorded_on_failure(self):
        """Failed LLM call should record a trace event with error."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace
        from agent.config import LLMAuthError

        llm_complete = _get_llm_func()

        mock_request = httpx.Request("POST", "https://api.test.com/v1/chat/completions")
        mock_response_obj = httpx.Response(status_code=401, request=mock_request, text="Unauthorized")
        http_error = httpx.HTTPStatusError("401", request=mock_request, response=mock_response_obj)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock(side_effect=http_error)

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
                patch("agent.config.get_default_provider", return_value="mimo"),
                patch("agent.config.get_llm_config", return_value={
                    "base_url": "https://api.test.com/v1",
                    "api_key": "bad-key",
                    "model": "test-model",
                }),
                pytest.raises(LLMAuthError),
            ):
                await llm_complete("Fail prompt")

            assert len(trace.llm_events) == 1
            event = trace.llm_events[0]
            assert event.success is False
        finally:
            clear_current_trace()

    async def test_anthropic_error_with_trace(self):
        """Anthropic error with active trace should record trace event."""
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm_complete = _get_llm_func()

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Anthropic error"))
        mock_llm._model = "claude-sonnet"

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.config.get_default_provider", return_value="anthropic"),
                patch("agent.config.get_llm_with_fallback", return_value=mock_llm),
                pytest.raises(RuntimeError, match="Anthropic error"),
            ):
                await llm_complete("Test")

            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is False
            assert trace.llm_events[0].error == "Anthropic error"
        finally:
            clear_current_trace()

    async def test_non_retryable_http_error_with_trace(self):
        """Non-retryable HTTP error with trace should record failure event."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm_complete = _get_llm_func()

        mock_request = httpx.Request("POST", "https://api.test.com/v1/chat/completions")
        error_resp = httpx.Response(status_code=400, request=mock_request, text="Bad request")
        http_error = httpx.HTTPStatusError("400", request=mock_request, response=error_resp)

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client.is_closed = False

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
                patch("agent.config.get_default_provider", return_value="mimo"),
                patch("agent.config.get_llm_config", return_value={
                    "base_url": "https://api.test.com/v1",
                    "api_key": "key",
                    "model": "test-model",
                }),
                pytest.raises(httpx.HTTPStatusError),
            ):
                await llm_complete("Test")

            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is False
            assert "HTTP 400" in trace.llm_events[0].error
        finally:
            clear_current_trace()

    async def test_timeout_all_retries_exhausted_with_trace(self):
        """All 3 timeout retries exhausted should record trace and raise."""
        import httpx
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm_complete = _get_llm_func()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.is_closed = False

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.tools.lightrag_tool._get_llm_client", new_callable=AsyncMock, return_value=mock_client),
                patch("agent.config.get_default_provider", return_value="mimo"),
                patch("agent.config.get_llm_config", return_value={
                    "base_url": "https://api.test.com/v1",
                    "api_key": "key",
                    "model": "test-model",
                }),
                patch("agent.tools.lightrag_tool.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises(httpx.TimeoutException),
            ):
                await llm_complete("Test")

            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is False
            assert trace.llm_events[0].retry_count == 2  # last attempt index
        finally:
            clear_current_trace()

    async def test_anthropic_trace_recorded(self):
        """Anthropic path should also record trace events."""
        from agent.tools.lightrag_tool import _get_llm_func
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm_complete = _get_llm_func()

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "Anthropic traced"
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        mock_llm._model = "claude-sonnet"

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)
        try:
            with (
                patch("agent.config.get_default_provider", return_value="anthropic"),
                patch("agent.config.get_llm_with_fallback", return_value=mock_llm),
            ):
                result = await llm_complete("Test")

            assert result == "Anthropic traced"
            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is True
            assert trace.llm_events[0].provider == "anthropic"
        finally:
            clear_current_trace()
