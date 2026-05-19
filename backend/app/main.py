import logging
import os
import threading
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import agent_audit, alerts, audit, config, documents, health, kg, reports
from app.core.database import Base, engine
from app.core.config import settings
from app.core.database import async_session
from app.services.task_runner import get_task_runner_factory
from app.services.event_bus import EventBus


def _configure_logging() -> None:
    from app.core.config import settings

    root_logger = logging.getLogger()
    if getattr(root_logger, "_gmp_audit_configured", False):
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    except PermissionError:
        logging.getLogger(__name__).warning(
            "Unable to open log file %s, continuing with console logging only",
            log_file,
        )
    else:
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger._gmp_audit_configured = True


async def startup():
    from app.core.config import PROJECT_ROOT

    _configure_logging()

    logger = logging.getLogger(__name__)
    logger.info("AuditBee starting")

    # Add bundled FFmpeg to PATH for torchcodec/sentence_transformers
    ffmpeg_dir = os.path.join(PROJECT_ROOT, "tools", "ffmpeg")
    if os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            logger.info("Added FFmpeg to PATH: %s", ffmpeg_dir)

    for d in [settings.UPLOAD_DIR, settings.PROCESSED_DIR, settings.REPORTS_DIR,
              os.path.join(PROJECT_ROOT, "data", "database")]:
        os.makedirs(d, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight schema migration for existing databases
        import sqlalchemy as sa
        result = await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_columns("audit_tasks")
        )
        existing_cols = {col["name"] for col in result}
        migrations = {
            "review_comment": "TEXT",
            "reviewed_at": "DATETIME",
            "auto_approve": "BOOLEAN DEFAULT 0",
        }
        for col_name, col_type in migrations.items():
            if col_name not in existing_cols:
                await conn.execute(sa.text(
                    f"ALTER TABLE audit_tasks ADD COLUMN {col_name} {col_type}"
                ))
                logger.info("Added column audit_tasks.%s", col_name)

    logger.info("Database schema verified")

    # Recover zombie tasks (RUNNING tasks from previous process)
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.audit_task import AuditTask, TaskStatus

    async with async_session() as db:
        result = await db.execute(select(AuditTask).where(AuditTask.status == TaskStatus.RUNNING))
        zombies = result.scalars().all()
        for t in zombies:
            t.status = TaskStatus.FAILED
            t.error_message = "进程重启，任务自动重置"
            t.completed_at = datetime.now(timezone.utc)
        if zombies:
            await db.commit()
            logger.warning("Recovered %d zombie tasks on startup", len(zombies))

    # Preload embedding model in background thread
    def _preload_embedding():
        try:
            import asyncio
            from agent.tools.lightrag_tool import preload_embedding_model
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(preload_embedding_model())
            loop.close()
        except Exception as e:
            logger.warning("Embedding model preload failed: %s", e)

    threading.Thread(target=_preload_embedding, daemon=True).start()
    logger.info("Embedding model preload started in background")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "task_runner_factory"):
        app.state.event_bus = EventBus()
        app.state.task_runner_factory = get_task_runner_factory(
            session_factory=async_session,
            max_concurrency=settings.MAX_CONCURRENT_TASKS,
            event_bus=app.state.event_bus,
        )
    await startup()
    await app.state.task_runner_factory().startup_recover()

    # Preload LightRAG knowledge graph index (non-blocking on failure)
    try:
        from agent.tools.lightrag_tool import get_lightrag
        await get_lightrag()
        logging.getLogger(__name__).info("LightRAG knowledge graph preloaded")
    except Exception as e:
        logging.getLogger(__name__).warning("LightRAG preload failed (will lazy-load on first query): %s", e)

    # Periodic cleanup of stale EventBus entries
    async def _eventbus_cleanup():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            try:
                await app.state.event_bus.cleanup_stale()
            except Exception:
                pass

    import asyncio
    cleanup_task = asyncio.create_task(_eventbus_cleanup())

    yield
    cleanup_task.cancel()
    from app.services.llm_engine import get_llm_engine
    await app.state.task_runner_factory().shutdown(timeout=30.0)
    await get_llm_engine().close()
    await engine.dispose()
    logging.getLogger(__name__).info("AuditBee stopped")


app = FastAPI(
    title="AuditBee",
    description="AI-powered GMP compliance audit system with multi-agent workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS origins from environment variable, default to localhost dev ports
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002")
origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(agent_audit.router, prefix="/api/agent-audit", tags=["agent-audit"])
app.include_router(kg.router, prefix="/api/kg", tags=["knowledge-graph"])
app.include_router(health.router, prefix="/api/health", tags=["health"])


@app.get("/")
async def root():
    return {"message": "AuditBee API"}


# Mount static files for frontend (PyInstaller packaging)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
