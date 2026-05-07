# CLAUDE.md

GMP Compliance Audit System - AI-powered document analysis and compliance checking for pharmaceutical manufacturing. Uses LangGraph multi-agent workflow with GraphRAG knowledge graph.

## Tech Stack

### Backend (Python 3.11+)
- **Framework:** FastAPI + Uvicorn
- **Database:** SQLAlchemy 2.0 (async) + aiosqlite (SQLite)
- **Agent System:** LangGraph (StateGraph with Supervisor pattern)
- **Knowledge Graph:** Microsoft GraphRAG (regulation retrieval)
- **Embedding:** Local BAAI/bge-large-zh-v1.5 via sentence-transformers
- **Document Processing:** PyMuPDF (PDF), python-docx (DOCX), RapidOCR (OCR)
- **HTTP Client:** httpx (async)
- **Config:** pydantic-settings, loads from `config/.env`
- **Testing:** pytest + pytest-asyncio + pytest-cov (asyncio_mode = auto)
- **Security:** JWT auth with Feishu OAuth (CSRF state validation), itsdangerous

### Frontend (TypeScript)
- **Framework:** React 18 + React Router 6
- **UI Library:** Ant Design 5
- **State Management:** Zustand
- **Charts:** ECharts (echarts-for-react)
- **HTTP Client:** Axios
- **Desktop:** Electron 28
- **Build:** react-scripts (CRA)

## Project Structure

```
gmpaudit/
  config/           # .env, .env.example
  data/             # Runtime data (documents, database, reports)
  scripts/          # start.bat, start.sh
  agent/            # LangGraph multi-agent system (PRIMARY audit engine)
    agents/         # Agent nodes: supervisor, regulation_expert, risk_assessor, report_writer
    parsers/        # Document parsers: pdf, docx, text
    tools/          # Utilities: embedding, graphrag_tool, regulation_db, risk_matrix
    config.py       # LLM provider config (SiliconFlow, DeepSeek, Qwen, GLM)
    graph.py        # LangGraph StateGraph definition
    state.py        # AuditState TypedDict (shared state)
    main.py         # CLI entry point
  graphrag_index/   # Microsoft GraphRAG knowledge graph
    input/          # Regulation text files for indexing
    settings.yaml   # GraphRAG config (SiliconFlow embedding/completion)
    output/         # Built index artifacts
  backend/
    app/
      main.py       # FastAPI app entry, auth middleware, router registration
      api/          # Route handlers: documents, audit, reports, config, auth, alerts, agent_audit
      core/         # config.py (Settings), database.py (engine, session), auth.py (JWT)
      models/       # SQLAlchemy models: document, audit_task, finding, report, risk_alert, configuration
      services/     # Business logic: llm_engine, document_processor
      utils/        # Helpers
    tests/          # pytest tests with conftest.py
  frontend/
    src/
      App.tsx       # Router setup, layout
      pages/        # Dashboard, Documents, AuditTasks, Reports, Settings, Alerts, Login, AuthCallback
      components/   # common/Header, Sidebar, Loading
      services/     # api.ts (axios instance + API functions)
      stores/       # Zustand stores
```

## Key Patterns

### Agent System (Primary Audit Engine)
- LangGraph StateGraph with Supervisor pattern for deterministic agent routing
- Flow: `parse_doc → supervisor → regulation_expert → risk_assessor → report_writer → END`
- `AuditState` TypedDict shared between all agents with `Annotated[list, merge_lists]` reducer
- Supervisor uses deterministic routing (not LLM-based) for reliability
- Regulation Expert tries GraphRAG first, falls back to hardcoded regulation DB
- Backend exposes agent via `POST /api/agent-audit/run` (background task)

### Backend API Pattern
- Routes use `APIRouter()` with dependency injection via `Depends(get_db)` for async DB sessions
- **Auth middleware**: Global middleware checks Bearer token; whitelist paths: `/`, `/docs`, `/openapi.json`, `/api/auth/*`
- All routes except auth require `get_current_user` dependency
- Config accessed via `from app.core.config import settings` (singleton)
- Models use SQLAlchemy declarative base with Enum columns for status/type fields
- All DB operations are async (`await db.execute`, `await db.commit`)
- Pagination: `page` + `page_size` query params with `.offset().limit()`

### LLM Adapter Pattern
- Abstract base class `BaseLLMAdapter` with `chat()` and `chat_stream()` methods
- Concrete adapters: DeepSeek, Qwen, OpenAI, Anthropic, GLM
- `LLMEngine` initializes available adapters based on API keys in config
- Agent system uses SiliconFlow API directly via `agent/config.py`
- All LLM calls are async via httpx

### Frontend API Pattern
- Single axios instance in `services/api.ts` with base URL `http://localhost:8000/api`
- Response interceptor unwraps `response.data` automatically
- API functions grouped by domain: `documentApi`, `auditApi`, `reportApi`, `configApi`

### Config Pattern
- `backend/app/core/config.py`: `Settings` class (pydantic-settings BaseSettings)
- `PROJECT_ROOT` = 3 levels up from config.py (project root)
- `.env` file loaded from `config/.env` (absolute path)
- All config fields have defaults; secrets are `Optional[str] = None`

## Database Models

| Model | Table | Key Fields |
|-------|-------|------------|
| Document | documents | filename, file_path, file_type, process_status (Enum) |
| AuditTask | audit_tasks | task_name, task_type (Enum), status (Enum), progress, document_ids (JSON) |
| Finding | findings | task_id (FK), finding_type (Enum), severity (Enum), title, description |
| Report | reports | task_id, report_type (Enum), title, content, file_path |
| RiskAlert | risk_alerts | finding_id (FK), alert_level (Enum), status (Enum) |
| Configuration | configurations | config_key (unique), config_value, config_type |

## Common Commands

```bash
# Backend
cd backend && python -m uvicorn app.main:app --reload    # Start dev server
cd backend && pytest                                       # Run tests
cd backend && pytest tests/test_documents.py               # Run single test file

# Agent (standalone)
cd agent && python main.py --file data/test_documents/sample_deviation.txt --type deviation

# Frontend
cd frontend && npm start                                   # Start dev server
cd frontend && npm run build                               # Production build
cd frontend && npm run dev                                 # Start with Electron

# Both
scripts/start.sh    # or start.bat on Windows
```

## Linting / Formatting

No explicit linter or formatter config found. Follow existing code style:
- Backend: PEP 8, 4-space indent, double quotes for strings
- Frontend: Standard CRA TypeScript, 2-space indent, single quotes

## Environment Variables

All defined in `config/.env` (see `config/.env.example`):
- Database: `DATABASE_URL`
- LLM Keys: `DEEPSEEK_API_KEY`, `QWEN_API_KEY`, `GLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- LLM URLs: `DEEPSEEK_BASE_URL`, `OPENAI_BASE_URL`
- **SiliconFlow:** `SILICONFLOW_API_KEY` (used by agent system for LLM + embedding)
- Feishu: `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_REDIRECT_URI`, `FEISHU_WEBHOOK_URL`
- JWT: `JWT_SECRET_KEY` (must change from default for production)
- Paths: `UPLOAD_DIR`, `PROCESSED_DIR`, `REPORTS_DIR`
- App: `LOG_LEVEL`, `MAX_CONCURRENT_TASKS`, `DOCUMENT_PROCESS_TIMEOUT`, `LLM_REQUEST_TIMEOUT`
