# CLAUDE.md

GMP Compliance Audit System - AI-powered document analysis and compliance checking for pharmaceutical manufacturing. Uses LangGraph multi-agent workflow with LightRAG knowledge graph. Distributed as PyInstaller desktop application with tkinter GUI launcher.

## Tech Stack

### Backend (Python 3.11+)
- **Framework:** FastAPI + Uvicorn
- **Database:** SQLAlchemy 2.0 (async) + aiosqlite (SQLite)
- **Agent System:** LangGraph (StateGraph with Supervisor pattern)
- **Knowledge Graph:** LightRAG (regulation retrieval, local embedding)
- **Embedding:** Local BAAI/bge-large-zh-v1.5 via sentence-transformers (agent only)
- **Document Processing:** PyMuPDF (PDF), python-docx (DOCX), RapidOCR (OCR)
- **HTTP Client:** httpx (async)
- **Notifications:** Feishu Webhook Bot (HMAC-SHA256 signed cards)
- **Config:** pydantic-settings, loads from `config/.env` (mutable at runtime, extra="ignore")
- **Testing:** pytest + pytest-asyncio + pytest-cov (asyncio_mode = auto)

### Frontend (TypeScript)
- **Framework:** React 18 + React Router 6
- **UI Library:** Ant Design 5
- **Charts:** ECharts (echarts-for-react)
- **HTTP Client:** Axios
- **Desktop:** PyInstaller + tkinter launcher (frontend runs in system browser)
- **Build:** react-scripts (CRA)

## Project Structure

```
gmpaudit/
  config/           # .env, .env.example
  data/             # Runtime data (documents, database, reports, logs)
  scripts/          # start.bat, start.sh, build_exe.bat, build.spec
    hooks/          # Custom PyInstaller hooks (hook-torch.py)
  model/            # Pre-downloaded embedding model (BAAI/bge-large-zh-v1.5)
  tools/            # Bundled tools (ffmpeg)
  agent/            # LangGraph multi-agent system (PRIMARY audit engine)
    agents/         # Agent nodes: regulation_expert, risk_assessor, report_writer
    parsers/        # Document parsers: pdf, docx, text
    tools/          # Utilities: lightrag_tool, regulation_db, risk_matrix, json_parser
    prompts/        # LLM prompt templates (Chinese)
    config.py       # LLM provider config (8 providers via langchain)
    graph.py        # LangGraph StateGraph definition
    state.py        # AuditState TypedDict (shared state)
    main.py         # CLI entry point
  lightrag_index/   # Knowledge graph index
    input/          # Regulation text files for indexing
    lightrag_output/# LightRAG built index artifacts
    settings.yaml   # GraphRAG config (legacy)
  backend/
    app/
      launcher.py          # PyInstaller entry point, tkinter launcher integration, --no-launcher flag
      main.py              # FastAPI app entry, CORS, lifespan (startup/shutdown)
      tkinter_launcher.py  # Standalone tkinter GUI (no app.* imports, operates on .env directly)
      api/          # Route handlers: documents, audit, reports, config, alerts, agent_audit, kg
      core/         # config.py (Settings), database.py (engine, session), paths.py (frozen/dev path resolution)
      models/       # SQLAlchemy models: document, audit_task, finding, report, risk_alert, configuration
      services/     # Business logic: llm_engine, document_processor, audit_engine, event_bus, notification, task_runner
      utils/        # Helpers: agent_helpers, file_utils
    tests/          # pytest tests with conftest.py
  frontend/
    electron/       # Electron main.ts + preload.js (dev only, not used in production)
    src/
      App.tsx       # Router setup, layout with lazy loading + ErrorBoundary
      pages/        # Dashboard, Documents, AuditTasks, Reports, Settings, Alerts, KnowledgeGraph, NotFound
      components/   # common/Header, Sidebar, ErrorBoundary, AgentFlowChart, AgentThinkingPanel, FindingDetailCard
      hooks/        # useSSE (generic SSE), useTaskSSE (domain hook for audit tasks)
      services/     # api.ts (axios instance + API functions)
      types/        # TypeScript type definitions (api.ts)
      constants/    # audit.ts (status/stage maps), theme.ts
```

## Key Patterns

### Agent System (Primary Audit Engine)
- LangGraph StateGraph with sequential pipeline for deterministic agent routing
- Flow: `parse_doc → regulation_expert → risk_assessor → report_writer → END`
- `AuditState` TypedDict shared between all agents with `Annotated[list, merge_lists]` reducer
- Supervisor uses deterministic routing (not LLM-based) for reliability
- Regulation Expert tries LightRAG first, falls back to hardcoded regulation DB (10 entries)
- **Graceful degradation**: LLM failures do NOT cascade-terminate — each agent has fallback behavior
- **LLM retry**: All LLM calls go through `call_llm_with_retry()` (1 retry, 2s delay)
- **Supervisor guard**: Only terminates on errors before regulation check completes
- **astream_events**: Uses `graph.astream_events(version="v2")` for node-level event streaming (replaces `ainvoke`)
- Backend exposes agent via `POST /api/agent-audit/run` (background task)

