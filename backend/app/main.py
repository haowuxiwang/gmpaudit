import asyncio
import logging
import os
import shutil
import sys
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
from app.core import paths
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

    log_dir = str(paths.LOG_DIR)
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


async def _seed_configurations():
    """Sync .env values into configurations DB table on first run."""
    import re
    from sqlalchemy import select
    from app.api.config import _LLM_KEY_MAP
    from app.models.configuration import Configuration

    _placeholder_re = re.compile(r'^your_', re.IGNORECASE)

    try:
        async with async_session() as db:
            for key, (attr, _) in _LLM_KEY_MAP.items():
                val = getattr(settings, attr, None)
                if val is None or str(val) == "":
                    continue
                # Skip placeholder values from .env.example
                if _placeholder_re.match(str(val)):
                    continue
                result = await db.execute(
                    select(Configuration).where(Configuration.config_key == key)
                )
                if result.scalar_one_or_none() is None:
                    db.add(Configuration(
                        config_key=key,
                        config_value=str(val),
                        config_type="string",
                    ))
            await db.commit()
            logging.getLogger(__name__).info("Seeded configurations table from .env")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to seed configurations: %s", e)


async def startup():
    _configure_logging()

    logger = logging.getLogger(__name__)
    logger.info("AuditBee starting (frozen=%s, app_dir=%s)", paths.FROZEN, paths.APP_DIR)

    # Ensure writable directories exist
    paths.ensure_writable_dirs()

    # Copy .env.example if .env doesn't exist
    if not paths.ENV_FILE.exists():
        example = paths.CONFIG_DIR / ".env.example"
        if example.exists():
            shutil.copy2(example, paths.ENV_FILE)
            logger.info("Created .env from .env.example")

    # Populate os.environ from .env so os.getenv() works for agent/Lightrag
    from dotenv import load_dotenv
    load_dotenv(paths.ENV_FILE, override=False)
    logger.info("Loaded .env into os.environ")

    # Seed KG_INPUT_DIR with bundled regulation files on first run
    if paths._KG_INPUT_BUNDLED.is_dir():
        existing = list(paths.KG_INPUT_DIR.glob("*.txt")) + list(paths.KG_INPUT_DIR.glob("*.md"))
        if not existing:
            for f in paths._KG_INPUT_BUNDLED.iterdir():
                if f.is_file():
                    shutil.copy2(f, paths.KG_INPUT_DIR / f.name)
            logger.info("Seeded KG input from bundled regulations")

    # Seed KG_OUTPUT_DIR with pre-built LightRAG index on first run
    if paths._KG_OUTPUT_BUNDLED.is_dir():
        existing = list(paths.KG_OUTPUT_DIR.glob("*.json")) + list(paths.KG_OUTPUT_DIR.glob("*.graphml"))
        if not existing:
            for f in paths._KG_OUTPUT_BUNDLED.iterdir():
                if f.is_file():
                    shutil.copy2(f, paths.KG_OUTPUT_DIR / f.name)
            logger.info("Seeded KG output from bundled pre-built index")

    # Add bundled FFmpeg to PATH for torchcodec/sentence_transformers
    ffmpeg_dir = str(paths.TOOLS_DIR / "ffmpeg")
    if os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            logger.info("Added FFmpeg to PATH: %s", ffmpeg_dir)

    for d in [settings.UPLOAD_DIR, settings.PROCESSED_DIR, settings.REPORTS_DIR, str(paths.DB_DIR)]:
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

    # Reset stale KG build status (in case of crash during previous build)
    _reset_json = '{"building": false, "started_at": null, "error": null, "recent_logs": []}'
    from sqlalchemy import text as _text
    async with async_session() as _db:
        await _db.execute(
            _text("UPDATE configurations SET config_value = :val WHERE config_key = 'kg_build_status' AND config_value LIKE '%\"building\": true%'"),
            {"val": _reset_json},
        )
        await _db.commit()
        logger.info("Reset stale KG build status (if any)")

    # Seed configurations table from .env so GET /config/ returns real values
    await _seed_configurations()

    # Recover zombie tasks (RUNNING tasks from previous process)
    from datetime import datetime, timezone
    from sqlalchemy import select
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
    version="1.0.2",
    lifespan=lifespan,
)

# CORS: in frozen mode use wildcard (desktop app, same-origin served by FastAPI);
# in dev mode restrict to localhost dev ports.
if getattr(sys, 'frozen', False):
    origins = ["*"]
else:
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002")
    origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_routers = [
    (documents, "/api/documents", "documents"),
    (audit, "/api/audit", "audit"),
    (reports, "/api/reports", "reports"),
    (config, "/api/config", "config"),
    (alerts, "/api/alerts", "alerts"),
    (agent_audit, "/api/agent-audit", "agent-audit"),
    (kg, "/api/kg", "knowledge-graph"),
    (health, "/api/health", "health"),
]
for _mod, _prefix, _tag in _routers:
    _router = getattr(_mod, "router", None)
    if _router is None:
        logging.warning("Router not found in module %s — skipping %s", _mod.__name__, _prefix)
    else:
        app.include_router(_router, prefix=_prefix, tags=[_tag])
        logging.info("Registered router: %s (%d routes)", _prefix, len(_router.routes))


# Mount static files for frontend (PyInstaller packaging)
if paths.STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(paths.STATIC_DIR), html=True), name="static")
