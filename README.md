# AuditBee

基于 LangGraph 多 Agent + LightRAG 知识图谱的制药行业 GMP 合规性审计系统，支持文档解析、智能审计分析、法规检索和结构化报告生成。以 Electron 桌面应用形式分发。

## 核心特性

- **多 Agent 审计流程**：LangGraph Supervisor 模式，法规专家 → 风险评估 → 报告撰写，确定性路由保障可靠性
- **法规知识图谱**：LightRAG 构建 GMP/ICH 法规知识库，本地 Embedding + 语义检索 + 硬编码备用库双重保障
- **批量文档处理**：支持 PDF、Word、纯文本格式，PyMuPDF + RapidOCR 双引擎
- **多 LLM 提供商**：统一适配器模式支持 DeepSeek、Qwen、GLM、SiliconFlow、OpenRouter、Mimo、Anthropic 共 8 个提供商
- **结构化报告**：自动生成 Markdown 格式专业审计报告，按严重程度分组
- **风险可视化**：ECharts 仪表盘展示风险分布和审计趋势
- **飞书通知**：Webhook Bot 群通知（HMAC-SHA256 签名卡片）
- **容错降级设计**：LightRAG → 硬编码法规库、LLM → 模板报告、PDF → OCR 多级降级

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端框架** | React 18 + TypeScript + React Router 6 |
| **UI 组件** | Ant Design 5 |
| **图表** | ECharts (echarts-for-react) |
| **桌面** | Electron 28 |
| **后端框架** | Python FastAPI + Uvicorn |
| **数据库** | SQLAlchemy 2.0 (async) + aiosqlite (SQLite) |
| **Agent 系统** | LangGraph (StateGraph + Supervisor 模式) |
| **知识图谱** | LightRAG + NanoVectorDB |
| **Embedding** | 本地 BAAI/bge-large-zh-v1.5 (sentence-transformers) |
| **文档处理** | PyMuPDF + python-docx + RapidOCR |
| **LLM 调用** | langchain-openai / langchain-anthropic + httpx |

## 快速开始

### 1. 配置环境

```bash
cp config/.env.example config/.env
# 编辑配置文件，添加至少一个 LLM 提供商的 API 密钥
# 推荐: MIMO_API_KEY 或 DEEPSEEK_API_KEY
```

### 2. 安装依赖

```bash
# 后端依赖
cd backend && pip install -r requirements.txt

# 前端依赖
cd ../frontend && npm install

# Agent 依赖 (如需独立运行)
cd ../agent && pip install -r requirements.txt
```

### 3. 启动系统

```bash
# Windows
scripts\start.bat

# Linux/Mac
./scripts/start.sh
```

### 4. 访问系统

- 前端界面：http://localhost:3000
- API 文档：http://localhost:8000/docs

## 系统架构

```
用户上传文档
    ↓
Backend API (FastAPI)
    ↓
Agent 系统 (LangGraph)
    ├─ parse_doc: 文档解析 (PDF/DOCX/TXT)
    ├─ supervisor: 流程调度 (确定性路由)
    ├─ regulation_expert: 法规检索 (LightRAG + 备用DB)
    ├─ risk_assessor: 风险评估 (LLM分析)
    └─ report_writer: 报告生成 (Markdown)
    ↓
结构化审计报告 + 风险告警 + 飞书通知
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload/batch` | 批量上传文档 |
| GET | `/api/documents/` | 获取文档列表（分页） |
| DELETE | `/api/documents/{id}` | 删除文档 |
| POST | `/api/audit/tasks` | 创建审计任务 |
| GET | `/api/audit/tasks` | 获取审计任务列表（分页） |
| POST | `/api/audit/tasks/{id}/run` | 运行审计任务 |
| GET | `/api/audit/tasks/{id}/findings` | 获取审计发现 |
| GET | `/api/audit/dashboard` | 仪表盘统计 |
| POST | `/api/agent-audit/run` | 运行 Agent 审计（单文档） |
| GET | `/api/reports/` | 获取审计报告（分页） |
| POST | `/api/reports/generate/{task_id}` | 生成审计报告 |
| GET | `/api/alerts/` | 获取风险警报（分页） |
| GET | `/api/config/` | 获取系统配置 |
| POST | `/api/config/batch` | 批量更新配置 |
| GET | `/api/kg/status` | 知识图谱索引状态 |
| POST | `/api/kg/build` | 触发索引构建 |
| POST | `/api/kg/query` | 查询知识图谱 |

## 目录结构

```
gmpaudit/
├── agent/             # LangGraph 多Agent系统 (核心审计引擎)
│   ├── agents/        # Agent 节点: supervisor, regulation_expert, risk_assessor, report_writer
│   ├── parsers/       # 文档解析器: PDF, DOCX, TXT
│   ├── tools/         # 工具: lightrag_tool, regulation_db, risk_matrix, json_parser
│   ├── prompts/       # LLM Prompt 模板
│   ├── config.py      # LLM 多提供商配置
│   ├── graph.py       # LangGraph StateGraph 定义
│   └── state.py       # AuditState 共享状态
├── graphrag_index/    # 知识图谱索引
│   ├── input/         # 法规文本文件 (5篇: GMP 3章 + ICH Q9/Q10)
│   └── lightrag_output/ # LightRAG 构建产物
├── backend/           # FastAPI 后端 (API 网关)
│   └── app/
│       ├── api/       # API 路由 (documents, audit, reports, config, alerts, agent_audit, kg)
│       ├── core/      # 配置、数据库
│       ├── models/    # 数据库模型 (6张表)
│       └── services/  # LLM 引擎、文档处理、任务运行器、通知
├── frontend/          # React 前端 (Electron 桌面应用)
│   └── src/
│       ├── pages/     # 8个页面: Dashboard, Documents, AuditTasks, Reports, Settings, Alerts, KnowledgeGraph, NotFound
│       ├── components/# 公共组件: Header, Sidebar, ErrorBoundary
│       └── services/  # API 调用封装 (axios)
├── config/            # .env 配置文件
├── data/              # 运行时数据 (文档、报告、数据库)
└── scripts/           # 启动脚本 (start.bat, start.sh)
```

## 开发指南

### 独立运行 Agent

```bash
cd agent
python main.py --file data/test_documents/sample_deviation.txt --type deviation
```

### 运行后端测试

```bash
cd backend
pytest
pytest tests/test_documents.py  # 单个测试文件
```

### 前端开发

```bash
cd frontend
npm start          # 开发服务器
npm run build      # 生产构建
npm run dev        # Electron 开发模式
```

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `MIMO_API_KEY` | Mimo API 密钥（默认 Agent 提供商） | 否（至少配一个 LLM） |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 否 |
| `QWEN_API_KEY` | 通义千问 API 密钥 | 否 |
| `GLM_API_KEY` | 智谱 GLM API 密钥 | 否 |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 | 否 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 否 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 否 |
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 | 否 |
| `AGENT_LLM_PROVIDER` | Agent 默认 LLM 提供商 | 否（默认 mimo） |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 通知地址 | 否 |

完整配置请参考 `config/.env.example`。

## 许可证

MIT License
