import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.risk_alert import AlertLevel, AlertStatus, RiskAlert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_alert(db_session, severity=SeverityLevel.HIGH, alert_level=AlertLevel.CRITICAL, status=AlertStatus.ACTIVE):
    finding = Finding(
        task_id=0, finding_type=FindingType.COMPLIANCE_RISK,
        severity=severity, title="Test Finding", description="Test desc",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    alert = RiskAlert(
        finding_id=finding.id, alert_level=alert_level, status=status,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert, finding


# ---------------------------------------------------------------------------
# List alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_alerts_empty(client: AsyncClient):
    response = await client.get("/api/alerts/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_alerts_with_data(client: AsyncClient, db_session: AsyncSession):
    alert, finding = await _create_alert(db_session)

    response = await client.get("/api/alerts/")
    assert response.status_code == 200
    alerts = response.json()["items"]
    assert len(alerts) >= 1
    a = alerts[0]
    assert a["id"] == alert.id
    assert a["finding_id"] == finding.id
    assert a["alert_level"] == "critical"
    assert a["status"] == "active"
    assert a["finding_title"] == "Test Finding"
    assert a["finding_severity"] == "high"


@pytest.mark.asyncio
async def test_list_alerts_includes_finding_info(client: AsyncClient, db_session: AsyncSession):
    alert, finding = await _create_alert(db_session)

    resp = await client.get("/api/alerts/")
    items = resp.json()["items"]
    a = [x for x in items if x["id"] == alert.id][0]
    assert a["finding_description"] == "Test desc"
    assert a["finding_severity"] == "high"
    assert a["task_id"] == 0


@pytest.mark.asyncio
async def test_list_alerts_pagination(client: AsyncClient, db_session: AsyncSession):
    for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
        await _create_alert(db_session, severity=sev)

    resp = await client.get("/api/alerts/", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_alerts_filter_by_status(client: AsyncClient, db_session: AsyncSession):
    await _create_alert(db_session, status=AlertStatus.ACTIVE)
    await _create_alert(db_session, status=AlertStatus.RESOLVED)

    response = await client.get("/api/alerts/", params={"status": "resolved"})
    assert response.status_code == 200
    alerts = response.json()["items"]
    assert all(a["status"] == "resolved" for a in alerts)


@pytest.mark.asyncio
async def test_list_alerts_filter_acknowledged(client: AsyncClient, db_session: AsyncSession):
    await _create_alert(db_session, status=AlertStatus.ACKNOWLEDGED)

    resp = await client.get("/api/alerts/", params={"status": "acknowledged"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(a["status"] == "acknowledged" for a in items)


@pytest.mark.asyncio
async def test_list_alerts_invalid_status(client: AsyncClient):
    resp = await client.get("/api/alerts/", params={"status": "bogus"})
    assert resp.status_code == 422
    assert "无效" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Acknowledge alert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acknowledge_alert(client: AsyncClient, db_session: AsyncSession):
    alert, _ = await _create_alert(db_session, status=AlertStatus.ACTIVE)

    response = await client.put(f"/api/alerts/{alert.id}/acknowledge")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_acknowledge_nonexistent_alert(client: AsyncClient):
    response = await client.put("/api/alerts/999/acknowledge")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_acknowledge_already_resolved(client: AsyncClient, db_session: AsyncSession):
    alert, _ = await _create_alert(db_session, status=AlertStatus.RESOLVED)

    resp = await client.put(f"/api/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 400
    assert "解决" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_acknowledge_already_acknowledged(client: AsyncClient, db_session: AsyncSession):
    """Acknowledging an already-acknowledged alert should succeed (idempotent)."""
    alert, _ = await _create_alert(db_session, status=AlertStatus.ACKNOWLEDGED)

    resp = await client.put(f"/api/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Resolve alert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_alert(client: AsyncClient, db_session: AsyncSession):
    alert, _ = await _create_alert(db_session, status=AlertStatus.ACTIVE)

    response = await client.put(f"/api/alerts/{alert.id}/resolve")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_resolve_from_acknowledged(client: AsyncClient, db_session: AsyncSession):
    alert, _ = await _create_alert(db_session, status=AlertStatus.ACKNOWLEDGED)

    resp = await client.put(f"/api/alerts/{alert.id}/resolve")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resolve_nonexistent_alert(client: AsyncClient):
    response = await client.put("/api/alerts/999/resolve")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resolve_already_resolved(client: AsyncClient, db_session: AsyncSession):
    alert, _ = await _create_alert(db_session, status=AlertStatus.RESOLVED)

    resp = await client.put(f"/api/alerts/{alert.id}/resolve")
    assert resp.status_code == 400
    assert "已经是解决状态" in resp.json()["detail"]
