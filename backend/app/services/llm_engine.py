import httpx
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM API error with status code and response body."""
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        pass


def _check_response(response: httpx.Response):
    """Raise LLMError if response status is not 200."""
    if response.status_code != 200:
        raise LLMError(
            f"LLM API error: {response.status_code}",
            status_code=response.status_code,
            response_body=response.text,
        )


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Generic adapter for OpenAI-compatible APIs.

    Works with: DeepSeek, Qwen, GLM, SiliconFlow, OpenRouter, Mimo,
    and any provider exposing an OpenAI-compatible /chat/completions endpoint.

    base_url should include the version path if needed (e.g. ".../v1").
    The adapter appends /chat/completions to it.
    """

    def __init__(self, api_key: str, base_url: str, model: str, name: str = "openai_compat"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = name

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                },
                timeout=kwargs.get("timeout", 120),
            )
            _check_response(response)
            data = response.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {}),
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True,
                },
                timeout=kwargs.get("timeout", 120),
            ) as response:
                _check_response(response)
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic适配器 (Messages API, not OpenAI-compatible)"""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @staticmethod
    def _extract_system(messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, str]]]:
        """Extract system message from messages array (Anthropic requires separate system param)."""
        system = ""
        filtered = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                filtered.append(msg)
        return system, filtered

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        system, user_messages = self._extract_system(messages)
        body: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "messages": user_messages,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=kwargs.get("timeout", 120),
            )
            _check_response(response)
            data = response.json()
            return LLMResponse(
                content=data["content"][0]["text"],
                model=data["model"],
                usage=data.get("usage", {}),
                finish_reason=data.get("stop_reason", "end_turn"),
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        system, user_messages = self._extract_system(messages)
        body: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "messages": user_messages,
            "stream": True,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=kwargs.get("timeout", 120),
            ) as response:
                _check_response(response)
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "content_block_delta":
                            yield data["delta"]["text"]


# Provider registry: name -> (base_url, default_model)
PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "siliconflow": {"base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3.2"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat"},
    "mimo": {"base_url": "https://api.minimax.chat/v1", "model": "MiniMax-Text-01"},
}


class LLMEngine:
    """LLM引擎 - 支持多提供商"""

    def __init__(self):
        self.adapters: Dict[str, BaseLLMAdapter] = {}
        self._init_adapters()

    def _init_adapters(self):
        # Map of provider name -> (env_key_name, env_base_url_name)
        providers = {
            "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
            "qwen": ("QWEN_API_KEY", "QWEN_BASE_URL"),
            "glm": ("GLM_API_KEY", "GLM_BASE_URL"),
            "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
            "siliconflow": ("SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL"),
            "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"),
            "mimo": ("MIMO_API_KEY", "MIMO_BASE_URL"),
        }

        for name, (key_attr, url_attr) in providers.items():
            api_key = getattr(settings, key_attr, None)
            if not api_key:
                continue

            defaults = PROVIDER_DEFAULTS[name]
            base_url = getattr(settings, url_attr, defaults["base_url"])
            model = defaults["model"]

            self.adapters[name] = OpenAICompatibleAdapter(
                api_key=api_key,
                base_url=base_url,
                model=model,
                name=name,
            )

        # Anthropic uses a different API format
        if settings.ANTHROPIC_API_KEY:
            base_url = getattr(settings, "ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            self.adapters["anthropic"] = AnthropicAdapter(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=base_url,
            )

    async def analyze(self, document: str, prompt: str, model: str = "deepseek") -> LLMResponse:
        adapter = self.adapters.get(model)
        if not adapter:
            available = list(self.adapters.keys())
            raise ValueError(f"不支持的模型: {model}，可用: {available}")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": document},
        ]
        return await adapter.chat(messages)

    async def compare(self, doc1: str, doc2: str, criteria: str, model: str = "deepseek") -> LLMResponse:
        adapter = self.adapters.get(model)
        if not adapter:
            available = list(self.adapters.keys())
            raise ValueError(f"不支持的模型: {model}，可用: {available}")

        prompt = f"""请根据以下标准比较两个文档：

标准：{criteria}

文档1：
{doc1[:3000]}

文档2：
{doc2[:3000]}

请指出：
1. 两者之间的主要差异
2. 潜在的不一致之处
3. 风险点和建议"""

        messages = [
            {"role": "system", "content": "你是一个专业的GMP审计员，擅长分析文档的一致性和合规性。"},
            {"role": "user", "content": prompt},
        ]
        return await adapter.chat(messages)

    async def generate_report(self, findings: List[Dict[str, Any]], model: str = "deepseek") -> str:
        adapter = self.adapters.get(model)
        if not adapter:
            available = list(self.adapters.keys())
            raise ValueError(f"不支持的模型: {model}，可用: {available}")

        findings_text = "\n".join([
            f"- [{f['severity']}] {f['title']}: {f['description']}"
            for f in findings
        ])

        prompt = f"""请基于以下审计发现生成一份专业的GMP合规性审计报告：

审计发现：
{findings_text}

报告应包含：
1. 执行摘要
2. 主要发现
3. 风险评估
4. 改进建议
5. 结论

请使用Markdown格式输出。"""

        messages = [
            {"role": "system", "content": "你是一个资深的GMP审计专家，擅长撰写专业的审计报告。"},
            {"role": "user", "content": prompt},
        ]
        response = await adapter.chat(messages)
        return response.content

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Return list of providers that have API keys configured."""
        result = []
        for name, adapter in self.adapters.items():
            defaults = PROVIDER_DEFAULTS.get(name, {})
            result.append({
                "name": name,
                "model": getattr(adapter, "model", defaults.get("model", "")),
                "available": True,
            })
        return result


llm_engine = None


def get_llm_engine() -> LLMEngine:
    global llm_engine
    if llm_engine is None:
        llm_engine = LLMEngine()
    return llm_engine
