# AuditBee Development Guide

## Project Goal

AuditBee is an AI-powered GMP compliance audit assistant for pharmaceutical quality management personnel. It combines multi-agent orchestration with knowledge graph retrieval to automate document analysis, risk identification, and report generation.

## Current Status (2026-05-18)

### What Works
- **Core pipeline**: End-to-end audit from document upload to structured report
- **Agent system**: 4-agent Supervisor pattern with deterministic routing
- **Knowledge graph**: LightRAG index with 5 regulation documents (GMP + ICH Q9/Q10)
- **Frontend**: 8 pages, fully Chinese UI, Ant Design zhCN locale, knowledge graph visualization
- **Multi-LLM**: 8 providers supported via adapter pattern with hot-swap
- **Notifications**: Feishu webhook with HMAC-SHA256 signed cards
- **Document processing**: .pdf, .docx, .doc, .txt, .jpg/.png/.tiff (OCR via RapidOCR)
- **Testing**: Backend 153 + Agent 73 = 226 tests, all green. TypeScript 0 errors.
- **Config security**: API keys masked in GET responses (`_mask_value()`)
- **Report export**: HTML export with print-friendly CSS (`GET /api/reports/{id}/export/html`)
- **Alerts enrichment**: Risk alerts include finding title, description, severity via SQLAlchemy relationship

### Known Limitations
- Agent executes linearly — no self-correcting loop when findings are empty
- Regulation fallback DB has only 10 entries
- Document content truncated to 3000 chars for LLM analysis
- No verification agent to challenge findings
- Backend-Agent bridge uses `sys.path` injection

### Pipeline Robustness (Implemented 2026-05-18)
- LightRAG failure triggers fallback regulation DB (was dead code, now fixed)
- LLM failures do NOT cascade-terminate the pipeline (regulation_expert/risk_assessor degrade gracefully)
- LLM calls have 1 retry with 2s delay for transient failures
- Supervisor only terminates on early errors (before regulation check completes)
- Report writer always produces output (LLM report or template fallback)
- See ARCHITECTURE.md "Failure Handling Strategy" for full degradation matrix

### Frontend Patterns
- Shared constants in `frontend/src/constants/audit.ts` (STATUS_LABELS, STAGE_LABELS, TASK_TYPE_LABELS, etc.)
- Theme colors centralized in `frontend/src/constants/theme.ts` — use `THEME.xxx` instead of hardcoded hex values
- Ant Design `zhCN` locale via `ConfigProvider` in `App.tsx`
- API types in `frontend/src/types/api.ts` — must match backend response shapes
- API error interceptor extracts `error.response.data.detail` into `error.message` automatically
- Date formatting: always use `.toLocaleString('zh-CN')` for consistency

## Development Environment

### Prerequisites
- Python 3.11+
- Node.js 18+
- At least one LLM provider API key (Mimo, DeepSeek, etc.)

### Setup
```bash
# 1. Clone and configure
git clone <repo>
cp config/.env.example config/.env
# Edit config/.env, add your API key(s)

# 2. Install dependencies
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
cd ../agent && pip install -r requirements.txt

# 3. Download embedding model (for knowledge graph)
cd .. && python scripts/download_model.py

# 4. Start
scripts/start.sh  # or start.bat on Windows
```

### Running Tests
```bash
cd backend && pytest                    # 153 tests
cd agent && pytest                      # 73 tests
cd frontend && npm test                 # Frontend tests
cd frontend && npx tsc --noEmit         # TypeScript check
```

## Architecture Patterns (Borrowed from Claude Code)

### 1. Tool Abstraction
Each audit capability is a self-contained unit with clear inputs and outputs:
- `parse_file(path) -> str` — document text extraction
- `search_regulations(query) -> list` — regulation lookup
- `calculate_risk_score(findings) -> (score, level)` — risk calculation
- `lightrag_search(query) -> str` — knowledge graph query

### 2. Deterministic Supervisor Routing
The supervisor node uses state flags, not LLM decisions, to route the pipeline. This is intentional — audit workflows require predictable, reproducible execution order.

### 3. Layered Context
- **Layer 1 (Persistent)**: Regulation standards in LightRAG index
- **Layer 2 (Session)**: Current audit findings and risk assessment
- **Layer 3 (Real-time)**: Document under review (truncated to 3000 chars)

### 4. Graceful Degradation
Every component has a fallback:
- LightRAG unavailable → hardcoded regulation DB (10 entries)
- LLM fails → template-based report generation
- PDF text extraction fails → OCR fallback

## Technical Roadmap

### P0: Foundation (Done)
- [x] Remove authentication system (local desktop app)
- [x] Documentation cleanup
- [x] Pipeline robustness — fix fallback chain, add retry, prevent cascade termination
- [x] Frontend fully localized to Chinese
- [x] API type alignment between frontend and backend
- [x] Document processing fixes (antiword encoding, pymupdf version)
- [x] Baseline commit and push
- [ ] Fix frontend production build (`spawn EPERM` issue)

### P1: Agent Intelligence
- [ ] Quality-driven loop: retry when findings empty or regulations insufficient
- [ ] Verification agent: challenge findings after report generation
- [ ] Expand regulation DB: add FDA 21 CFR, EU GMP, WHO guidelines
- [ ] Increase document content limit (3000 → 8000+ chars with context management)

### P2: Deployment & Integration
- [ ] Docker Compose: backend/agent/frontend containers
- [ ] MCP tool packaging: wrap regulation_db, risk_matrix as MCP servers
- [ ] Electron packaging: working .exe/.dmg build
- [ ] CI/CD pipeline: automated testing + build

### P3: Advanced Features
- [ ] Human-in-the-loop: review node for high-risk findings
- [ ] A2A protocol: interoperability with external QMS systems
- [ ] Multi-site audit: support auditing multiple facilities
- [ ] Audit history: track and compare audit results over time

## Adding a New Agent

1. Create `agent/agents/my_agent.py` with a node function:
```python
async def my_agent_node(state: AuditState) -> dict:
    # Process state, call LLM if needed
    return {"my_field": result, "my_flag": True}
```

2. Register in `agent/graph.py`:
```python
graph.add_node("my_agent", my_agent_node)
```

3. Add routing in `supervisor.py`:
```python
if not state.get("my_flag"):
    return {"next_agent": "my_agent"}
```

4. Add state fields in `agent/state.py`

5. Write tests in `agent/tests/test_my_agent.py`

## Adding a New Tool

1. Create `agent/tools/my_tool.py`:
```python
def my_tool(input_data: str) -> dict:
    # Implementation
    return {"result": ...}
```

2. Use in agent nodes via direct import

3. Write tests in `agent/tests/test_my_tool.py`

## Expanding the Regulation库

1. Add regulation text files to `graphrag_index/input/` (`.txt` format)
2. Rebuild index: `POST /api/kg/build` or via Knowledge Graph page
3. Update `agent/tools/regulation_db.py` fallback entries if needed