### SSE Streaming Pattern
- **EventBus** (`backend/app/services/event_bus.py`): In-memory pub/sub with per-connection `asyncio.Queue` fan-out
- TaskRunner publishes events via `_publish()` and `_publish_done()` helpers
- SSE endpoint subscribes to EventBus, sends historical snapshot first, then live events
- 30s keepalive via `asyncio.wait_for(queue.get(), timeout=30.0)`
- Frontend `useTaskSSE` hook: connects to `/audit/tasks/{id}/stream`, handles `event`, `agent_thinking`, `progress`, `done` event types
- Progress computed from both SSE `progress` events and stage-based fallback map

### Task Cancellation
- `TaskRunner.cancel(task_id)` calls `asyncio_task.cancel()` on the active task
- `CancelledError` caught separately from `Exception` in `_run()` (Python 3.9+ `BaseException` hierarchy)
- Status set to `CANCELLED` (new enum value), EventBus notified via `_publish_done(task_id, "cancelled")`

### Human-in-the-Loop Review
- High-risk findings trigger `AWAITING_REVIEW` status (review gate)
- Frontend shows approve/reject banner; API: `POST /audit/tasks/{id}/approve` / `reject`
- After approval, task moves to `COMPLETED`; after rejection, findings are marked and task completes

### Concurrency Model
- `asyncio.Semaphore(5)` gates parallel task execution (`MAX_CONCURRENT_TASKS`)
- Within a task, multiple documents processed in parallel (`MAX_CONCURRENT_LLM_CALLS=3`)
- Progress uses atomic `UPDATE ... WHERE progress < percent` to prevent race conditions

### Backend API Pattern
- Routes use `APIRouter()` with dependency injection via `Depends(get_db)` for async DB sessions
- No authentication — all endpoints are open (local desktop application)
- Config accessed via `from app.core.config import settings` (mutable singleton)
- Config hot-reload: `PUT /config/{key}` updates settings singleton + reloads LLM adapters
- Models use SQLAlchemy declarative base with Enum columns for status/type fields
- All DB operations are async (`await db.execute`, `await db.commit`)

### Knowledge Graph Upload Pattern
- PDF/DOCX converted to Markdown via `markitdown` library before saving
- Empty conversion result rejected with HTTP 400 (prevents 0kb files for scanned PDFs)
- TXT/MD files saved as-is (binary copy)
- Index build is a separate step (`POST /kg/build`), runs in background via `BackgroundTasks`
- Query uses LightRAG with local embedding model (BAAI/bge-large-zh-v1.5)
- **Limitation**: markitdown has no OCR fallback; scanned/image-only PDFs fail (use DocumentProcessor for OCR)

### LLM Adapter Pattern
- `LLMEngine` singleton with 8 providers (DeepSeek, Qwen, GLM, OpenAI, Anthropic, SiliconFlow, OpenRouter, Mimo)
- 7 use `OpenAICompatibleAdapter`, Anthropic uses `AnthropicAdapter`
- `reload_provider()` for hot-swapping at runtime
- Agent system uses `langchain_openai.ChatOpenAI` / `langchain_anthropic.ChatAnthropic`

### Frontend API Pattern
- Single axios instance in `services/api.ts` with base URL `http://localhost:8000/api`
- Response interceptor unwraps `response.data` automatically
- API functions grouped by domain: `documentApi`, `auditApi`, `reportApi`, `configApi`, `alertsApi`, `agentAuditApi`, `kgApi`
- SSE via `useSSE` generic hook (EventSource + named event dispatch) and `useTaskSSE` domain hook

### Config Pattern
- `backend/app/core/config.py`: `Settings` class (pydantic-settings, `frozen=False` for runtime updates, `extra="ignore"`)
- `.env` file loaded from `config/.env` (absolute path)
- All config fields have defaults; secrets are `Optional[str] = None`

