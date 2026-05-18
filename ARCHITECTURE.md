# AuditBee Architecture

## System Goal

AuditBee is an AI-powered GMP compliance audit system for pharmaceutical manufacturing. It combines multi-agent orchestration (LangGraph) with knowledge graph retrieval (LightRAG) to analyze documents, identify compliance risks, and generate structured audit reports. Distributed as an Electron desktop application.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Electron Desktop                    │
│  ┌──────────────────────────────────────────────┐   │
│  │         Frontend (React + Ant Design)        │   │
│  │  Dashboard │ Documents │ Audit │ Reports │ KG│   │
│  └──────────────────┬───────────────────────────┘   │
│                     │ HTTP (localhost:8000)           │
│  ┌──────────────────┴───────────────────────────┐   │
│  │           Backend API (FastAPI)               │   │
│  │  documents │ audit │ reports │ config │ alerts│   │
│  │  agent-audit │ kg                              │   │
│  └──────┬────────────────┬──────────────────────┘   │
│         │                │                           │
│  ┌──────┴──────┐  ┌──────┴──────┐                   │
│  │ Agent System │  │ Knowledge   │                   │
│  │ (LangGraph)  │  │ Graph       │                   │
│  │              │  │ (LightRAG)  │                   │
│  └─────────────┘  └─────────────┘                   │
└─────────────────────────────────────────────────────┘
```

## Agent Pipeline

The audit pipeline is a deterministic state machine managed by LangGraph's StateGraph:

```
parse_doc ──→ supervisor ──→ regulation_expert ──→ supervisor ──→ risk_assessor ──→ supervisor ──→ report_writer ──→ supervisor ──→ END
```

### Node Responsibilities

| Node | Role | External Calls |
|------|------|----------------|
| `parse_doc` | Extract text from document, auto-detect type (deviation/SOP/change_control) | PyMuPDF, python-docx |
| `supervisor` | Deterministic routing based on state flags (no LLM) | None |
| `regulation_expert` | Find relevant GMP regulations, analyze document against them | LightRAG → fallback DB, LLM |
| `risk_assessor` | Identify compliance issues, calculate risk score | LLM, risk_matrix |
| `report_writer` | Generate structured Markdown audit report | LLM (fallback: template) |

### Supervisor Routing Logic

```
if status == "error"           → END
if iteration > 10              → END (error)
if report_generated == True    → END (completed)
if regulation_checked == False → regulation_expert
if risk_assessed == False      → risk_assessor
else                           → report_writer
```

### Shared State (AuditState)

All nodes communicate via a shared `AuditState` TypedDict:
- **Input**: `document_content`, `document_name`, `document_path`, `document_type`, `audit_focus`
- **Regulation**: `matched_regulations`, `regulation_summary`, `regulation_checked`
- **Risk**: `findings`, `risk_score`, `risk_level`, `risk_assessed`
- **Output**: `report_markdown`, `report_path`, `report_generated`
- **Control**: `messages` (Annotated[list, merge_lists]), `iteration`, `status`, `next_agent`

## Knowledge Graph Integration

### LightRAG Pipeline

```
Regulation texts (graphrag_index/input/)
    ↓ Chunking (1200 tokens, 100 overlap)
    ↓ Entity extraction (LLM)
    ↓ Embedding (BAAI/bge-large-zh-v1.5, 1024-dim)
    ↓ Graph construction (entities + relations)
    ↓ Vector storage (NanoVectorDB)
Knowledge graph index (graphrag_index/lightrag_output/)
```

### Query Flow

```
regulation_expert node
    ↓ Try: lightrag_search(query, method="local")
    ↓ Success → use results
    ↓ Failure → fallback to search_regulations() (hardcoded 10 entries)
    ↓ Merge LLM analysis + DB results
    ↓ Return matched_regulations + regulation_summary
```

### Source Documents (5 files)

- `gmp_china_ch02_quality.txt` — Chinese GMP Chapter 2: Quality Management
- `gmp_china_ch08_document.txt` — Chinese GMP Chapter 8: Document Management
- `gmp_china_ch10_qc_qa.txt` — Chinese GMP Chapter 10: QC & QA
- `ich_q9_risk_management.txt` — ICH Q9 Quality Risk Management
- `ich_q10_quality_system.txt` — ICH Q10 Pharmaceutical Quality System

## Data Flow

```
1. User uploads document (PDF/DOCX/TXT)
   → Backend saves file, creates Document record (status: UPLOADED)
   → Background task: extract text → save to content_text (status: PROCESSED)

