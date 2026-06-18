import pytest

from app.services.audit_engine import AuditEngine, get_audit_engine


def test_get_audit_engine_singleton():
    e1 = get_audit_engine()
    e2 = get_audit_engine()
    assert e1 is e2


@pytest.mark.asyncio
async def test_assess_risk_high():
    engine = AuditEngine()
    findings = [
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"},
    ]
    risk = await engine.assess_risk(findings)
    assert risk["risk_level"] == "high"
    assert risk["total_findings"] == 3
    assert risk["high_risk"] == 1


@pytest.mark.asyncio
async def test_assess_risk_medium():
    engine = AuditEngine()
    findings = [{"severity": "medium"} for _ in range(5)]
    risk = await engine.assess_risk(findings)
    assert risk["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_assess_risk_low():
    engine = AuditEngine()
    findings = [{"severity": "low"}]
    risk = await engine.assess_risk(findings)
    assert risk["risk_level"] == "low"
    assert risk["score"] > 0


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


@pytest.mark.asyncio
async def test_assess_risk_empty_findings():
    engine = AuditEngine()
    risk = await engine.assess_risk([])
    assert risk["risk_level"] == "low"
    assert risk["total_findings"] == 0
    assert risk["high_risk"] == 0
    assert risk["medium_risk"] == 0
    assert risk["low_risk"] == 0
    assert risk["score"] == 100


@pytest.mark.asyncio
async def test_assess_risk_score_clamped_to_zero():
    engine = AuditEngine()
    # 6 high findings: 100 - 6*20 = -20, should clamp to 0
    findings = [{"severity": "high"} for _ in range(6)]
    risk = await engine.assess_risk(findings)
    assert risk["score"] == 0
    assert risk["risk_level"] == "high"


@pytest.mark.asyncio
async def test_assess_risk_medium_threshold_boundary():
    engine = AuditEngine()
    # 3 medium out of 10 = 30%, should be "low" (not > 0.3)
    findings = [{"severity": "medium"} for _ in range(3)] + [{"severity": "low"} for _ in range(7)]
    risk = await engine.assess_risk(findings)
    assert risk["risk_level"] == "low"

    # 4 medium out of 10 = 40%, should be "medium"
    findings = [{"severity": "medium"} for _ in range(4)] + [{"severity": "low"} for _ in range(6)]
    risk = await engine.assess_risk(findings)
    assert risk["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_assess_risk_missing_severity_key():
    engine = AuditEngine()
    findings = [{"severity": None}, {}, {"title": "no severity"}]
    risk = await engine.assess_risk(findings)
    assert risk["high_risk"] == 0
    assert risk["medium_risk"] == 0
    assert risk["low_risk"] == 0
    assert risk["total_findings"] == 3


@pytest.mark.asyncio
async def test_assess_risk_mixed_no_high():
    engine = AuditEngine()
    findings = [
        {"severity": "medium"},
        {"severity": "low"},
        {"severity": "low"},
    ]
    risk = await engine.assess_risk(findings)
    # 1 medium out of 3 = 33%, > 0.3, so medium
    assert risk["risk_level"] == "medium"
    assert risk["score"] == 100 - (10 + 5 + 5)
