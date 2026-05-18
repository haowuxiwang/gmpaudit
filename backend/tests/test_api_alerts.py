import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.risk_alert import RiskAlert, AlertLevel, AlertStatus


@pytest.mark.asyncio
async def test_list_alerts_empty(client: AsyncClient):
    response = await client.get("/api/alerts/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_alerts_with_data(client: AsyncClient, db_session: AsyncSession):
    # Create a finding first (alerts need a finding_id)
    finding = Finding(
        task_id=0,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH,
        title="Test Finding",
        description="Test desc",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    # Create an alert
    alert = RiskAlert(
        finding_id=finding.id,
        alert_level=AlertLevel.CRITICAL,
        status=AlertStatus.ACTIVE,
    )
    db_session.add(alert)
    await db_session.commit()

    response = await client.get("/api/alerts/")
    assert response.status_code == 200
    alerts = response.json()["items"]
    assert len(alerts) >= 1


@pytest.mark.asyncio
async def test_acknowledge_alert(client: AsyncClient, db_session: AsyncSession):
    finding = Finding(
        task_id=0,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH,
        title="Test",
        description="Test",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    alert = RiskAlert(
        finding_id=finding.id,
        alert_level=AlertLevel.WARNING,
        status=AlertStatus.ACTIVE,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    response = await client.put(f"/api/alerts/{alert.id}/acknowledge")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_resolve_alert(client: AsyncClient, db_session: AsyncSession):
    finding = Finding(
        task_id=0,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.LOW,
        title="Test",
        description="Test",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    alert = RiskAlert(
        finding_id=finding.id,
        alert_level=AlertLevel.INFO,
        status=AlertStatus.ACTIVE,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    response = await client.put(f"/api/alerts/{alert.id}/resolve")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_acknowledge_nonexistent_alert(client: AsyncClient):
    response = await client.put("/api/alerts/999/acknowledge")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resolve_nonexistent_alert(client: AsyncClient):
    response = await client.put("/api/alerts/999/resolve")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_alerts_filter_by_status(client: AsyncClient, db_session: AsyncSession):
    finding = Finding(
        task_id=0,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.MEDIUM,
        title="Test",
        description="Test",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    alert = RiskAlert(
        finding_id=finding.id,
        alert_level=AlertLevel.WARNING,
        status=AlertStatus.RESOLVED,
    )
    db_session.add(alert)
    await db_session.commit()

    response = await client.get("/api/alerts/?status=resolved")
    assert response.status_code == 200
    alerts = response.json()["items"]
    assert all(a["status"] == "resolved" for a in alerts)
