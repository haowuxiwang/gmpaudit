"""Tests for LLM retry logic and jitter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.config import call_llm_with_retry


@pytest.mark.asyncio
class TestCallLlmWithRetry:
    """Test call_llm_with_retry behavior."""

    async def test_success_no_retry(self):
        """Successful call returns immediately without retry."""
        llm = MagicMock()
        response = MagicMock()
        response.content = "Hello"
        response.additional_kwargs = {}
        llm.ainvoke = AsyncMock(return_value=response)

        result = await call_llm_with_retry(llm, "test prompt", node="test")
        assert result.content == "Hello"
        assert llm.ainvoke.call_count == 1

    async def test_retry_on_timeout(self):
        """TimeoutError triggers retry."""
        llm = MagicMock()
        success_response = MagicMock()
        success_response.content = "OK"
        success_response.additional_kwargs = {}
        llm.ainvoke = AsyncMock(side_effect=[asyncio.TimeoutError(), success_response])

        with patch("agent.config.asyncio.sleep", new_callable=AsyncMock):
            result = await call_llm_with_retry(llm, "test", node="test", max_retries=2, retry_delay=0.1)
        assert result.content == "OK"
        assert llm.ainvoke.call_count == 2

    async def test_empty_content_raises(self):
        """Empty LLM content raises ValueError (non-retryable)."""
        llm = MagicMock()
        empty_response = MagicMock()
        empty_response.content = ""
        empty_response.additional_kwargs = {}
        llm.ainvoke = AsyncMock(return_value=empty_response)

        with pytest.raises(ValueError, match="empty content"):
            await call_llm_with_retry(llm, "test", node="test", max_retries=2, retry_delay=0.1)

    async def test_jitter_in_delay(self):
        """Retry delay includes jitter (not exact exponential)."""
        llm = MagicMock()
        success = MagicMock()
        success.content = "OK"
        success.additional_kwargs = {}
        llm.ainvoke = AsyncMock(side_effect=[asyncio.TimeoutError(), success])

        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            # Don't actually sleep

        with patch("agent.config.asyncio.sleep", side_effect=mock_sleep):
            await call_llm_with_retry(llm, "test", node="test", max_retries=2, retry_delay=1.0)

        # First retry: base_delay=1.0 * 2^0 = 1.0, plus 0-50% jitter
        assert len(sleep_calls) == 1
        assert 1.0 <= sleep_calls[0] <= 1.5  # base + up to 50% jitter

    async def test_max_retries_exceeded(self):
        """Raises after max_retries exhausted."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch("agent.config.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(asyncio.TimeoutError),
        ):
            await call_llm_with_retry(llm, "test", node="test", max_retries=1, retry_delay=0.01)
