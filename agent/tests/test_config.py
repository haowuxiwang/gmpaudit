"""Tests for agent/config.py — LLM configuration, retry logic, error detection."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.config as config_mod
from agent.config import (
    LLMAuthError,
    MODEL_ENDPOINTS,
    _get_anthropic_llm,
    _is_auth_error,
    _is_reasoning_model,
    _is_retryable_error,
    _validate_model_name,
    call_llm_with_retry,
    clear_llm_cache,
    get_default_provider,
    get_llm,
    get_llm_config,
    get_llm_with_fallback,
)


# ---------------------------------------------------------------------------
# LLMAuthError
# ---------------------------------------------------------------------------
class TestLLMAuthError:
    def test_attributes(self):
        err = LLMAuthError("mimo", "401 Unauthorized")
        assert err.provider == "mimo"
        assert err.original_error == "401 Unauthorized"
        assert "mimo" in err.user_message

    def test_is_exception(self):
        err = LLMAuthError("deepseek")
        assert isinstance(err, Exception)

    def test_user_message_format(self):
        err = LLMAuthError("qwen")
        assert "API Key" in err.user_message
        assert "qwen" in err.user_message


# ---------------------------------------------------------------------------
# clear_llm_cache
# ---------------------------------------------------------------------------
class TestClearLlmCache:
    def setup_method(self):
        config_mod._llm_cache.clear()

    def test_clear_all(self):
        config_mod._llm_cache[("mimo", "model", 0.3, 4000)] = "instance"
        config_mod._llm_cache[("deepseek", "model", 0.3, 4000)] = "instance2"
        clear_llm_cache()
        assert len(config_mod._llm_cache) == 0

    def test_clear_specific_provider(self):
        config_mod._llm_cache[("mimo", "model", 0.3, 4000)] = "instance"
        config_mod._llm_cache[("deepseek", "model", 0.3, 4000)] = "instance2"
        clear_llm_cache("mimo")
        assert len(config_mod._llm_cache) == 1
        assert ("deepseek", "model", 0.3, 4000) in config_mod._llm_cache

    def test_clear_legacy_string_keys(self):
        """Legacy string keys starting with provider name should also be cleared."""
        config_mod._llm_cache["mimo_legacy"] = "old_instance"
        config_mod._llm_cache[("deepseek", "m", 0.3, 4000)] = "new_instance"
        clear_llm_cache("mimo")
        assert len(config_mod._llm_cache) == 1


# ---------------------------------------------------------------------------
# get_default_provider
# ---------------------------------------------------------------------------
class TestGetDefaultProvider:
    def test_default_is_mimo(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_LLM_PROVIDER", None)
            assert get_default_provider() == "mimo"

    def test_reads_from_env(self):
        with patch.dict(os.environ, {"AGENT_LLM_PROVIDER": "deepseek"}):
            assert get_default_provider() == "deepseek"

    def test_env_changes_picked_up(self):
        """Each call reads from env (no caching)."""
        with patch.dict(os.environ, {"AGENT_LLM_PROVIDER": "qwen"}):
            assert get_default_provider() == "qwen"
        with patch.dict(os.environ, {"AGENT_LLM_PROVIDER": "glm"}):
            assert get_default_provider() == "glm"


# ---------------------------------------------------------------------------
# get_llm_config
# ---------------------------------------------------------------------------
class TestGetLlmConfig:
    def test_returns_dict_keys(self):
        config = get_llm_config("mimo")
        assert "base_url" in config
        assert "api_key" in config
        assert "model" in config

    def test_uses_endpoint_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("MIMO_API_KEY", "MIMO_BASE_URL", "MIMO_MODEL"):
                os.environ.pop(key, None)
            config = get_llm_config("mimo")
            assert config["base_url"] == MODEL_ENDPOINTS["mimo"]["base_url"]
            assert config["model"] == MODEL_ENDPOINTS["mimo"]["default_model"]

    def test_env_overrides(self):
        with patch.dict(os.environ, {
            "MIMO_API_KEY": "custom-key",
            "MIMO_BASE_URL": "https://custom.url/v1",
            "MIMO_MODEL": "custom-model",
        }):
            config = get_llm_config("mimo")
            assert config["api_key"] == "custom-key"
            assert config["base_url"] == "https://custom.url/v1"
            assert config["model"] == "custom-model"

    def test_unknown_provider(self):
        config = get_llm_config("unknown_provider")
        assert config["base_url"] == ""
        assert config["api_key"] == ""

    def test_uses_default_provider_when_none(self):
        with patch("agent.config.get_default_provider", return_value="deepseek"), \
             patch.dict(os.environ, {"DEEPSEEK_BASE_URL": MODEL_ENDPOINTS["deepseek"]["base_url"], "DEEPSEEK_API_KEY": "test-key"}, clear=False):
            config = get_llm_config(None)
            assert config["base_url"] == MODEL_ENDPOINTS["deepseek"]["base_url"]


# ---------------------------------------------------------------------------
# _validate_model_name
# ---------------------------------------------------------------------------
class TestValidateModelName:
    def test_slash_in_non_slash_provider_warns(self):
        """Model with '/' in non-slash provider should warn."""
        with patch("agent.config.logger") as mock_logger:
            _validate_model_name("deepseek", "org/model")
            mock_logger.warning.assert_called()

    def test_no_slash_in_slash_provider_warns(self):
        """Model without '/' in slash provider should warn."""
        with patch("agent.config.logger") as mock_logger:
            _validate_model_name("siliconflow", "simple-model")
            mock_logger.warning.assert_called()

    def test_correct_format_no_warning(self):
        """Correct format should not warn."""
        with patch("agent.config.logger") as mock_logger:
            _validate_model_name("deepseek", "deepseek-chat")
            mock_logger.warning.assert_not_called()

    def test_slash_provider_with_slash_no_warning(self):
        """Slash provider with slash model should not warn."""
        with patch("agent.config.logger") as mock_logger:
            _validate_model_name("siliconflow", "deepseek-ai/DeepSeek-V3.2")
            mock_logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# _is_reasoning_model
# ---------------------------------------------------------------------------
class TestIsReasoningModel:
    def test_deepseek_r1(self):
        assert _is_reasoning_model("deepseek-r1") is True

    def test_nex_n2(self):
        assert _is_reasoning_model("nex-n2-pro") is True

    def test_o1_model(self):
        assert _is_reasoning_model("o1-preview") is True

    def test_o3_model(self):
        assert _is_reasoning_model("o3-mini") is True

    def test_thinking_model(self):
        assert _is_reasoning_model("thinking-model") is True

    def test_reason_model(self):
        assert _is_reasoning_model("reason-plus") is True

    def test_regular_model(self):
        assert _is_reasoning_model("gpt-4o") is False

    def test_deepseek_chat(self):
        assert _is_reasoning_model("deepseek-chat") is False

    def test_non_string(self):
        assert _is_reasoning_model(None) is False
        assert _is_reasoning_model(123) is False


# ---------------------------------------------------------------------------
# get_llm
# ---------------------------------------------------------------------------
class TestGetLlm:
    def setup_method(self):
        config_mod._llm_cache.clear()

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_llm("nonexistent_provider")

    def test_missing_api_key_raises(self):
        with (
            patch.dict(os.environ, {"MIMO_API_KEY": ""}, clear=False),
            pytest.raises(ValueError, match="Missing or placeholder API key"),
        ):
            get_llm("mimo")

    def test_placeholder_api_key_raises(self):
        with (
            patch.dict(os.environ, {"MIMO_API_KEY": "your_key_here"}, clear=False),
            pytest.raises(ValueError, match="Missing or placeholder API key"),
        ):
            get_llm("mimo")

    def test_cache_hit(self):
        """Same params should return cached instance."""
        mock_llm = MagicMock()
        mock_llm._provider = "mimo"
        mock_llm._model = "test"
        config_mod._llm_cache[("mimo", "mimo-v2.5-pro", 0.3, 4000)] = mock_llm
        result = get_llm("mimo", model="mimo-v2.5-pro")
        assert result is mock_llm

    def test_creates_new_instance(self):
        """Should create a ChatOpenAI instance with correct params."""
        with (
            patch.dict(os.environ, {
                "MIMO_API_KEY": "test-key-123",
                "MIMO_BASE_URL": "https://api.test.com/v1",
            }, clear=False),
            patch("langchain_openai.ChatOpenAI") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = get_llm("mimo", model="test-model", temperature=0.5, max_tokens=8000)

            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 8000
            assert call_kwargs["api_key"] == "test-key-123"

    def test_cache_eviction_at_50(self):
        """Cache should evict oldest entry when full (50 entries)."""
        # Fill cache to 50
        for i in range(50):
            config_mod._llm_cache[("test", f"model-{i}", 0.3, 4000)] = f"instance-{i}"
        assert len(config_mod._llm_cache) == 50

        with (
            patch.dict(os.environ, {
                "TEST_API_KEY": "key",
                "TEST_BASE_URL": "https://test.com/v1",
            }, clear=False),
            patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
            patch("agent.config.MODEL_ENDPOINTS", {"test": {"base_url": "https://test.com/v1", "default_model": "default"}}),
        ):
            get_llm("test", model="new-model")

        assert len(config_mod._llm_cache) == 50  # still at cap

    def test_placeholder_model_uses_default(self):
        """Model starting with 'your_' should fall back to provider default."""
        with (
            patch.dict(os.environ, {
                "MIMO_API_KEY": "test-key",
            }, clear=False),
            patch("langchain_openai.ChatOpenAI") as mock_cls,
        ):
            mock_cls.return_value = MagicMock()
            get_llm("mimo", model="your_model_here")
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["model"] == MODEL_ENDPOINTS["mimo"]["default_model"]

    def test_reasoning_model_boosts_max_tokens(self):
        """Reasoning models should auto-boost max_tokens."""
        with (
            patch.dict(os.environ, {
                "DEEPSEEK_API_KEY": "test-key",
            }, clear=False),
            patch("langchain_openai.ChatOpenAI") as mock_cls,
        ):
            mock_cls.return_value = MagicMock()
            get_llm("deepseek", model="deepseek-r1", max_tokens=4000)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["max_tokens"] == 16000  # boosted

    def test_provider_none_uses_default(self):
        """get_llm(provider=None) should use get_default_provider()."""
        mock_llm = MagicMock()
        with (
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch.dict(os.environ, {"MIMO_API_KEY": "test-key"}, clear=False),
            patch("langchain_openai.ChatOpenAI", return_value=MagicMock()),
        ):
            result = get_llm(None, model="test-model")
            assert result is not None

    def test_anthropic_provider_route(self):
        """get_llm('anthropic') should route to _get_anthropic_llm."""
        mock_llm = MagicMock()
        with patch("agent.config._get_anthropic_llm", return_value=mock_llm) as mock_anth:
            result = get_llm("anthropic", model="claude-sonnet", temperature=0.5, max_tokens=8000)
            mock_anth.assert_called_once_with("claude-sonnet", 0.5, 8000)
            assert result is mock_llm

    def test_placeholder_base_url_falls_back(self):
        """Base URL starting with 'your_' should fall back to endpoint default."""
        with (
            patch.dict(os.environ, {
                "MIMO_API_KEY": "test-key",
                "MIMO_BASE_URL": "your_base_url_here",
            }, clear=False),
            patch("langchain_openai.ChatOpenAI") as mock_cls,
        ):
            mock_cls.return_value = MagicMock()
            get_llm("mimo", model="test-model")
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["base_url"] == MODEL_ENDPOINTS["mimo"]["base_url"]


# ---------------------------------------------------------------------------
# _get_anthropic_llm
# ---------------------------------------------------------------------------
class TestGetAnthropicLlm:
    def setup_method(self):
        config_mod._llm_cache.clear()

    def test_missing_api_key_raises(self):
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False),
            pytest.raises(ValueError, match="Missing or placeholder API key"),
        ):
            _get_anthropic_llm(None, 0.3, 4000)

    def test_placeholder_key_raises(self):
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "your_key"}, clear=False),
            pytest.raises(ValueError, match="Missing or placeholder API key"),
        ):
            _get_anthropic_llm(None, 0.3, 4000)

    def test_import_error_raises(self):
        """Missing langchain-anthropic should raise ImportError."""
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key"}, clear=False),
            patch.dict("sys.modules", {"langchain_anthropic": None}),
            pytest.raises(ImportError, match="langchain-anthropic"),
        ):
            _get_anthropic_llm(None, 0.3, 4000)

    def test_creates_instance(self):
        """Should create ChatAnthropic with correct params."""
        mock_anthropic = MagicMock()
        mock_cls = MagicMock()
        mock_anthropic.ChatAnthropic = mock_cls
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key"}, clear=False),
            patch.dict("sys.modules", {"langchain_anthropic": mock_anthropic}),
        ):
            result = _get_anthropic_llm("claude-sonnet-4-20250514", 0.5, 8000)

            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 8000
            assert result._provider == "anthropic"

    def test_uses_default_model(self):
        """None model should use ANTHROPIC_DEFAULT_MODEL."""
        mock_anthropic = MagicMock()
        mock_cls = MagicMock()
        mock_anthropic.ChatAnthropic = mock_cls

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key", "ANTHROPIC_MODEL": ""}, clear=False),
            patch.dict("sys.modules", {"langchain_anthropic": mock_anthropic}),
        ):
            mock_cls.return_value = MagicMock()
            _get_anthropic_llm(None, 0.3, 4000)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    def test_cache_hit(self):
        """Same params should return cached instance."""
        mock_instance = MagicMock()
        config_mod._llm_cache[("anthropic", "claude-sonnet-4-20250514", 0.3, 4000)] = mock_instance
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-sonnet-4-20250514"}, clear=False):
            result = _get_anthropic_llm(None, 0.3, 4000)
        assert result is mock_instance

    def test_cache_eviction_at_50(self):
        """Anthropic cache should evict oldest entry when full (50 entries)."""
        config_mod._llm_cache.clear()
        # Fill cache to 50
        for i in range(50):
            config_mod._llm_cache[("anthropic", f"model-{i}", 0.3, 4000)] = f"instance-{i}"
        assert len(config_mod._llm_cache) == 50

        mock_anthropic = MagicMock()
        mock_cls = MagicMock()
        mock_anthropic.ChatAnthropic = mock_cls
        mock_cls.return_value = MagicMock()

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key"}, clear=False),
            patch.dict("sys.modules", {"langchain_anthropic": mock_anthropic}),
        ):
            _get_anthropic_llm("new-model", 0.3, 4000)

        assert len(config_mod._llm_cache) == 50  # still at cap


# ---------------------------------------------------------------------------
# get_llm_with_fallback
# ---------------------------------------------------------------------------
class TestGetLlmWithFallback:
    def setup_method(self):
        config_mod._llm_cache.clear()

    def test_first_provider_succeeds(self):
        """Default provider succeeds — returns immediately."""
        mock_llm = MagicMock()
        with patch("agent.config.get_llm", return_value=mock_llm):
            result = get_llm_with_fallback()
        assert result is mock_llm

    def test_fallback_to_next_provider(self):
        """Default fails, next provider succeeds."""
        call_count = 0

        def mock_get_llm(provider, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if provider == "mimo":
                raise ValueError("No API key")
            return MagicMock()

        with (
            patch("agent.config.get_default_provider", return_value="mimo"),
            patch("agent.config.get_llm", side_effect=mock_get_llm),
        ):
            result = get_llm_with_fallback()
        assert result is not None

    def test_all_providers_fail_raises(self):
        """All providers fail — raises ValueError."""
        with (
            patch("agent.config.get_llm", side_effect=ValueError("No key")),
            pytest.raises(ValueError, match="No provider with valid API key"),
        ):
            get_llm_with_fallback()


# ---------------------------------------------------------------------------
# _is_retryable_error
# ---------------------------------------------------------------------------
class TestIsRetryableError:
    def test_timeout_error(self):
        assert _is_retryable_error(asyncio.TimeoutError()) is True

    def test_rate_limit(self):
        assert _is_retryable_error(Exception("429 rate limit exceeded")) is True

    def test_server_error_500(self):
        assert _is_retryable_error(Exception("HTTP 500 Internal Server Error")) is True

    def test_server_error_502(self):
        assert _is_retryable_error(Exception("502 Bad Gateway")) is True

    def test_server_error_503(self):
        assert _is_retryable_error(Exception("503 Service Unavailable")) is True

    def test_connection_error(self):
        assert _is_retryable_error(Exception("Connection refused")) is True

    def test_overloaded(self):
        assert _is_retryable_error(Exception("server overloaded")) is True

    def test_auth_error_not_retryable(self):
        assert _is_retryable_error(Exception("401 Unauthorized")) is False

    def test_403_not_retryable(self):
        assert _is_retryable_error(Exception("403 Forbidden")) is False

    def test_bad_request_not_retryable(self):
        assert _is_retryable_error(Exception("400 Bad Request")) is False

    def test_invalid_api_key_not_retryable(self):
        assert _is_retryable_error(Exception("Invalid API Key")) is False

    def test_unknown_error_not_retryable(self):
        """Unknown errors are not retryable (only explicit patterns)."""
        assert _is_retryable_error(Exception("Something weird")) is False

    def test_httpx_timeout(self):
        """httpx timeout errors should be retryable."""
        try:
            import httpx
            assert _is_retryable_error(httpx.TimeoutException("timeout")) is True
            assert _is_retryable_error(httpx.ConnectTimeout("connect timeout")) is True
            assert _is_retryable_error(httpx.ReadTimeout("read timeout")) is True
        except ImportError:
            pytest.skip("httpx not installed")

    def test_httpx_not_importable_fallback(self):
        """When httpx is not importable, should fall through gracefully."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("no httpx")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            # Should not raise, should fall through to string-based detection
            assert _is_retryable_error(asyncio.TimeoutError()) is True
            assert _is_retryable_error(Exception("429 rate limit")) is True
            assert _is_retryable_error(Exception("unknown")) is False


