import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.audit_engine import AuditEngine, AuditConfig, get_audit_engine


def test_audit_config_defaults():
    config = AuditConfig()
    assert config.check_logic_flaws is True
    assert config.check_compliance is True
    assert config.check_consistency is True
    assert config.check_missing_info is True
    assert config.risk_threshold == "medium"
    assert config.max_findings == 50


def test_get_audit_engine_singleton():
    e1 = get_audit_engine()
    e2 = get_audit_engine()
    assert e1 is e2


def test_parse_findings_valid_json():
    engine = AuditEngine()
    content = '[{"type": "logic_flaw", "severity": "high", "title": "Test", "description": "Desc"}]'
    findings = engine._parse_findings(content)
    assert len(findings) == 1
    assert findings[0]["type"] == "logic_flaw"


def test_parse_findings_invalid_json():
    engine = AuditEngine()
    content = "This is not JSON at all"
    findings = engine._parse_findings(content)
    assert len(findings) == 1
    assert findings[0]["title"] == "需要人工审核"
    assert findings[0]["severity"] == "medium"


def test_parse_findings_json_in_text():
    engine = AuditEngine()
    content = 'Some text before [{"type": "compliance", "severity": "low", "title": "T", "description": "D"}] some text after'
    findings = engine._parse_findings(content)
    assert len(findings) == 1


def test_parse_findings_empty():
    engine = AuditEngine()
    findings = engine._parse_findings("")
    assert len(findings) == 1  # Fallback


def test_assess_risk_high():
    engine = AuditEngine()
    findings = [
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"},
    ]

    async def run():
        risk = await engine.assess_risk(findings)
        return risk

    import asyncio
    risk = asyncio.get_event_loop().run_until_complete(run())
    assert risk["risk_level"] == "high"
    assert risk["total_findings"] == 3
    assert risk["high_risk"] == 1


def test_assess_risk_medium():
    engine = AuditEngine()
    findings = [{"severity": "medium"} for _ in range(5)]

    import asyncio
    risk = asyncio.get_event_loop().run_until_complete(engine.assess_risk(findings))
    assert risk["risk_level"] == "medium"


def test_assess_risk_low():
    engine = AuditEngine()
    findings = [{"severity": "low"}]

    import asyncio
    risk = asyncio.get_event_loop().run_until_complete(engine.assess_risk(findings))
    assert risk["risk_level"] == "low"
    assert risk["score"] > 0


@pytest.mark.asyncio
async def test_analyze_deviation():
    engine = AuditEngine()
    mock_llm = AsyncMock()
    mock_llm.analyze = AsyncMock(return_value=MagicMock(
        content='[{"type": "logic_flaw", "severity": "high", "title": "T", "description": "D"}]'
    ))
    engine.llm = mock_llm

    config = AuditConfig()
    findings = await engine.analyze_deviation("偏差报告内容", config)
    assert len(findings) == 1
    mock_llm.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_sop():
    engine = AuditEngine()
    mock_llm = AsyncMock()
    mock_llm.analyze = AsyncMock(return_value=MagicMock(
        content='[{"type": "compliance_risk", "severity": "medium", "title": "T", "description": "D"}]'
    ))
    engine.llm = mock_llm

    config = AuditConfig()
    findings = await engine.analyze_sop("SOP内容", config)
    assert len(findings) == 1


@pytest.mark.asyncio
async def test_check_consistency_single_doc():
    engine = AuditEngine()
    config = AuditConfig()
    findings = await engine.check_consistency(["单个文档"], config)
    assert findings == []


@pytest.mark.asyncio
async def test_check_consistency_multiple_docs():
    engine = AuditEngine()
    mock_llm = AsyncMock()
    mock_llm.analyze = AsyncMock(return_value=MagicMock(
        content='[{"type": "inconsistency", "severity": "low", "title": "T", "description": "D"}]'
    ))
    engine.llm = mock_llm

    config = AuditConfig()
    findings = await engine.check_consistency(["文档1", "文档2"], config)
    assert len(findings) == 1


@pytest.mark.asyncio
async def test_assess_risk_score_calculation():
    engine = AuditEngine()
    findings = [
        {"severity": "high"},
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"},
    ]
    risk = await engine.assess_risk(findings)
    # score = 100 - (2*20 + 1*10 + 1*5) = 100 - 55 = 45
    assert risk["score"] == 45
