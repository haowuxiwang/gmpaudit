# AuditBee - Project Goal

## What We're Building

An AI-powered GMP compliance audit assistant for pharmaceutical quality management personnel. Combines multi-agent orchestration (LangGraph) with knowledge graph retrieval (LightRAG) to automate document analysis, risk identification, and report generation. Distributed as an Electron desktop application.

## Core Design Principles

1. **Deterministic pipeline**: Supervisor routing uses state flags, not LLM decisions. Audit workflows require predictable, reproducible execution.
2. **Graceful degradation**: Every component has a fallback. LightRAG → regulation DB, LLM → template report, PDF → OCR. The system must never crash — it always produces a result.
3. **Local-first**: Embedding model runs locally (BAAI/bge-large-zh-v1.5). No mandatory cloud dependencies for core functionality.
4. **Multi-provider LLM**: 8 providers via adapter pattern with hot-swap. Users choose their own LLM provider.

## Pipeline

```
parse_doc → supervisor → regulation_expert → risk_assessor → report_writer → END
```

- **parse_doc**: Extract text, detect document type
- **regulation_expert**: Search LightRAG knowledge graph (fallback: hardcoded DB of 10 entries), LLM analysis
- **risk_assessor**: LLM identifies findings, calculates risk score
- **report_writer**: LLM generates Markdown report (fallback: template)
- **supervisor**: Deterministic routing based on state flags

## Current Status (2026-05-18)

### Working
- End-to-end audit pipeline (document → report)
- 4-agent Supervisor pattern with deterministic routing
- LightRAG knowledge graph with 5 regulation documents (GMP + ICH Q9/Q10)
- 8 LLM providers via unified adapter
- Frontend: 8 pages, fully Chinese UI, knowledge graph visualization
- Feishu webhook notifications (HMAC-SHA256)
- Test suite: Backend 153 + Agent 73 = 226 tests, all green
- Auth system removed (local desktop app, no login needed)
- Document processing: .pdf, .docx, .doc, .txt, .jpg/.png/.tiff (OCR)
- Config API: API keys masked in GET responses
- Report export: HTML with print-friendly CSS (browser print-to-PDF)
- Risk alerts enriched with Finding details (title, description, severity)
- Frontend theme colors centralized in `constants/theme.ts`
- All `any` types eliminated from frontend pages
- Accessibility: clickable task items have `role="button"` + keyboard support

### Recently Fixed
- LightRAG fallback chain was dead code — now properly triggers on failure
- LLM failures no longer cascade-terminate the pipeline
- Added LLM retry (1 retry, 2s delay) for transient failures
- Supervisor only terminates on early errors (before regulation check)
- Antiword subprocess encoding crash on Windows (GBK → UTF-8)
- Frontend fully localized to Chinese (Ant Design zhCN locale)
- Frontend API types aligned with backend (ConfigMap, Finding, RiskAlert)
- Deprecated `bodyStyle` replaced with `styles.body` across all pages
- Shared constants extracted (STATUS_LABELS, STAGE_LABELS, TASK_TYPE_LABELS)
- 60+ hardcoded colors replaced with THEME token references
- `toLocaleString()` calls now include `'zh-CN'` locale
- `Modal.confirm` onOk handlers wrapped with try/catch
- API error interceptor extracts backend `detail` field into `error.message`

### Known Limitations
- Regulation fallback DB has only 10 entries
- Document content truncated to 3000 chars for LLM analysis
- No verification agent to challenge findings
- Backend-Agent bridge uses `sys.path` injection

## Development Priority

| Phase | Focus | Status |
|-------|-------|--------|
| P0 | Auth removal, docs, pipeline robustness | Done |
| P1 | Quality-driven loop, verification agent, expand regulation DB | Not started |
| P2 | UI polish, config security, report export, Docker/Electron | In progress (UI polish done, Docker/Electron pending) |
| P3 | Human-in-the-loop, A2A protocol, multi-site, audit history | Not started |

## Quick Start

```bash
cp config/.env.example config/.env  # Add at least one LLM API key
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
scripts/start.bat  # or start.sh on Linux/Mac
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture and data flow.

## Development Guide

See [docs/development-guide.md](docs/development-guide.md) for setup, patterns, and contribution guide.
