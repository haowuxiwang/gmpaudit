# GMP合规性审计系统

基于 LangGraph 多Agent + GraphRAG 知识图谱的 GMP 合规性审计系统，支持文档解析、智能审计分析、法规检索、结构化报告生成。

## 功能特性

- **多Agent审计流程**: LangGraph Supervisor 模式，法规专家→风险评估→报告撰写
- **法规知识图谱**: Microsoft GraphRAG 构建 GMP/ICH 法规知识库，语义检索
- **批量文档处理**: 支持 PDF、Word、纯文本格式，RapidOCR 识别
- **多模型支持**: 通过 SiliconFlow API 支持 DeepSeek、Qwen、GLM 等模型
- **结构化报告**: 自动生成 Markdown 格式专业审计报告
- **风险可视化**: 仪表盘展示风险分布和审计趋势

## 技术栈

- **前端**: Electron + React + TypeScript + Ant Design + ECharts
- **后端**: Python FastAPI + SQLAlchemy (async) + SQLite
- **Agent**: LangGraph (StateGraph + Supervisor pattern)
- **知识图谱**: Microsoft GraphRAG + SiliconFlow Embedding (Qwen3-Embedding-8B)
- **文档处理**: PyMuPDF + python-docx + RapidOCR
- **LLM**: SiliconFlow API (DeepSeek-V3.2, Qwen-Plus, GLM-4-Flash)

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
```

### 3. 启动系统

```bash
# Windows
scripts\start.bat

# Linux/Mac
./scripts/start.sh
```

### 4. 访问系统

- 前端界面: http://localhost:3000
- API 文档: http://localhost:8000/docs

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

## 目录结构

```
gmpaudit/
├── agent/             # LangGraph 多Agent系统 (核心审计引擎)
│   ├── agents/        # Agent 节点: supervisor, regulation_expert, risk_assessor, report_writer
│   ├── parsers/       # 文档解析器: PDF, DOCX, TXT
│   ├── tools/         # 工具: embedding, graphrag_tool, regulation_db, risk_matrix
│   ├── config.py      # LLM 配置 (SiliconFlow 等)
│   ├── graph.py       # LangGraph StateGraph 定义
│   └── state.py       # AuditState 共享状态
├── graphrag_index/    # GraphRAG 知识图谱
│   ├── input/         # 法规文本文件
│   └── settings.yaml  # GraphRAG 配置
├── backend/           # FastAPI 后端 (API 网关)
│   └── app/
│       ├── api/       # API 路由 (含 agent_audit)
│       ├── core/      # 配置、数据库、认证
│       ├── models/    # 数据库模型
│       └── services/  # LLM 引擎、文档处理
├── frontend/          # React 前端
│   └── src/
│       ├── pages/     # 8个页面: Dashboard, Documents, AuditTasks, Reports, Settings, Alerts, Login, AuthCallback
│       └── services/  # API 调用封装
├── config/            # .env 配置文件
├── data/              # 运行时数据 (文档、报告)
└── scripts/           # 启动脚本
```

## 许可证

MIT License
