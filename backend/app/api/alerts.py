from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.risk_alert import RiskAlert, AlertStatus

router = APIRouter()

@router.get("/")
async def list_alerts(status: str = None, db: AsyncSession = Depends(get_db)):
    query = select(RiskAlert)
    if status:
        query = query.where(RiskAlert.status == status)
    query = query.order_by(RiskAlert.created_at.desc())
    result = await db.execute(query)
    alerts = result.scalars().all()
    return [{"id": a.id, "finding_id": a.finding_id, "alert_level": a.alert_level.value,
             "status": a.status.value, "created_at": a.created_at,
             "resolved_at": a.resolved_at, "resolved_by": a.resolved_by} for a in alerts]

@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskAlert).where(RiskAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="警报不存在")
    alert.status = AlertStatus.ACKNOWLEDGED
    await db.commit()
    return {"status": "success"}

@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskAlert).where(RiskAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="警报不存在")
    alert.status = AlertStatus.RESOLVED
    from sqlalchemy.sql import func
    alert.resolved_at = func.now()
    await db.commit()
    return {"status": "success"}
