# Changelog

All notable changes to AuditBee will be documented in this file.

## [1.0.3] - 2026-05-21

### Bug Fixes

- **LightRAG transitive dependencies**: Added `nano_vectordb`, `aiohttp`, `networkx`, `pandas`, `pypinyin`, `tenacity`, `xlsxwriter` to `build.spec` `collect_all()`. Fixes LightRAG initialization failure in packaged exe.
- **Pre-built knowledge graph index bundling**: Added `graphrag_index/lightrag_output` to `build.spec` datas + manual copy in `build_exe.bat`. Pre-built index now ships with the exe.
- **KG index first-run seeding**: Added startup logic in `main.py` to copy bundled pre-built index to writable `KG_OUTPUT_DIR` on first run.
- **asyncio.Lock race condition**: Fixed `lightrag_tool.py` creating `asyncio.Lock` lazily inside `get_lightrag()`, which allowed two concurrent coroutines to create separate locks. Now initialized at module level.
- **risk_assessor silent failure**: Changed failed LLM call behavior from `risk_assessed=True, status="running"` to `risk_assessed=False, status="error"`, allowing supervisor to properly detect and stop the pipeline.
- **supervisor error detection**: Expanded error detection from `status=="error" and not regulation_checked` to `status=="error"` at any stage, preventing silent continuation after failures.
- **Dead code cleanup**: Removed unused `format_risk_summary()` function from `risk_matrix.py`.

### Security

- **CORS default**: Changed `CORS_ORIGINS` default from `*` to `http://localhost:3000,http://localhost:8000` in `.env.example`.
- **Host binding**: Changed `--host` default from `0.0.0.0` to `127.0.0.1` in launcher.

### Documentation

- **Improvement roadmap**: Added `docs/roadmap.md` with P0-P3 improvement plan covering data closed loop, human-in-the-loop, performance optimization, GPU support, and Docker deployment.

## [1.0.2] - 2026-05-20

### Bug Fixes

- **PDF export native dependency**: Replaced `weasyprint` (requires Pango/Cairo/GObject native libs) with `xhtml2pdf` (pure Python). PDF export now works on Windows without GTK runtime installation.
- **RapidOCR ONNX model bundling**: Added `collect_data_files('rapidocr_onnxruntime')` to `build.spec` so PyInstaller bundles the 3 ONNX model files (~16MB) + config.yaml. Previously only Python code was collected via `hiddenimports`, leaving models unbundled.
- **PyInstaller package collection**: Replaced `hiddenimports` with `collect_all()` for critical packages (bleach, reportlab, pydantic_settings, httpx, aiosqlite, xhtml2pdf, etc.) to ensure all submodules and data files are bundled. Fixes ImportError crashes on packaged exe startup.
- **Embedding model directory**: `MODEL_DIR` now defaults to `APP_DIR / "model"` (writable) instead of `RESOURCE_BASE / "model"` (read-only `_internal/`). `download_model.py` now detects frozen mode and downloads to the exe directory.

- **PyInstaller path resolution**: Created unified `backend/app/core/paths.py` module replacing all `__file__`-based path calculations across 10+ files. Fixes crash when running from extracted archive on another machine.
- **Writable data directory**: Data files (database, logs, reports, documents) now correctly write to `exe_dir/data/` instead of `_internal/data/`, preventing failures in write-protected installations.
- **asyncio.Lock lifecycle**: Fixed `lightrag_tool.py` creating `asyncio.Lock()` at import time, which caused `RuntimeError` when event loop changed.
- **ENV_FILE writable location**: `.env` config file now stored at `exe_dir/config/.env` instead of read-only `_internal/config/.env`. UI configuration changes persist across restarts.
- **os.getenv() missing .env values**: Added `load_dotenv()` in startup sequence so agent/Lightrag API keys are available via `os.getenv()` on first boot.
- **KG input directory writable**: Knowledge graph input directory moved to `data/kg_input/` (writable). Bundled regulation files auto-copied on first run. Fixes `PermissionError` when uploading regulation documents.
- **Agent prompt path robustness**: `report_writer.py`, `regulation_expert.py`, `risk_assessor.py` prompt loaders now use `AGENT_DIR` from paths module with `__file__` fallback.
- **report_writer fallback path**: Fallback directory now points to project root `data/reports/` instead of read-only bundle path.
- **Agent system frozen import**: `agent_helpers.py` now uses `BUNDLE_DIR` (`sys._MEIPASS`) for `sys.path` in frozen mode, fixing `ImportError` that made the entire agent audit system unavailable (503) in packaged builds.

### Features

- **Tkinter GUI launcher**: New `backend/app/tkinter_launcher.py` provides a first-run GUI window for LLM provider selection, API key input, connection testing, and optional embedding model download (~1.3 GB). Non-technical users no longer need to manually edit `.env` files.
- **Launcher CLI flag**: `--no-launcher` flag to skip tkinter GUI for headless/automated deployments.
- **PDF report export**: New `GET /api/reports/{id}/export/pdf` endpoint using xhtml2pdf. Reports page now has a direct PDF download button instead of browser print dialog.
- **HTML/PDF XSS sanitization**: Markdown-generated HTML sanitized via `bleach.clean()` before rendering, stripping `<script>` and other dangerous tags.

### Improvements

