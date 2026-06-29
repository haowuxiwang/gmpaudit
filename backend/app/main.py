import asyncio
import contextlib
import logging
import os
import shutil
import sys
import time as _time
import uuid
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

from app.api import agent_audit, alerts, audit, config, documents, health, kg, reports
from app.core import paths
from app.core.config import settings
from app.core.database import Base, async_session, engine
from app.services.event_bus import EventBus
from app.services.task_runner import get_task_runner_factory


class _JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production log analysis."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        return json.dumps(log_entry, ensure_ascii=False)


def _configure_logging() -> None:
    from app.core.config import settings

    root_logger = logging.getLogger()
    if getattr(root_logger, "_gmp_audit_configured", False):
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    console_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    json_fmt = _JsonFormatter()
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    log_dir = str(paths.LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
    except PermissionError:
        logging.getLogger(__name__).warning(
            "Unable to open log file %s, continuing with console logging only",
            log_file,
        )
    else:
        file_handler.setFormatter(json_fmt)
        root_logger.addHandler(file_handler)

    root_logger._gmp_audit_configured = True


async def _seed_configurations():
    """Sync .env values into configurations DB table on first run."""
    import re

    from sqlalchemy import select

    from app.api.config import _LLM_KEY_MAP
    from app.models.configuration import Configuration

    _placeholder_re = re.compile(r"^your_", re.IGNORECASE)

    try:
        async with async_session() as db:
            for key, (attr, _) in _LLM_KEY_MAP.items():
                val = getattr(settings, attr, None)
                if val is None or str(val) == "":
                    continue
                # Skip placeholder values from .env.example
                if _placeholder_re.match(str(val)):
                    continue
                result = await db.execute(select(Configuration).where(Configuration.config_key == key))
                if result.scalar_one_or_none() is None:
                    db.add(
                        Configuration(
                            config_key=key,
                            config_value=str(val),
                            config_type="string",
                        )
                    )
            await db.commit()
            logging.getLogger(__name__).info("Seeded configurations table from .env")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to seed configurations: %s", e)


async def _sync_db_to_env():
    """Read DB config values into os.environ and settings (DB is authoritative)."""
    import os

    from sqlalchemy import select

    from app.api.config import _LLM_KEY_MAP
    from app.models.configuration import Configuration

    try:
        async with async_session() as db:
            result = await db.execute(select(Configuration))
            rows = result.scalars().all()
            updated = 0
            for row in rows:
                key = row.config_key
                val = row.config_value
                if not val or key not in _LLM_KEY_MAP:
                    continue
                attr, env_key = _LLM_KEY_MAP[key]
                os.environ[env_key] = val
                if hasattr(settings, attr):
                    setattr(settings, attr, val)
                updated += 1
            if updated:
                logging.getLogger(__name__).info("Synced %d config values from DB to runtime", updated)
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to sync DB config to runtime: %s", e)


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
            shutil.copyfile(example, paths.ENV_FILE)
            os.chmod(paths.ENV_FILE, 0o600)
            logger.info("Created .env from .env.example")

    # Populate os.environ from .env so os.getenv() works for agent/Lightrag
    from dotenv import load_dotenv

    load_dotenv(paths.ENV_FILE, override=True)
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

        result = await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_columns("audit_tasks"))
        existing_cols = {col["name"] for col in result}
        migrations = {
            "review_comment": "TEXT",
            "reviewed_at": "DATETIME",
            "auto_approve": "BOOLEAN DEFAULT 0",
        }
        for col_name, col_type in migrations.items():
            if col_name not in existing_cols:
                await conn.execute(sa.text(f"ALTER TABLE audit_tasks ADD COLUMN {col_name} {col_type}"))
                logger.info("Added column audit_tasks.%s", col_name)

        # Migration for findings table (finding-level approval)
        try:
            result = await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_columns("findings"))
            existing_finding_cols = {col["name"] for col in result}
            finding_migrations = {
                "status": "VARCHAR(20) DEFAULT 'pending' NOT NULL",
                "reviewer_comment": "TEXT",
                "reviewed_at": "DATETIME",
            }
            for col_name, col_type in finding_migrations.items():
                if col_name not in existing_finding_cols:
                    await conn.execute(sa.text(f"ALTER TABLE findings ADD COLUMN {col_name} {col_type}"))
                    logger.info("Added column findings.%s", col_name)
        except Exception:
            logger.debug("findings table not yet created, skipping migration")

    logger.info("Database schema verified")

    # Reset stale KG build status (in case of crash during previous build)
    _reset_json = '{"building": false, "started_at": null, "error": null, "recent_logs": []}'
    from sqlalchemy import text as _text

    async with async_session() as _db:
        await _db.execute(
            _text(
                "UPDATE configurations SET config_value = :val WHERE config_key = 'kg_build_status' AND config_value LIKE '%\"building\": true%'"
            ),
            {"val": _reset_json},
        )
        await _db.commit()
        logger.info("Reset stale KG build status (if any)")

    # Seed configurations table from .env so GET /config/ returns real values
    await _seed_configurations()

    # Sync DB config values back to runtime (DB is authoritative after UI edits)
    await _sync_db_to_env()

    # Zombie task recovery is handled by TaskRunner.startup_recover()
    # which resets RUNNING/PENDING tasks to PENDING and re-enqueues them


