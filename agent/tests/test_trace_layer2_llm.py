"""Layer 2: LLM Stability Verification.

Requires real API key (AGENT_LLM_PROVIDER configured).
Mark with @pytest.mark.real_llm for selective exclusion.
"""

import pytest

# Skip all tests if no real LLM is configured
pytestmark = pytest.mark.real_llm


class TestLLMStability:
    """Verify LLM is stable with consecutive calls."""

    def test_default_provider_set(self):
        from agent.config import get_default_provider

        provider = get_default_provider()
        assert provider, "Default provider is empty"
        assert isinstance(provider, str)

    def test_provider_fallback_works(self):
        from agent.config import get_llm_with_fallback

        llm = get_llm_with_fallback(temperature=0.1)
        assert llm is not None, "get_llm_with_fallback returned None"
        assert hasattr(llm, "ainvoke"), "LLM instance missing ainvoke method"

    def test_llm_has_provider_tag(self):
        from agent.config import get_llm_with_fallback

        llm = get_llm_with_fallback(temperature=0.1)
        assert hasattr(llm, "_provider"), "LLM missing _provider attribute"
        assert llm._provider, "_provider is empty"

    def test_10_consecutive_calls_no_401(self):
        """Make 10 consecutive LLM calls and verify no auth errors."""
        import asyncio

        from agent.config import call_llm_with_retry, get_llm_with_fallback

        llm = get_llm_with_fallback(temperature=0.1)

        async def run():
            results = []
            for i in range(10):
                try:
                    resp = await call_llm_with_retry(llm, f"Say 'pong {i}' and nothing else.")
                    results.append({"success": True, "content_length": len(resp.content)})
                except Exception as e:
                    error_str = str(e).lower()
                    is_auth = any(kw in error_str for kw in ("401", "403", "unauthorized", "invalid api key"))
                    results.append({"success": False, "error": str(e)[:200], "is_auth_error": is_auth})
            return results

        results = asyncio.run(run())

        successes = [r for r in results if r["success"]]
        auth_errors = [r for r in results if not r["success"] and r.get("is_auth_error")]

        assert len(auth_errors) == 0, f"Auth errors found: {auth_errors}"
        assert len(successes) >= 8, f"Expected >= 8 successes out of 10, got {len(successes)}"

    def test_response_parseable(self):
        """LLM returns parseable content."""
        import asyncio

        from agent.config import call_llm_with_retry, get_llm_with_fallback

        async def run():
            llm = get_llm_with_fallback(temperature=0.1)
            resp = await call_llm_with_retry(llm, "Return exactly: hello")
            return resp.content

        content = asyncio.run(run())
        assert content, "Empty response from LLM"
        assert isinstance(content, str)
        assert len(content) > 0