### Path Resolution Pattern (`backend/app/core/paths.py`)
- **`FROZEN`**: `True` when running as PyInstaller bundle
- **`BUNDLE_DIR`** (`sys._MEIPASS`): Read-only resources bundled by PyInstaller (`_internal/`)
- **`APP_DIR`**: Writable application directory — `exe_dir` (frozen) or project root (dev)
- **`RESOURCE_BASE`**: `BUNDLE_DIR` (frozen) or `APP_DIR` (dev) — for read-only resource lookups
- Derived paths: `CONFIG_DIR`, `AGENT_DIR`, `TOOLS_DIR` (read-only), `DATA_DIR`, `DB_DIR`, `LOG_DIR`, `REPORTS_DIR`, `KG_INPUT_DIR`, `KG_OUTPUT_DIR` (writable, always under `APP_DIR`)
- **`MODEL_DIR`**: Defaults to `APP_DIR / "model"` (writable), overridable via `EMBEDDING_MODEL_PATH` env var
- **`ENV_FILE`**: `APP_DIR / "config" / ".env"` (writable location for user config)
- `ensure_writable_dirs()` creates all writable directories at startup

### Launcher Pattern (`backend/app/tkinter_launcher.py`)
- Standalone module — does NOT import from `app.core`, `app.services`, or any `app.*` module
- Avoids circular imports and slow startup (tkinter window appears instantly)
- Operates directly on `.env` file and HTTP requests (`urllib.request`)
- Provider config (8 providers) is hardcoded — must be kept in sync with `agent/config.py`
- `show_launcher() -> dict | None`: Blocks until user clicks "Start" or closes window
- `write_env(path, updates)`: Line-level .env file updater (find `KEY=` and replace, or append)
- Thread safety: All UI updates from background threads via `root.after(0, callback)`
- `--no-launcher` flag in `launcher.py` skips GUI for headless/CI deployments

## Database Models

| Model | Table | Key Fields |
|-------|-------|------------|
| Document | documents | filename, file_path, file_type, process_status (Enum) |
| AuditTask | audit_tasks | task_name, task_type (Enum), status (Enum), progress, document_ids (JSON) |
| Finding | findings | task_id (FK), finding_type (Enum), severity (Enum), title, description, regulation_ref |
| Report | reports | task_id (FK), report_type (Enum), title, content |
| RiskAlert | risk_alerts | finding_id (FK), alert_level (Enum), status (Enum) |
| Configuration | configurations | config_key (unique), config_value, config_type |

## Common Commands

```bash
# Backend
cd backend && python -m uvicorn app.main:app --reload    # Start dev server
cd backend && python -m app.launcher                      # Start with tkinter GUI launcher
cd backend && python -m app.launcher --no-launcher        # Start without GUI (headless)
cd backend && pytest                                       # Run tests
cd backend && pytest tests/test_documents.py               # Run single test file

# Agent (standalone)
cd agent && python main.py --file data/test_documents/sample_deviation.txt --type deviation

# Frontend
cd frontend && npm start                                   # Start dev server (port 3000)
cd frontend && npm run build                               # Production build (output to build/)
cd frontend && npm run dev                                 # Start dev server + Electron window (dev only)

# Both
scripts/start.sh    # or start.bat on Windows

# Packaging
scripts\build_exe.bat  # PyInstaller packaging → dist\AuditBee\
```

## Linting / Formatting

- Backend: `ruff check` + `ruff format --check` (CI enforced)
- Frontend: ESLint + Prettier (CI enforced)
- Style: PEP 8, 4-space indent, double quotes (Python); 2-space indent, single quotes (TypeScript)

## Environment Variables

All defined in `config/.env` (see `config/.env.example`):
- LLM Keys: `DEEPSEEK_API_KEY`, `QWEN_API_KEY`, `GLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SILICONFLOW_API_KEY`, `OPENROUTER_API_KEY`, `MIMO_API_KEY`
- LLM URLs: `DEEPSEEK_BASE_URL`, `QWEN_BASE_URL`, `GLM_BASE_URL`, `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `SILICONFLOW_BASE_URL`, `OPENROUTER_BASE_URL`, `MIMO_BASE_URL` (all include `/v1`)
- LLM Models: `DEEPSEEK_MODEL`, `QWEN_MODEL`, `GLM_MODEL`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `SILICONFLOW_MODEL`, `OPENROUTER_MODEL`, `MIMO_MODEL` (empty = use provider default)
- **Agent:** `AGENT_LLM_PROVIDER` (default provider for agent pipeline, e.g. `mimo`)
- Feishu: `FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET` (optional HMAC-SHA256 signing)
- App: `APP_BASE_URL` (default `http://localhost:8000`), `LOG_LEVEL`, `MAX_CONCURRENT_TASKS`, `DOCUMENT_PROCESS_TIMEOUT`, `LLM_REQUEST_TIMEOUT`, `CORS_ORIGINS`
- Agent tuning: `CHUNK_MAX_CHARS` (default 8000), `STUFF_LIMIT` (default 60000), `MAX_DOCUMENT_CHARS` (default 3000)
- Embedding: `EMBEDDING_MODEL_PATH` (default `./model`)