- **LLM client caching**: `agent/config.py` now caches `ChatOpenAI` instances by `(provider, model, temperature, max_tokens)`, eliminating repeated TCP/TLS handshake overhead.
- **Startup warmup**: Embedding model preloading and LightRAG initialization run in background thread at startup.
- **Build config**: `graphrag_index/input/` bundled (source regulation files); stale output data excluded from bundle; `data/` directory structure created at exe level; `.env` auto-created from `.env.example` on first run. Added `docx`, `lxml`, `numpy`, `onnxruntime` to hiddenimports. Added `tkinter`, `_tkinter`, `tkinter.ttk` to hiddenimports for GUI launcher.
- **Entry point**: PyInstaller entry point changed from `main.py` to `launcher.py` (CLI wrapper that optionally shows tkinter GUI before starting uvicorn).
- **Test coverage**: Added `test_paths.py` (path module) and `test_api_reports_export.py` (PDF/HTML export). Total: 181 tests passing.

## [1.0.1] - 2026-05-19

### Bug Fixes

- **Timezone display**: All API datetime responses now include UTC timezone suffix (+00:00), fixing 8-hour display offset in frontend
- **Knowledge graph page**: Fixed TDZ compile error caused by useCallback declaration order
- **Risk alerts**: Create alerts in `awaiting_review` path (was skipped by early return)
- **Audit findings**: Lowered `validate_findings` description length threshold from 10 to 2 characters
- **Dashboard responsive**: Use Ant Design responsive breakpoints instead of fixed column widths
- **Config float handling**: `_apply_setting()` now correctly handles float types (e.g., TEMPERATURE)
- **Config Path import**: Fixed `NameError: name 'Path' is not defined` in `_update_env_file()`
- **Asyncio import**: Moved asyncio import to file-level in main.py
- **LLM engine close**: Protected `close()` method from single adapter failure
- **SSE hook**: Fixed race condition by closing existing EventSource before creating new one
- **JSON parser**: Added trailing comma handling for LLM outputs

### Improvements

- **Build spec**: Added hiddenimports for markdown, pymupdf, mammoth, rapidocr, httpx, json_repair
- **Config example**: Added missing `_MODEL` entries for all 8 LLM providers
- **Knowledge graph**: Auto-load graph visualization when index is built
- **Build index**: Now indexes both `.txt` and `.md` files
- **Factory reset script**: New `scripts/factory_reset.bat` to clean runtime data while preserving knowledge graph
- **Build script**: Creates runtime directory structure after packaging

## [1.0.0] - 2026-05-19

### Security Fixes (Phase 1)

- **Electron security hardening**: Set `contextIsolation: true`, `nodeIntegration: false`, added `preload.js` with `contextBridge`
- **Path traversal prevention**: Added filename validation (`..`, `/`, `\\`) to knowledge graph upload endpoint
- **XSS prevention**: HTML report export now escapes title with `html.escape()`
- **Config input validation**: Added try/except for integer config values, returns 422 on invalid input
- **Data loss protection**: Re-run now deletes old findings only after new audit succeeds (backup mechanism)
- **CORS configurable**: Read origins from `CORS_ORIGINS` environment variable instead of hardcoded localhost
- **SSE disconnect detection**: `stream_all_tasks` endpoint checks `request.is_disconnected()` to prevent infinite loops
- **ErrorBoundary fix**: Added `componentDidCatch` to log errors instead of silently swallowing them

### Agent UX Optimization (Phase 2)

- **Task cancellation**: New `POST /tasks/{id}/cancel` endpoint + cancel button in task list and drawer
- **SSE progress streaming**: EventBus publishes real-time progress events (0% → 100%) via Server-Sent Events
- **Elapsed time timer**: Shows "已运行 Xm Ys" in task drawer, updates every second
- **Browser notifications**: Notification API fires on task completion/failure/awaiting_review
- **Agent thinking panel**: Collapsible panel showing agent execution logs with typewriter animation
- **Agent flow chart interaction**: Node click handler, running node glow effect, completed edge highlighting
- **Progress bar**: SSE-driven progress updates from 0% to 100% during audit execution

### Architecture

- **EventBus**: In-memory pub/sub with per-connection queue fan-out for SSE streaming
- **astream_events**: Replaced `graph.ainvoke()` with `graph.astream_events(version="v2")` for node-level event streaming
- **validate_findings**: Activated previously dead code to filter invalid findings before persistence

### Backend

- Added `CANCELLED` status to `TaskStatus` enum
- Added `_publish_progress()` method to `TaskRunner`
- Added `cancel()` method to `TaskRunner` with `asyncio.CancelledError` handling
- Document content truncation warning in regulation_expert and risk_assessor agents
- JSON parse failure logging in `json_parser.py`
- Fallback report marker when LLM is unavailable

### Frontend

- `useTaskSSE` hook: progress event handler, STAGE_PROGRESS_MAP fallback
- `AgentThinkingPanel`: Collapse/expand toggle, auto-collapse on task completion, typewriter animation
- `AgentFlowChart`: `onNodeClick` callback, node shadow glow, edge color differentiation
- `AuditTasksPage`: Cancel button, elapsed timer, completion notification, STATUS_FILTER_OPTIONS updated
- New types: `AgentThinkingEvent`, `LLMTokenEvent` interfaces
- Constants: Added `cancelled` status to all maps (STATUS_COLORS, STATUS_LABELS, STAGE_LABELS, STAGE_COLORS)