@asynccontextmanager
async def lifespan(app: FastAPI):
    import secrets

    # Generate session API token for request authentication
    app.state.api_token = secrets.token_urlsafe(32)
    logger.info("Session API token generated")

    if not hasattr(app.state, "task_runner_factory"):
        app.state.event_bus = EventBus()
        app.state.task_runner_factory = get_task_runner_factory(
            session_factory=async_session,
            max_concurrency=settings.MAX_CONCURRENT_TASKS,
            llm_concurrency=settings.MAX_CONCURRENT_LLM_CALLS,
            event_bus=app.state.event_bus,
        )
    await startup()
    await app.state.task_runner_factory().startup_recover()

    # Preload LightRAG knowledge graph index in background (non-blocking)
    async def _preload_lightrag():
        try:
            from agent.tools.lightrag_tool import get_lightrag

            await get_lightrag()
            logging.getLogger(__name__).info("LightRAG knowledge graph preloaded")
        except Exception as e:
            logging.getLogger(__name__).warning("LightRAG preload failed (will lazy-load on first query): %s", e)

    asyncio.create_task(_preload_lightrag())

    # Periodic cleanup of stale EventBus entries
    async def _eventbus_cleanup():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            with contextlib.suppress(Exception):
                await app.state.event_bus.cleanup_stale()

    cleanup_task = asyncio.create_task(_eventbus_cleanup())

    # Periodic cleanup of stale rate limit entries
    async def _ratelimit_cleanup():
        """Clean up stale rate limit entries every 5 minutes."""
        while True:
            await asyncio.sleep(300)
            now = _time.monotonic()
            cutoff = now - 60.0  # 1 minute window
            stale_ips = [
                ip for ip, timestamps in _rate_limit_store.items() if not timestamps or timestamps[-1] < cutoff
            ]
            for ip in stale_ips:
                del _rate_limit_store[ip]
            if stale_ips:
                logger.debug("Cleaned up %d stale rate limit entries", len(stale_ips))

    ratelimit_cleanup_task = asyncio.create_task(_ratelimit_cleanup())

    yield
    cleanup_task.cancel()
    ratelimit_cleanup_task.cancel()
    from app.services.llm_engine import get_llm_engine
    from app.services.notification import close_httpx_client

    await app.state.task_runner_factory().shutdown(timeout=30.0)
    await get_llm_engine().close()
    await close_httpx_client()
    await engine.dispose()
    logging.getLogger(__name__).info("AuditBee stopped")


