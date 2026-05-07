# GMP 合规性审计系统

基于 LangGraph 多 Agent + GraphRAG 知识图谱的制药行业 GMP 合规性审计系统，支持文档解析、智能审计分析、法规检索和结构化报告生成。

## 核心特性

- **多 Agent 审计流程**：LangGraph Supervisor 模式，法规专家 → 风险评估 → 报告撰写，确定性路由保障可靠性
- **法规知识图谱**：Microsoft GraphRAG 构建 GMP/ICH 法规知识库，语义检索 + 硬编码备用库双重保障
- **批量文档处理**：支持 PDF、Word、纯文本格式，PyMuPDF + RapidOCR 双引擎
- **多 LLM 提供商**：统一适配器模式支持 DeepSeek、Qwen、GLM、SiliconFlow、OpenRouter、Mimo、Anthropic 共 7 个提供商
- **结构化报告**：自动生成 Markdown 格式专业审计报告，按严重程度分组
- **风险可视化**：ECharts 仪表盘展示风险分布和审计趋势
- **飞书深度集成**：OAuth 2.0 登录、JWT 鉴权、Webhook 通知
- **容错降级设计**：GraphRAG → 硬编码法规库、LLM → 模板报告、PDF → OCR 多级降级

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
| **知识图谱** | Microsoft GraphRAG + LanceDB |
| **Embedding** | 本地 BAAI/bge-large-zh-v1.5 (sentence-transformers) |
| **文档处理** | PyMuPDF + python-docx + RapidOCR |
| **LLM 调用** | langchain-openai / langchain-anthropic + httpx |
| **认证** | 飞书 OAuth 2.0 + JWT (PyJWT) + CSRF (itsdangerous) |

## 快速开始

### 1. 配置环境

```bash
cp config/.env.example config/.env
# 编辑配置文件，添加 API 密钥
# 必须配置: SILICONFLOW_API_KEY (用于 LLM 调用和 Embedding)
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
    ├─ regulation_expert: 法规检索 (GraphRAG + 备用DB)
    ├─ risk_assessor: 风险评估 (LLM分析)
    └─ report_writer: 报告生成 (Markdown)
    ↓
结构化审计报告
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 飞书 OAuth 登录 |
| GET | `/api/auth/callback` | OAuth 回调 |
| GET | `/api/documents` | 获取文档列表 |
| POST | `/api/documents/upload` | 上传文档 |
| POST | `/api/documents/{id}/process` | 处理文档 |
| POST | `/api/agent-audit/run` | 运行 Agent 审计 |
| GET | `/api/audit-tasks` | 获取审计任务 |
| GET | `/api/reports` | 获取审计报告 |
| GET | `/api/alerts` | 获取风险警报 |
| GET | `/api/config` | 获取系统配置 |

## 目录结构

```
gmpaudit/
├── agent/             # LangGraph 多Agent系统 (核心审计引擎)
│   ├── agents/        # Agent 节点: supervisor, regulation_expert, risk_assessor, report_writer
│   ├── parsers/       # 文档解析器: PDF, DOCX, TXT
│   ├── tools/         # 工具: embedding, graphrag_tool, regulation_db, risk_matrix
│   ├── prompts/       # LLM Prompt 模板
│   ├── config.py      # LLM 多提供商配置
│   ├── graph.py       # LangGraph StateGraph 定义
│   └── state.py       # AuditState 共享状态
├── graphrag_index/    # GraphRAG 知识图谱
│   ├── input/         # 法规文本文件
│   └── settings.yaml  # GraphRAG 配置
├── backend/           # FastAPI 后端 (API 网关)
│   └── app/
│       ├── api/       # API 路由 (含 agent_audit)
│       ├── core/      # 配置、数据库、认证
│       ├── models/    # 数据库模型 (6张表)
│       └── services/  # LLM 引擎、文档处理
├── frontend/          # React 前端 (Electron 桌面应用)
│   └── src/
│       ├── pages/     # 8个页面: Dashboard, Documents, AuditTasks, Reports, Settings, Alerts, Login, AuthCallback
│       └── services/  # API 调用封装
├── config/            # .env 配置文件、系统配置、审计规则
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
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 | 是 |
| `DATABASE_URL` | 数据库连接字符串 | 否 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 是 |
| `FEISHU_APP_ID` | 飞书应用 ID | 否 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 否 |
| `FEISHU_REDIRECT_URI` | 飞书回调地址 | 否 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 地址 | 否 |

完整配置请参考 `config/.env.example`。

## 许可证

MIT License
