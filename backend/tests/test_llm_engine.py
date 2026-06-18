from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_engine import (
    PROVIDER_DEFAULTS,
    AnthropicAdapter,
    LLMEngine,
    LLMError,
    LLMResponse,
    OpenAICompatibleAdapter,
    _check_response,
)


@pytest.fixture(autouse=True)
def _mock_httpx_client():
    """Prevent real httpx.AsyncClient creation (hangs on SSL in CI)."""
    with patch("httpx.AsyncClient"):
        yield


def test_llm_response_creation():
    response = LLMResponse(
        content="测试内容",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        finish_reason="stop",
    )
    assert response.content == "测试内容"
    assert response.model == "test-model"
    assert response.finish_reason == "stop"
    assert response.usage["prompt_tokens"] == 10


def test_llm_error_attributes():
    err = LLMError("test error", status_code=429, response_body="rate limited")
    assert str(err) == "test error"
    assert err.status_code == 429
    assert err.response_body == "rate limited"


def test_llm_error_defaults():
    err = LLMError("test")
    assert err.status_code == 0
    assert err.response_body == ""


def test_check_response_raises_on_non_200():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    with pytest.raises(LLMError) as exc_info:
        _check_response(mock_response)
    assert exc_info.value.status_code == 500


def test_check_response_passes_on_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    _check_response(mock_response)  # Should not raise


def test_provider_defaults_structure():
    for _name, defaults in PROVIDER_DEFAULTS.items():
        assert "base_url" in defaults
        assert "model" in defaults
        assert defaults["base_url"].startswith("https://")


def test_llm_engine_initialization():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    assert isinstance(engine.adapters, dict)


@pytest.mark.asyncio
async def test_analyze_without_adapter():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    with pytest.raises(ValueError, match="不支持的模型"):
        await engine.analyze("测试文档", "测试提示", model="nonexistent")


@pytest.mark.asyncio
async def test_generate_report_without_adapter():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    findings = [{"severity": "high", "title": "测试发现", "description": "测试描述"}]
    with pytest.raises(ValueError, match="不支持的模型"):
        await engine.generate_report(findings, model="nonexistent")


def test_get_available_providers_empty():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    # No API keys configured, so no adapters
    providers = engine.get_available_providers()
    assert isinstance(providers, list)


def test_openai_adapter_init():
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
        name="test",
    )
    assert adapter.api_key == "test-key"
    assert adapter.base_url == "https://api.example.com/v1"
    assert adapter.model == "test-model"
    assert adapter.name == "test"


def test_openai_adapter_strips_trailing_slash():
    adapter = OpenAICompatibleAdapter(
        api_key="key",
        base_url="https://api.example.com/v1/",
        model="m",
    )
    assert adapter.base_url == "https://api.example.com/v1"


def test_anthropic_adapter_init():
    adapter = AnthropicAdapter(api_key="test-key")
    assert adapter.api_key == "test-key"
    assert adapter.base_url == "https://api.anthropic.com"


def test_anthropic_extract_system():
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
    ]
    system, filtered = AnthropicAdapter._extract_system(messages)
    assert system == "You are helpful"
    assert len(filtered) == 1
    assert filtered[0]["role"] == "user"


def test_anthropic_extract_system_no_system():
    messages = [{"role": "user", "content": "Hello"}]
    system, filtered = AnthropicAdapter._extract_system(messages)
    assert system == ""
    assert len(filtered) == 1