2. User creates audit task, selects documents
   → Backend creates AuditTask record (status: PENDING)

3. User runs task (or agent-audit/run)
   → TaskRunner picks up task (status: RUNNING)
   → For each document: invoke agent graph
     → parse_doc: read content_text
     → regulation_expert: query LightRAG + LLM analysis
     → risk_assessor: LLM analysis → findings + risk score
     → report_writer: LLM → Markdown report
   → Save findings to DB, create RiskAlerts for HIGH/MEDIUM
   → Generate aggregate report (multi-doc) or use agent report (single-doc)
   → Send Feishu notification
   → Task status: COMPLETED

4. User views results
   → Dashboard: statistics, recent tasks
   → Reports: Markdown content with metadata
   → Alerts: risk alerts with acknowledge/resolve actions
   → Knowledge Graph: query + visualization
```

## Technology Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Agent framework | LangGraph | Deterministic routing, StateGraph fits sequential audit flow |
| Knowledge graph | LightRAG | Lightweight, local embedding, good for Chinese text |
| Embedding model | BAAI/bge-large-zh-v1.5 | Chinese-optimized, 1024-dim, runs locally |
| Routing strategy | Deterministic (state flags) | Audit requires predictable order, not LLM decisions |
| Database | SQLite (aiosqlite) | Simple deployment, no external dependencies |
| Desktop framework | Electron | Cross-platform, web tech stack reuse |
| LLM providers | 8 providers via adapter | Flexibility, cost optimization, fallback options |

## Failure Handling Strategy

Every component in the pipeline has a degradation path. The system must never crash — it always produces a result.

### LightRAG Failure Chain

```
lightrag_search() fails (ImportError / model missing / index not built / LLM error)
    ↓ raises exception (never swallows)
    ↓ regulation_expert catches → uses fallback regulation DB (10 entries)
    ↓ sets source = "fallback DB"
    ↓ pipeline continues with DB results
```

LightRAG failure scenarios:
- `lightrag-hku` package not installed
- Embedding model files not downloaded (user needs to pull from ModelScope)
- Embedding model files corrupted
- LightRAG index not built
- LightRAG internal LLM call fails

### LLM Failure Chain

```
LLM call fails (401 / 429 / timeout / 500 / bad model / bad URL)
    ↓ call_llm_with_retry: retry once after 2s delay
    ↓ still fails → agent catches exception
    ↓ regulation_expert: returns DB results with summary noting LLM failure
    ↓ risk_assessor: returns empty findings, status="running" (not "error")
    ↓ report_writer: generates template-based fallback report
    ↓ supervisor: does NOT terminate (only terminates on pre-regulation errors)
    ↓ pipeline completes with degraded output
```

### Supervisor Termination Rules

The supervisor only terminates the pipeline early when:
- `status == "error"` AND `regulation_checked == False` (error before regulation check)
- `iteration > 10` (infinite loop protection)

Post-regulation errors (LLM failures in risk_assessor or report_writer) never terminate the pipeline.

### LLM Retry

All LLM calls go through `call_llm_with_retry()` in `agent/config.py`:
- 1 retry with 2-second delay
- Handles transient failures: network timeout, rate limiting, DNS resolution
- After retry exhaustion, exception propagates to agent-level fallback

## Known Limitations

1. **Linear execution**: Agent runs once through, no self-correcting loop when findings are empty or regulations insufficient
2. **Small regulation DB**: Fallback has only 10 entries; LightRAG index covers 5 documents
3. **Document truncation**: Content truncated to 3000 chars for LLM analysis
4. **No verification agent**: No dedicated step to challenge/validate findings
5. **Backend-Agent bridge**: Uses `sys.path` injection (`agent_helpers.py`), not clean package import

## Future Directions

- **Quality-driven loop**: Add retry logic when findings are empty or report lacks evidence
- **Verification agent**: Post-report agent that challenges findings and checks evidence
- **Expanded regulation库**: Add FDA 21 CFR, EU GMP, WHO guidelines to LightRAG index
- **Human-in-the-loop**: Review node for high-risk findings before finalizing report
- **MCP tool packaging**: Wrap agent tools as MCP servers for external integration
- **Containerized deployment**: Docker Compose for backend/agent/frontend separation
