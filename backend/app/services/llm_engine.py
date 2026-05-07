import httpx
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

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

class DeepSeekAdapter(BaseLLMAdapter):
    """DeepSeek适配器"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "deepseek-chat"

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                },
                timeout=kwargs.get("timeout", 120)
            )

            data = response.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data["usage"],
                finish_reason=data["choices"][0]["finish_reason"]
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True
                },
                timeout=kwargs.get("timeout", 120)
            ) as response:
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

class QwenAdapter(BaseLLMAdapter):
    """通义千问适配器 (OpenAI兼容模式)"""

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-plus"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                },
                timeout=kwargs.get("timeout", 120)
            )

            data = response.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data["usage"],
                finish_reason=data["choices"][0]["finish_reason"]
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True
                },
                timeout=kwargs.get("timeout", 120)
            ) as response:
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

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI适配器"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com", model: str = "gpt-4o"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                },
                timeout=kwargs.get("timeout", 120)
            )

            data = response.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data["usage"],
                finish_reason=data["choices"][0]["finish_reason"]
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        import json
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True
                },
                timeout=kwargs.get("timeout", 120)
            ) as response:
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
    """Anthropic适配器"""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.base_url = base_url
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
                    "content-type": "application/json"
                },
                json=body,
                timeout=kwargs.get("timeout", 120)
            )

            data = response.json()
            return LLMResponse(
                content=data["content"][0]["text"],
                model=data["model"],
                usage=data["usage"],
                finish_reason=data.get("stop_reason", "end_turn")
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:

        system, user_messages = self._extract_system(messages)
        body: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
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
                    "content-type": "application/json"
                },
                json=body,
                timeout=kwargs.get("timeout", 120)
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "content_block_delta":
                            yield data["delta"]["text"]

class GLMAdapter(BaseLLMAdapter):
    """智谱AI适配器"""

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4", model: str = "glm-4-flash"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096)
                },
                timeout=kwargs.get("timeout", 120)
            )

            data = response.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data["usage"],
                finish_reason=data["choices"][0]["finish_reason"]
            )

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        import json
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True
                },
                timeout=kwargs.get("timeout", 120)
            ) as response:
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

class LLMEngine:
    """LLM引擎"""

    def __init__(self):
        self.adapters: Dict[str, BaseLLMAdapter] = {}
        self._init_adapters()

    def _init_adapters(self):
        if settings.DEEPSEEK_API_KEY:
            self.adapters["deepseek"] = DeepSeekAdapter(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL
            )

        if settings.QWEN_API_KEY:
            self.adapters["qwen"] = QwenAdapter(
                api_key=settings.QWEN_API_KEY,
                base_url=getattr(settings, 'QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
            )

        if settings.OPENAI_API_KEY:
            self.adapters["openai"] = OpenAIAdapter(settings.OPENAI_API_KEY, settings.OPENAI_BASE_URL)

        if settings.ANTHROPIC_API_KEY:
            self.adapters["anthropic"] = AnthropicAdapter(settings.ANTHROPIC_API_KEY)

        if settings.GLM_API_KEY:
            self.adapters["glm"] = GLMAdapter(settings.GLM_API_KEY)

    async def analyze(self, document: str, prompt: str, model: str = "deepseek") -> LLMResponse:
        adapter = self.adapters.get(model)
        if not adapter:
            raise ValueError(f"不支持的模型: {model}")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": document}
        ]

        return await adapter.chat(messages)

    async def compare(self, doc1: str, doc2: str, criteria: str, model: str = "deepseek") -> LLMResponse:
        adapter = self.adapters.get(model)
        if not adapter:
            raise ValueError(f"不支持的模型: {model}")

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
            {"role": "user", "content": prompt}
        ]

        return await adapter.chat(messages)

    async def generate_report(self, findings: List[Dict[str, Any]], model: str = "deepseek") -> str:
        adapter = self.adapters.get(model)
        if not adapter:
            raise ValueError(f"不支持的模型: {model}")

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
            {"role": "user", "content": prompt}
        ]

        response = await adapter.chat(messages)
        return response.content

llm_engine = None

def get_llm_engine() -> LLMEngine:
    global llm_engine
    if llm_engine is None:
        llm_engine = LLMEngine()
    return llm_engine