# ---------------------------------------------------------------------------
# _is_auth_error
# ---------------------------------------------------------------------------
class TestIsAuthError:
    def test_invalid_api_key(self):
        assert _is_auth_error(Exception("Invalid API Key provided")) is True

    def test_invalid_key(self):
        assert _is_auth_error(Exception("invalid_key error")) is True

    def test_unauthorized(self):
        assert _is_auth_error(Exception("Unauthorized access")) is True

    def test_error_code_401(self):
        assert _is_auth_error(Exception("error code: 401")) is True

    def test_status_code_403(self):
        assert _is_auth_error(Exception("status_code: 403")) is True

    def test_http_401_with_auth(self):
        assert _is_auth_error(Exception("HTTP 401 authentication failed")) is True

    def test_401_alone_not_enough(self):
        """Bare '401' without context should not match."""
        # The regex requires auth context for bare 401
        assert _is_auth_error(Exception("model 401b parameters")) is False

    def test_not_auth_error(self):
        assert _is_auth_error(Exception("500 Internal Server Error")) is False

    def test_rate_limit_not_auth(self):
        assert _is_auth_error(Exception("429 rate limit")) is False


# ---------------------------------------------------------------------------
# call_llm_with_retry — additional coverage
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestCallLlmWithRetryExtended:
    async def test_auth_error_wraps_as_llmautherror(self):
        """Auth errors should be wrapped as LLMAuthError."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("Invalid API Key"))
        llm._provider = "mimo"
        llm._model = "test-model"

        with pytest.raises(LLMAuthError) as exc_info:
            await call_llm_with_retry(llm, "test", node="test", max_retries=2, retry_delay=0.01)
        assert exc_info.value.provider == "mimo"

    async def test_non_retryable_error_raises_immediately(self):
        """Non-retryable errors should raise without retrying."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=ValueError("Bad request"))
        llm._provider = "test"
        llm._model = "test"

        with pytest.raises(ValueError, match="Bad request"):
            await call_llm_with_retry(llm, "test", node="test", max_retries=3, retry_delay=0.01)

        assert llm.ainvoke.call_count == 1  # no retry

    async def test_reasoning_model_content_recovery(self):
        """Reasoning model output in reasoning_content should be recovered."""
        llm = MagicMock()
        response = MagicMock()
        response.content = ""
        response.additional_kwargs = {"reasoning_content": "Recovered reasoning output"}
        llm.ainvoke = AsyncMock(return_value=response)
        llm._provider = "deepseek"
        llm._model = "deepseek-r1"

        result = await call_llm_with_retry(llm, "test", node="test")
        assert result.content == "Recovered reasoning output"

    async def test_trace_recorded_on_success(self):
        """Successful call should record trace event."""
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm = MagicMock()
        response = MagicMock()
        response.content = "OK"
        response.additional_kwargs = {}
        llm.ainvoke = AsyncMock(return_value=response)
        llm._provider = "test"
        llm._model = "test"

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            await call_llm_with_retry(llm, "prompt", node="test_node")
            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is True
            assert trace.llm_events[0].node == "test_node"
        finally:
            clear_current_trace()

    async def test_trace_recorded_on_auth_error(self):
        """Auth error should also record trace event."""
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("Unauthorized"))
        llm._provider = "mimo"
        llm._model = "test"

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            with pytest.raises(LLMAuthError):
                await call_llm_with_retry(llm, "prompt", node="test_node")
            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is False
        finally:
            clear_current_trace()

    async def test_trace_recorded_on_max_retries_exceeded(self):
        """Max retries exceeded should record trace event."""
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())
        llm._provider = "test"
        llm._model = "test"

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            with (
                patch("agent.config.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises(asyncio.TimeoutError),
            ):
                await call_llm_with_retry(llm, "prompt", node="test", max_retries=1, retry_delay=0.01)
            assert len(trace.llm_events) == 1
            assert trace.llm_events[0].success is False
        finally:
            clear_current_trace()


# ---------------------------------------------------------------------------
# MODEL_ENDPOINTS completeness
# ---------------------------------------------------------------------------
class TestModelEndpoints:
    def test_all_providers_present(self):
        expected = {"deepseek", "qwen", "glm", "siliconflow", "openai", "openrouter", "mimo"}
        assert expected == set(MODEL_ENDPOINTS.keys())

    def test_each_has_base_url_and_default_model(self):
        for provider, config in MODEL_ENDPOINTS.items():
            assert "base_url" in config, f"{provider} missing base_url"
            assert "default_model" in config, f"{provider} missing default_model"
            assert config["base_url"].startswith("https://"), f"{provider} base_url not HTTPS"
