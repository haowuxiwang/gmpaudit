# Changelog

All notable changes to AuditBee will be documented in this file.

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