@pytest.mark.asyncio
async def test_openai_adapter_chat_success():
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    with patch.object(adapter._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await adapter.chat([{"role": "user", "content": "Hi"}])
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello"
        assert result.model == "test-model"


@pytest.mark.asyncio
async def test_openai_adapter_chat_error():
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"

    with patch.object(adapter._client, "post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(LLMError) as exc_info:
            await adapter.chat([{"role": "user", "content": "Hi"}])
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_engine_analyze_success():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(
        return_value=LLMResponse(
            content="分析结果",
            model="test",
            usage={},
            finish_reason="stop",
        )
    )
    engine.adapters["test"] = mock_adapter

    result = await engine.analyze("文档内容", "分析提示", model="test")
    assert result.content == "分析结果"


@pytest.mark.asyncio
async def test_engine_generate_report_success():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(
        return_value=LLMResponse(
            content="# Report",
            model="test",
            usage={},
            finish_reason="stop",
        )
    )
    engine.adapters["test"] = mock_adapter

    findings = [{"severity": "high", "title": "Finding 1", "description": "Desc"}]
    result = await engine.generate_report(findings, model="test")
    assert result == "# Report"


def test_engine_get_available_providers():
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    # All 8 providers from PROVIDER_REGISTRY should be returned
    providers = engine.get_available_providers()
    assert len(providers) == 8
    # Each provider should have required fields
    for p in providers:
        assert "name" in p
        assert "model" in p
        assert "available" in p
        assert isinstance(p["available"], bool)


# === New tests for coverage gaps ===


@pytest.mark.asyncio
async def test_openai_adapter_chat_empty_choices():
    """OpenAI adapter raises ValueError when choices is empty."""
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
        name="test",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [],
        "model": "test-model",
        "usage": {},
    }

    with patch.object(adapter._client, "post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(ValueError, match="empty choices"):
            await adapter.chat([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_openai_adapter_chat_stream():
    """Test OpenAI chat_stream yields content from SSE chunks."""
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    # Mock the stream context manager
    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
        yield 'data: {"choices":[{"delta":{"content":" World"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["Hello", " World"]


@pytest.mark.asyncio
async def test_openai_adapter_chat_stream_bad_json():
    """Test OpenAI chat_stream skips malformed JSON lines."""
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield "data: {bad json"
        yield 'data: {"choices":[{"delta":{"content":"OK"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["OK"]


@pytest.mark.asyncio
async def test_openai_adapter_chat_stream_no_content_delta():
    """Test OpenAI chat_stream skips chunks without content in delta."""
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}'
        yield 'data: {"choices":[{"delta":{"content":"text"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["text"]


@pytest.mark.asyncio
async def test_openai_adapter_chat_stream_empty_choices():
    """Test OpenAI chat_stream skips chunks with empty choices."""
    adapter = OpenAICompatibleAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield 'data: {"choices":[]}'
        yield 'data: {"choices":[{"delta":{"content":"text"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["text"]


@pytest.mark.asyncio
async def test_anthropic_adapter_chat_stream():
    """Test Anthropic chat_stream yields content from SSE chunks."""
    adapter = AnthropicAdapter(api_key="test-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield 'data: {"type":"content_block_delta","delta":{"text":"Hello"}}'
        yield 'data: {"type":"content_block_delta","delta":{"text":" World"}}'

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["Hello", " World"]


@pytest.mark.asyncio
async def test_anthropic_adapter_chat_stream_bad_json():
    """Test Anthropic chat_stream skips malformed JSON."""
    adapter = AnthropicAdapter(api_key="test-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield "data: {not valid json"
        yield 'data: {"type":"content_block_delta","delta":{"text":"OK"}}'

    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["OK"]


@pytest.mark.asyncio
async def test_anthropic_adapter_chat_success():
    """Test Anthropic chat returns LLMResponse correctly."""
    adapter = AnthropicAdapter(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": "Anthropic response"}],
        "model": "claude-3-sonnet",
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "stop_reason": "end_turn",
    }

    with patch.object(adapter._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await adapter.chat([{"role": "user", "content": "Hi"}])
        assert isinstance(result, LLMResponse)
        assert result.content == "Anthropic response"
        assert result.model == "claude-3-sonnet"
        assert result.finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_adapter_chat_with_system():
    """Test Anthropic chat extracts system message."""
    adapter = AnthropicAdapter(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": "response"}],
        "model": "claude-3-sonnet",
        "usage": {},
        "stop_reason": "end_turn",
    }

    with patch.object(adapter._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await adapter.chat([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ])
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["system"] == "You are helpful"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_reload_provider_openai():
    """Test reload_provider creates a new OpenAI adapter."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    engine.adapters.clear()

    old_adapter = AsyncMock()
    old_adapter.close = AsyncMock()
    engine.adapters["deepseek"] = old_adapter

    with patch("httpx.AsyncClient"):
        await engine.reload_provider("deepseek", api_key="new-key", base_url="https://new.example.com/v1", model="new-model")
    assert "deepseek" in engine.adapters
    adapter = engine.adapters["deepseek"]
    assert isinstance(adapter, OpenAICompatibleAdapter)
    assert adapter.api_key == "new-key"
    assert adapter.model == "new-model"


@pytest.mark.asyncio
async def test_reload_provider_remove_adapter():
    """Test reload_provider with empty api_key removes the adapter."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    old_adapter = AsyncMock()
    old_adapter.close = AsyncMock()
    engine.adapters["deepseek"] = old_adapter

    await engine.reload_provider("deepseek", api_key="")
    assert "deepseek" not in engine.adapters


@pytest.mark.asyncio
async def test_reload_provider_anthropic():
    """Test reload_provider creates AnthropicAdapter for anthropic."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    engine.adapters.clear()

    with patch("httpx.AsyncClient"):
        await engine.reload_provider("anthropic", api_key="new-key", model="claude-3-opus")
    assert "anthropic" in engine.adapters
    adapter = engine.adapters["anthropic"]
    assert isinstance(adapter, AnthropicAdapter)
    assert adapter.api_key == "new-key"


@pytest.mark.asyncio
async def test_reload_provider_anthropic_remove():
    """Test reload_provider with empty api_key removes anthropic adapter."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    old_adapter = AsyncMock()
    old_adapter.close = AsyncMock()
    engine.adapters["anthropic"] = old_adapter

    await engine.reload_provider("anthropic", api_key="")
    assert "anthropic" not in engine.adapters


@pytest.mark.asyncio
async def test_reload_provider_placeholder_url():
    """Test reload_provider skips placeholder URLs."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    # Clear any adapters created by _init_adapters to avoid close() issues
    engine.adapters.clear()

    with patch("httpx.AsyncClient"):
        await engine.reload_provider("deepseek", api_key="key", base_url="your_url_here", model="your_model_here")
    adapter = engine.adapters["deepseek"]
    # Should fall back to defaults
    assert not adapter.base_url.startswith("your_")


@pytest.mark.asyncio
async def test_reload_provider_closes_old_adapter():
    """Test reload_provider closes old adapter before replacing."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    engine.adapters.clear()

    old_adapter = AsyncMock()
    old_adapter.close = AsyncMock()
    engine.adapters["deepseek"] = old_adapter

    with patch("httpx.AsyncClient"):
        await engine.reload_provider("deepseek", api_key="new-key")
    old_adapter.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_engine_close():
    """Test LLMEngine.close() closes all adapters."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    adapter1 = AsyncMock()
    adapter1.close = AsyncMock()
    adapter2 = AsyncMock()
    adapter2.close = AsyncMock()
    engine.adapters = {"a": adapter1, "b": adapter2}

    await engine.close()
    adapter1.close.assert_awaited_once()
    adapter2.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_engine_close_handles_errors():
    """Test LLMEngine.close() continues even if one adapter close fails."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    adapter1 = AsyncMock()
    adapter1.close = AsyncMock(side_effect=Exception("close error"))
    adapter2 = AsyncMock()
    adapter2.close = AsyncMock()
    engine.adapters = {"a": adapter1, "b": adapter2}

    await engine.close()  # Should not raise
    adapter2.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_engine_analyze_llm_error():
    """Test engine.analyze propagates LLMError."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    engine.adapters.clear()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(side_effect=LLMError("API error", status_code=500))
    engine.adapters["test"] = mock_adapter

    with pytest.raises(LLMError, match="API error"):
        await engine.analyze("doc", "prompt", model="test")


@pytest.mark.asyncio
async def test_engine_generate_report_llm_error():
    """Test engine.generate_report propagates LLMError."""
    with patch("httpx.AsyncClient"):
        engine = LLMEngine()
    engine.adapters.clear()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(side_effect=LLMError("API error", status_code=429))
    engine.adapters["test"] = mock_adapter

    with pytest.raises(LLMError):
        await engine.generate_report([{"severity": "high", "title": "t", "description": "d"}], model="test")


@pytest.mark.asyncio
async def test_openai_adapter_close():
    """Test OpenAICompatibleAdapter.close() closes httpx client."""
    with patch("httpx.AsyncClient"):
        adapter = OpenAICompatibleAdapter(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="test-model",
        )
    with patch.object(adapter._client, "aclose", new_callable=AsyncMock) as mock_close:
        await adapter.close()
        mock_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_anthropic_adapter_close():
    """Test AnthropicAdapter.close() closes httpx client."""
    with patch("httpx.AsyncClient"):
        adapter = AnthropicAdapter(api_key="test-key")
    with patch.object(adapter._client, "aclose", new_callable=AsyncMock) as mock_close:
        await adapter.close()
        mock_close.assert_awaited_once()


def test_get_llm_engine_singleton():
    """Test get_llm_engine returns a singleton."""
    import app.services.llm_engine as module
    old = module.llm_engine
    try:
        module.llm_engine = None
        with patch("httpx.AsyncClient"):
            e1 = module.get_llm_engine()
            e2 = module.get_llm_engine()
            assert e1 is e2
    finally:
        module.llm_engine = old
