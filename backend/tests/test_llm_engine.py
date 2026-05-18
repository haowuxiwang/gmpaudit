import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_engine import (
    LLMEngine, LLMResponse, LLMError,
    OpenAICompatibleAdapter, AnthropicAdapter,
    _check_response, PROVIDER_DEFAULTS,
)


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
    for name, defaults in PROVIDER_DEFAULTS.items():
        assert "base_url" in defaults
        assert "model" in defaults
        assert defaults["base_url"].startswith("https://")


def test_llm_engine_initialization():
    engine = LLMEngine()
    assert isinstance(engine.adapters, dict)


@pytest.mark.asyncio
async def test_analyze_without_adapter():
    engine = LLMEngine()
    with pytest.raises(ValueError, match="不支持的模型"):
        await engine.analyze("测试文档", "测试提示", model="nonexistent")


@pytest.mark.asyncio
async def test_generate_report_without_adapter():
    engine = LLMEngine()
    findings = [{"severity": "high", "title": "测试发现", "description": "测试描述"}]
    with pytest.raises(ValueError, match="不支持的模型"):
        await engine.generate_report(findings, model="nonexistent")


def test_get_available_providers_empty():
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

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
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

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(LLMError) as exc_info:
            await adapter.chat([{"role": "user", "content": "Hi"}])
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_engine_analyze_success():
    engine = LLMEngine()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=LLMResponse(
        content="分析结果",
        model="test",
        usage={},
        finish_reason="stop",
    ))
    engine.adapters["test"] = mock_adapter

    result = await engine.analyze("文档内容", "分析提示", model="test")
    assert result.content == "分析结果"


@pytest.mark.asyncio
async def test_engine_generate_report_success():
    engine = LLMEngine()
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=LLMResponse(
        content="# Report",
        model="test",
        usage={},
        finish_reason="stop",
    ))
    engine.adapters["test"] = mock_adapter

    findings = [{"severity": "high", "title": "Finding 1", "description": "Desc"}]
    result = await engine.generate_report(findings, model="test")
    assert result == "# Report"


def test_engine_get_available_providers():
    engine = LLMEngine()
    # Clear existing adapters and add a mock one
    engine.adapters.clear()
    mock_adapter = MagicMock()
    mock_adapter.model = "test-model"
    engine.adapters["test_provider"] = mock_adapter

    providers = engine.get_available_providers()
    assert len(providers) == 1
    assert providers[0]["name"] == "test_provider"
    assert providers[0]["model"] == "test-model"
    assert providers[0]["available"] is True
