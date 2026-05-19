from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.risk_alert import RiskAlert, AlertStatus

router = APIRouter()

@router.get("/")
async def list_alerts(status: str = None, page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    query = select(RiskAlert).options(selectinload(RiskAlert.finding))
    count_q = select(func.count()).select_from(RiskAlert)
    if status:
        try:
            alert_status = AlertStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"无效的状态值: {status}，可选: {[s.value for s in AlertStatus]}")
        query = query.where(RiskAlert.status == alert_status)
        count_q = count_q.where(RiskAlert.status == alert_status)
    total = (await db.execute(count_q)).scalar()
    query = query.order_by(RiskAlert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    alerts = result.scalars().unique().all()
    return {
        "items": [{
            "id": a.id, "finding_id": a.finding_id, "alert_level": a.alert_level.value,
            "status": a.status.value,
            "created_at": a.created_at.replace(tzinfo=timezone.utc).isoformat() if a.created_at else None,
            "resolved_at": a.resolved_at.replace(tzinfo=timezone.utc).isoformat() if a.resolved_at else None,
            "resolved_by": a.resolved_by,
            "finding_title": a.finding.title if a.finding else None,
            "finding_description": a.finding.description if a.finding else None,
            "finding_severity": a.finding.severity.value if a.finding else None,
            "task_id": a.finding.task_id if a.finding else None,
        } for a in alerts],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

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
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "success"}
