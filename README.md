# GMP合规性审计系统

基于LLM的GMP合规性审计与模拟审计员系统，支持批量文档处理、智能审计分析、结构化报告生成。

## 功能特性

- **批量文档处理**: 支持PDF、Word、图片格式，自动OCR识别
- **智能审计分析**: 利用LLM模拟审计员，识别逻辑漏洞、合规性风险
- **多模型支持**: 支持DeepSeek、通义千问、智谱GLM等中国开源模型
- **结构化报告**: 自动生成专业审计报告
- **风险可视化**: 仪表盘展示风险分布

## 技术栈

- **前端**: Electron + React + TypeScript + Ant Design
- **后端**: Python FastAPI
- **数据库**: SQLite + ChromaDB
- **OCR**: PaddleOCR
- **LLM**: DeepSeek API

## 快速开始

### 1. 配置环境

```bash
cp config/.env.example config/.env
# 编辑配置文件，添加API密钥
```

### 2. 安装依赖

```bash
# 后端依赖
cd backend
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install
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
- API文档: http://localhost:8000/docs

## 目录结构

```
gmpaudit/
├── frontend/          # 前端代码
├── backend/           # 后端代码
├── config/            # 配置文件
├── data/              # 数据目录
├── scripts/           # 脚本文件
└── docs/              # 文档
```

## 许可证

MIT License
