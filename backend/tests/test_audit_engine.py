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
