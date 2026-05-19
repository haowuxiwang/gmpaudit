from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "ok", "service": "AuditBee"}


@router.get("/db")
async def db_health(db: AsyncSession = Depends(get_db)):
    result = {}
    try:
        rows = (await db.execute(text("PRAGMA journal_mode"))).fetchone()
        result["journal_mode"] = rows[0] if rows else "unknown"
        rows = (await db.execute(text("PRAGMA synchronous"))).fetchone()
        result["synchronous"] = rows[0] if rows else "unknown"
        rows = (await db.execute(text("PRAGMA busy_timeout"))).fetchone()
        result["busy_timeout"] = rows[0] if rows else 0
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result
