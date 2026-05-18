import pytest
from app.services.llm_engine import LLMEngine, LLMResponse

def test_llm_engine_initialization():
    engine = LLMEngine()
    # 没有配置API key时，适配器应该为空
    assert isinstance(engine.adapters, dict)

def test_llm_response_creation():
    response = LLMResponse(
        content="测试内容",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        finish_reason="stop"
    )
    assert response.content == "测试内容"
    assert response.model == "test-model"
    assert response.finish_reason == "stop"

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