app = FastAPI(
    title="AuditBee",
    description="AI-powered GMP compliance audit system with multi-agent workflow.",
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all exception handler to prevent traceback leakage."""
    logger.error("Unhandled exception on %s %s: [%s] %s", request.method, request.url.path, type(exc).__name__, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# CORS: in frozen mode the frontend is same-origin (served by FastAPI static),
# so CORS is not needed. In dev mode restrict to localhost dev ports.
if getattr(sys, "frozen", False):
    origins = []
else:
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002")
    origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not getattr(sys, "frozen", False),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Simple in-memory metrics store
_metrics = {
    "requests_total": 0,
    "requests_by_status": {},
    "latency_sum_ms": 0.0,
    "latency_count": 0,
    "started_at": _time.time(),
}


# Simple in-memory rate limiter (sliding window per client IP)
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_GENERAL = 120  # requests per minute for general endpoints
_RATE_LIMIT_EXPENSIVE = 20  # requests per minute for expensive endpoints
_RATE_LIMIT_EXPENSIVE_PATHS = {"/api/config/test-llm", "/api/agent-audit/run"}


@app.middleware("http")
async def _rate_limit(request, call_next):
    """Simple sliding-window rate limiter per client IP. Active in frozen (production) mode only."""
    if not getattr(sys, "frozen", False):
        return await call_next(request)

    import time

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = 60.0  # 1 minute

    # Get or create request log for this IP
    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []
    timestamps = _rate_limit_store[client_ip]

    # Prune old entries outside the window
    cutoff = now - window
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)

    # Check limit
    limit = _RATE_LIMIT_EXPENSIVE if request.url.path in _RATE_LIMIT_EXPENSIVE_PATHS else _RATE_LIMIT_GENERAL
    if len(timestamps) >= limit:
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})

    timestamps.append(now)
    return await call_next(request)


@app.middleware("http")
async def _log_requests(request, call_next):
    """Log every HTTP request with trace ID, method, path, status, and latency."""
    trace_id = uuid.uuid4().hex[:8]
    request.state.trace_id = trace_id

    start = _time.monotonic()
    response = await call_next(request)
    elapsed_ms = (_time.monotonic() - start) * 1000

    logger.info(
        "[%s] %s %s -> %d (%.0fms)",
        trace_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    # Update metrics
    _metrics["requests_total"] += 1
    _metrics["latency_sum_ms"] += elapsed_ms
    _metrics["latency_count"] += 1
    status_key = str(response.status_code)
    _metrics["requests_by_status"][status_key] = _metrics["requests_by_status"].get(status_key, 0) + 1

    response.headers["X-Request-ID"] = trace_id
    return response


# Auth: unauthenticated paths (health check and token endpoint)
_AUTH_SKIP_PATHS = {
    "/api/health",
    "/api/health/db",
    "/api/health/full",
    "/api/auth/token",
    "/docs",
    "/openapi.json",
    "/",
    "/index.html",
    "/favicon.ico",
}


@app.middleware("http")
async def _authenticate(request, call_next):
    """Validate API token on all requests except health/token/docs.

    In frozen (production) mode: all endpoints require auth (except skip paths).
    In dev mode: only sensitive endpoints require auth (config mutations, audit actions).
    """
    import re

    # Paths that require auth even in dev mode (sensitive mutation endpoints)
    _SENSITIVE_PATHS_RE = re.compile(
        r"^/api/config/(batch|test-llm|test-webhook)$"
        r"|^/api/config/[^/]+$"  # PUT /api/config/{key} (matched by method below)
        r"|^/api/audit/tasks/[^/]+/(run|cancel|approve|reject)$"
    )
    _SENSITIVE_METHODS = {"PUT", "POST", "DELETE", "PATCH"}

    is_frozen = getattr(sys, "frozen", False)
    path = request.url.path

    # Skip paths that never need auth
    if path in _AUTH_SKIP_PATHS or path.startswith("/static"):
        return await call_next(request)

    # Skip SSE stream endpoints — EventSource API cannot send custom headers
    if path.startswith("/api/audit/tasks/") and path.endswith("/stream"):
        return await call_next(request)
    if path == "/api/audit/tasks/stream":
        return await call_next(request)

    # In frozen mode, all endpoints require auth
    # In dev mode, only sensitive mutation endpoints require auth
    requires_auth = is_frozen or (request.method in _SENSITIVE_METHODS and _SENSITIVE_PATHS_RE.match(path))

    if not requires_auth:
        return await call_next(request)

    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    expected = getattr(app.state, "api_token", None)
    if expected and token != expected:
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": "未授权访问"})
    return await call_next(request)


@app.get("/api/auth/token")
async def get_auth_token(request: Request):
    """Return the session API token. Only accessible from localhost."""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"token": getattr(app.state, "api_token", "")}


@app.get("/api/metrics")
async def get_metrics():
    """Return basic application metrics as JSON."""
    uptime_seconds = _time.time() - _metrics["started_at"]
    avg_latency = (_metrics["latency_sum_ms"] / _metrics["latency_count"]) if _metrics["latency_count"] > 0 else 0
    return {
        "uptime_seconds": round(uptime_seconds, 1),
        "requests_total": _metrics["requests_total"],
        "requests_by_status": _metrics["requests_by_status"],
        "avg_latency_ms": round(avg_latency, 1),
    }


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
