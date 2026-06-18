import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import paths
from app.core.database import async_session, get_db

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
        result["error"] = "数据库连接失败"
        raise HTTPException(status_code=503, detail=result) from e
    return result


@router.get("/full")
async def full_health_check():
    """Comprehensive health check including LLM and disk."""
    checks = {
        "status": "ok",
        "service": "AuditBee",
        "version": "1.0.3",
        "checks": {},
    }

    # Database check
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["checks"]["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Disk space check
    try:
        usage = shutil.disk_usage(str(paths.DATA_DIR))
        free_gb = usage.free / (1024**3)
        checks["checks"]["disk_free_gb"] = round(free_gb, 2)
        if free_gb < 1:
            checks["checks"]["disk"] = "warning: low space"
            checks["status"] = "degraded"
        else:
            checks["checks"]["disk"] = "ok"
    except Exception:
        checks["checks"]["disk"] = "unknown"

    # LLM check (just check if adapters exist)
    try:
        from app.services.llm_engine import get_llm_engine

        engine = get_llm_engine()
        if engine.adapters:
            checks["checks"]["llm"] = f"ok ({len(engine.adapters)} providers)"
        else:
            checks["checks"]["llm"] = "warning: no providers configured"
            checks["status"] = "degraded"
    except Exception:
        checks["checks"]["llm"] = "unknown"

    return checks
