# AuditBee 平台化蓝图：从 GMP 工具到通用审计 AI 平台

> 日期: 2026-05-28
> 版本: v1.0
> 作者: 基于代码库深度分析生成

---

## 执行摘要

AuditBee 当前是一个针对中国 GMP 合规审计的本地桌面应用，技术架构质量出乎意料地高。核心发现：**行业耦合面极窄** — 仅 3 个 prompt 模板、1 个法规数据库文件、1 个知识图谱输入目录、6 行文档类型启发式规则。这意味着从 GMP 专用工具到通用审计平台的路径比预期短得多。

**关键结论：**
- 技术可行性: **高** — 耦合面窄，解耦成本可控（预估 2-4 周）
- 市场机会: **中高** — 合规审计是高价值、高痛点场景，但市场教育成本不可忽视
- 商业模式: **混合模式** — 本地 license + SaaS 订阅的双轨策略最稳妥
- 最大风险: **LLM 可靠性** — 审计场景对准确性要求极高，LLM 幻觉是硬伤

---

## 1. 技术架构评估

### 1.1 架构优势

#### LangGraph 工作流设计（优秀）

当前 Supervisor 模式是整个系统最亮眼的设计。关键代码位于 `agent/graph.py`:

```
Flow: parse_doc -> supervisor -> regulation_expert -> supervisor
                               -> risk_assessor    -> supervisor
                               -> report_writer    -> supervisor -> END
```

**优势分析：**
- **确定性路由**：`agent/agents/supervisor.py` 使用状态标志（`regulation_checked`, `risk_assessed`, `report_generated`）而非 LLM 决策做路由，避免了 LLM 路由的不可预测性
- **迭代保护**：`iteration > 10` 硬上限防止无限循环
- **错误传播控制**：每个 agent 独立 catch 异常，不会级联崩溃
- **可观测性**：`agent/trace.py` 提供完整的 PipelineTrace，记录每个节点的延迟、LLM 调用详情、KG 查询结果

这是生产级的 agent 架构，比大多数 LangGraph demo 项目成熟得多。

#### 优雅降级策略（优秀）

系统在多个层面实现了降级：

| 层级 | 主路径 | 降级路径 | 代码位置 |
|------|--------|----------|----------|
| 法规检索 | LightRAG 知识图谱 | 硬编码法规 DB（22 条） | `agent/agents/regulation_expert.py:23-79` |
| LLM 调用 | 默认 provider | `get_llm_with_fallback()` 遍历所有 provider | `agent/config.py:201-222` |
| LLM 重试 | 正常响应 | 指数退避重试（区分可重试/不可重试错误） | `agent/config.py:268-355` |
| 报告生成 | LLM 生成 | 模板化 fallback 报告 | `agent/agents/report_writer.py:76-91` |
| 文档处理 | Stuff 策略（单次调用） | Map-Reduce（分块分析 + 去重） | `agent/tools/document_chunker.py` |

这种设计对于桌面应用至关重要 — 用户可能配置了错误的 API key，或者 LLM 服务临时不可用，系统仍然能给出有用的结果。

#### SSE 实时推送架构（良好）

`backend/app/services/event_bus.py` 实现了基于内存的 pub/sub 模式：

- TaskRunner 通过 `_publish()` 推送事件到 EventBus
- EventBus 为每个 SSE 连接维护独立的 `asyncio.Queue`
- 30 秒 keepalive 心跳
- `DONE_SENTINEL` 确保连接正确终止
- 10 分钟 TTL 自动清理过期订阅

这比 DB 轮询方案高效得多，且支持多客户端同时监听同一任务。

#### 任务管理系统（良好）

`backend/app/services/task_runner.py` 实现了：
- 信号量控制并发（`max_concurrency`）
- 任务取消（`CancelledError` 独立处理）
- 审阅门控（`AWAITING_REVIEW` 状态，高风险发现触发）
- 进程重启恢复（`startup_recover`）
- 僵尸任务检测

### 1.2 架构弱点

#### SQLite 单点限制

当前使用 `sqlite+aiosqlite`，存在以下限制：
- **并发写入**：SQLite 写锁粒度是数据库级别，高并发场景会阻塞
- **单用户**：无法支持多用户同时操作
- **无事务隔离**：读写互相阻塞

**影响评估**：对于桌面单用户场景，SQLite 完全够用。但如果走向 SaaS，必须迁移到 PostgreSQL。

#### EventBus 内存丢失

EventBus 是纯内存实现，进程重启后所有事件丢失。虽然 `startup_recover` 能恢复任务状态，但中间事件（如 agent thinking 进度）不可恢复。

**影响评估**：桌面场景可接受。SaaS 场景需要 Redis/Kafka 持久化。

#### 无认证机制

所有 API 端点完全开放（`backend/app/main.py` 无 auth middleware）。设计文档明确说明"本地桌面应用，无需认证"。

**影响评估**：桌面场景合理。SaaS 场景必须从零构建认证体系。

#### LLM 可靠性硬伤

这是整个系统最大的技术风险。当前 LLM 调用链路：

1. Agent prompt 模板（中文） → LLM → JSON 输出 → `parse_llm_json()` 解析
2. 依赖 LLM 输出严格 JSON 格式
3. `agent/tools/json_parser.py` 需要处理各种格式异常

**问题**：
- LLM 输出 JSON 格式不稳定（特别是国产模型）
- 审计场景对准确性要求极高，LLM 幻觉可能导致误判
- 中文 prompt 对国产模型效果好，但切换到英文 prompt 后效果可能下降

### 1.3 耦合分析

这是最关键的分析 — 哪些是通用的，哪些是行业特定的。

#### 通用组件（85%+ 代码）

| 组件 | 文件 | 说明 |
|------|------|------|
| LangGraph 工作流 | `agent/graph.py` | 4 节点 supervisor 模式，完全通用 |
| AuditState 定义 | `agent/state.py` | 状态字段名通用（findings, risk_score 等） |
| Supervisor 路由 | `agent/agents/supervisor.py` | 基于状态标志的确定性路由 |
| Risk Assessor 逻辑 | `agent/agents/risk_assessor.py` | 分析 + 评分，prompt 可替换 |
| Report Writer 逻辑 | `agent/agents/report_writer.py` | 报告生成，模板可替换 |
| Document Chunker | `agent/tools/document_chunker.py` | 中文/Markdown 分块，完全通用 |
| Risk Matrix | `agent/tools/risk_matrix.py` | 评分算法通用 |
| Prompt Loader | `agent/tools/prompt_loader.py` | 模板加载器，完全通用 |
| LLM 配置系统 | `agent/config.py` | 8 provider 支持，完全通用 |
| LLM 重试逻辑 | `agent/config.py:268-355` | 指数退避，完全通用 |
| Pipeline Trace | `agent/trace.py` | 可观测性，完全通用 |
| Task Runner | `backend/app/services/task_runner.py` | 任务管理，完全通用 |
| Event Bus | `backend/app/services/event_bus.py` | SSE 推送，完全通用 |
| DB Models | `backend/app/models/*.py` | 通用审计数据模型 |
| Frontend | `frontend/src/**` | UI 组件，主题可配置 |
| Notification | `backend/app/services/notification.py` | 飞书通知，可扩展 |

#### 行业特定组件（15% 代码）

| 组件 | 文件 | 耦合点 | 解耦难度 |
|------|------|--------|----------|
| Regulation Expert Prompt | `agent/prompts/regulation_expert.txt` | 中文 GMP 专家角色、GMP 领域术语 | 低 — 替换为模板变量 |
| Risk Assessor Prompt | `agent/prompts/risk_assessor.txt` | GMP 审计员角色、GMP 问题类型 | 低 — 替换为模板变量 |
| Report Writer Prompt | `agent/prompts/report_writer.txt` | GMP 报告格式、CAPA 术语 | 低 — 替换为模板变量 |
| Regulation DB | `agent/tools/regulation_db.py` | 22 条中国 GMP 硬编码法规 | 低 — 改为可配置数据源 |
| Doc Type Heuristics | `agent/graph.py:89-96` | 6 行中文关键词匹配 | 低 — 改为可配置规则 |
| KG Input Files | `graphrag_index/input/*.txt` | 16 个 GMP 章节文件 | 低 — 按行业替换 |
| Fallback Keywords | `agent/agents/regulation_expert.py:69,129` | 硬编码 GMP 关键词 | 低 — 改为配置 |

**核心发现**：所有行业特定组件的解耦难度都是"低"。没有深层架构耦合，只有浅层配置耦合。

### 1.4 技术栈评估

| 技术 | 当前选择 | 替代方案 | 评估 |
|------|----------|----------|------|
| Web 框架 | FastAPI | Django, Flask | **最优选择** — async 原生支持，性能好，类型安全 |
| Agent 框架 | LangGraph | CrewAI, AutoGen, LangChain Agent | **合理选择** — 确定性工作流比 LLM 路由更可靠 |
| 知识图谱 | LightRAG | LlamaIndex, Haystack, 自建 RAG | **合理选择** — 本地 embedding + 图检索，但文档较少 |
| 前端 | React + Ant Design | Vue, Next.js | **合理选择** — 生态成熟，Ant Design 企业级组件丰富 |
| 桌面 | Electron | Tauri, PyInstaller GUI | **可接受** — Electron 包体大但跨平台好 |
| 数据库 | SQLite | PostgreSQL, MySQL | **桌面合理，SaaS 不足** |
| Embedding | BAAI/bge-large-zh-v1.5 | OpenAI Embedding, Jina | **合理选择** — 本地运行，无 API 依赖，中文效果好 |

---

## 2. 通用化路径

### 2.1 行业配置层设计

核心思路：**将所有行业特定内容抽取为可配置的"行业包"（Industry Pack）**。

#### 配置架构

```
config/
  industries/
    gmp_china/
      manifest.yaml          # 行业元数据
      prompts/
        regulation_expert.txt
        risk_assessor.txt
        report_writer.txt
      regulations/
        fallback_db.json      # 替代硬编码的 GMP_REGULATIONS
        keywords.json         # 文档类型启发式关键词
      kg_input/
        gmp_china_ch01_general.txt
        ...
    iso_13485/
      manifest.yaml
      prompts/
        ...
      regulations/
        ...
      kg_input/
        ...
    haccp/
      ...
```

#### manifest.yaml 结构

```yaml
id: gmp_china
name: 中国GMP合规审计
version: "1.0"
language: zh-CN
description: 中国药品生产质量管理规范（2010年修订版）合规审计

# 文档类型定义
document_types:
  deviation:
    name: 偏差分析
    keywords: ["偏差", "deviation", "非计划"]
  change_control:
    name: 变更控制
    keywords: ["变更", "change control"]
  sop:
    name: SOP合规
    keywords: []  # 默认类型

# 风险等级定义
risk_levels:
  high:
    label: 高风险
    score_threshold: 80
  medium:
    label: 中风险
    score_threshold: 50
  low:
    label: 低风险

# Finding 类型定义
finding_types:
  - id: compliance
    name: 合规风险
  - id: logic_flaw
    name: 逻辑缺陷
  - id: inconsistency
    name: 不一致
  - id: missing_info
    name: 信息缺失

# Prompt 模板变量
prompt_variables:
  expert_role: "资深的GMP法规专家，精通中国GMP（2010年修订版）、ICH Q7/Q9/Q10等指导原则"
  auditor_role: "资深的GMP审计员和风险评估专家"
  report_role: "专业的GMP审计报告撰写专家"
  regulation_name: "GMP"
  report_title: "GMP合规性审计报告"
```

#### 实现方案

**Step 1: Prompt 模板化**（工作量: 2-3 天）

将 `agent/prompts/*.txt` 中的硬编码文本替换为 Jinja2 模板变量：

当前 `regulation_expert.txt`:
```
你是一位资深的GMP法规专家，精通中国GMP（2010年修订版）、ICH Q7/Q9/Q10等指导原则。
请分析以下GMP文档内容，找出所有相关的法规条款要求。
```

改为:
```
你是一位{{ expert_role }}。
请分析以下{{ regulation_name }}文档内容，找出所有相关的法规条款要求。
```

`agent/tools/prompt_loader.py` 已经有缓存机制，只需扩展为支持行业目录查找。

**Step 2: Regulation DB 可配置化**（工作量: 1-2 天）

`agent/tools/regulation_db.py` 当前硬编码 22 条 GMP 法规。改为：
1. 从 `config/industries/{industry}/regulations/fallback_db.json` 加载
2. 保持 `search_regulations()` 接口不变
3. 启动时按当前行业配置加载对应数据

**Step 3: 文档类型启发式可配置化**（工作量: 0.5 天）

`agent/graph.py:89-96` 的 6 行关键词匹配改为从 manifest.yaml 的 `document_types` 读取。

**Step 4: 行业选择 UI**（工作量: 2-3 天）

在 Settings 页面添加行业选择器，切换行业时：
1. 重新加载 prompt 模板
2. 重新加载 regulation DB
3. 可选：重新构建知识图谱

### 2.2 多租户架构考虑

如果走向 SaaS，需要考虑：

#### 数据隔离方案

| 方案 | 隔离级别 | 复杂度 | 适用场景 |
|------|----------|--------|----------|
| Schema-per-tenant | PostgreSQL schema | 中 | 中型 SaaS（<100 租户） |
| Row-level security | 行级策略 | 低 | 小型 SaaS（<50 租户） |
| Database-per-tenant | 独立数据库 | 高 | 大型企业客户 |

**推荐**：Phase 2 使用 Row-level security（添加 `tenant_id` 字段），Phase 3 按需升级到 Schema-per-tenant。

#### 知识图谱隔离

每个租户/行业需要独立的知识图谱索引。当前 LightRAG 使用文件系统存储（`WORKING_DIR`），多租户方案：

```
data/
  tenants/
    tenant_001/
      kg_output/     # 独立 LightRAG 索引
      kg_input/      # 行业法规文件
      documents/     # 审计文档
    tenant_002/
      ...
```

### 2.3 知识图谱管理

#### 当前流程

1. 法规文本文件放入 `graphrag_index/input/`（16 个 GMP 章节文件）
2. `lightrag_tool.py:build_index()` 构建索引
3. 索引产物存入 `graphrag_index/lightrag_output/`
4. 查询时通过 `lightrag_search()` 语义检索

#### 通用化方案

1. **按行业组织输入文件**：`config/industries/{id}/kg_input/`
2. **索引构建 API 增强**：支持按行业构建/重建索引
3. **索引切换**：运行时切换活跃行业时加载对应索引
4. **用户自定义法规上传**：当前已有 `POST /kg/documents/upload`，扩展为支持行业分类

---

## 3. 商业化分析

### 3.1 目标市场

| 行业 | 法规标准 | 市场规模（中国） | 痛点程度 | 进入难度 |
|------|----------|------------------|----------|----------|
| 制药（GMP） | 中国GMP, ICH, FDA 21 CFR | ~8000 家药企 | 极高 | 低（当前产品） |
| 医疗器械 | ISO 13485, FDA QSR | ~30000 家企业 | 高 | 中 |
| 食品安全 | HACCP, FDA FSMA, GB 标准 | ~150000 家企业 | 高 | 中 |
| 金融合规 | SOX, 巴塞尔III, 中国银保监 | ~500 家金融机构 | 极高 | 高 |
| 化工 | ISO 9001, REACH | ~20000 家企业 | 中 | 中 |
| 汽车 | IATF 16949 | ~10000 家企业 | 中 | 中 |

**优先级排序**：
1. **制药 GMP** — 当前产品，验证核心循环
2. **医疗器械 ISO 13485** — 与 GMP 高度相似，复用率 >80%
3. **食品安全 HACCP** — 市场大，法规体系成熟

### 3.2 竞品分析

#### 直接竞品

| 产品 | 定位 | 优势 | 劣势 |
|------|------|------|------|
| Veeva Vault QMS | 制药质量管理 SaaS | 行业标杆，客户基数大 | 贵（$100K+/年），重，非 AI 原生 |
| MasterControl | 质量管理平台 | 功能全面 | 传统软件，无 AI 审计能力 |
| Qualio | 中小药企 QMS | 轻量，云原生 | 无自动审计功能 |
| Sparta Systems (TrackWise) | 企业级 QMS | 深度集成 | 复杂，昂贵 |

#### 间接竞品

| 产品 | 定位 | 与 AuditBee 的差异 |
|------|------|---------------------|
| ChatGPT/Claude + 手动 prompt | 通用 AI | 无结构化工作流，无知识图谱，无持久化 |
| 自建 LangChain 方案 | 开发者工具 | 需要工程团队，非产品化 |
| 传统审计咨询公司 | 人工服务 | 贵，慢，不可规模化 |

#### 竞争定位

AuditBee 的独特定位：**AI 原生的合规审计自动化工具**。

现有 QMS 厂商的核心能力是"流程管理"（workflows, document control, CAPA tracking），而不是"智能分析"。AuditBee 的核心能力正好相反 — 自动分析文档、识别合规问题、生成审计报告。

**最佳策略不是替代 QMS，而是作为 QMS 的"AI 审计引擎"插件。**

### 3.3 定价模型

#### 方案 A: 本地 License

| 版本 | 价格 | 功能 |
|------|------|------|
| 免费版 | ¥0 | 单文档审计，无知识图谱，水印报告 |
| 专业版 | ¥2,999/年 | 无限审计，知识图谱，飞书通知，PDF 导出 |
| 企业版 | ¥9,999/年 | 多行业支持，自定义法规库，API 集成 |

**优势**：无服务器成本，用户数据本地存储（制药行业对数据安全敏感）
**劣势**：收入天花板低，无法规模化

#### 方案 B: SaaS 订阅

| 版本 | 价格 | 功能 |
|------|------|------|
| 免费版 | ¥0 | 5 次/月审计，基础报告 |
| 专业版 | ¥499/月 | 无限审计，全行业支持，团队协作 |
| 企业版 | ¥1,999/月 | 自定义法规库，API，SSO，专属支持 |

**优势**：经常性收入，规模化潜力
**劣势**：服务器成本，数据安全顾虑，合规认证要求

#### 方案 C: 混合模式（推荐）

| 产品形态 | 价格 | 目标客户 |
|----------|------|----------|
| 本地桌面版 | ¥2,999/年 | 数据敏感的大中型药企 |
| 云端 SaaS 版 | ¥499/月 | 中小企业，多行业用户 |
| API 服务 | ¥0.5/次审计 | 开发者，集成商 |

**推荐理由**：
1. 制药行业对数据安全极度敏感，纯 SaaS 会流失大客户
2. 中小企业更倾向低门槛的 SaaS
3. API 服务为未来 QMS 集成铺路

### 3.4 护城河分析

| 护城河类型 | 强度 | 说明 |
|------------|------|------|
| 数据网络效应 | 中 | 用户越多 → 法规知识库越完善 → 审计质量越高 |
| 技术壁垒 | 低-中 | LangGraph + LightRAG 技术门槛不高，但工程化细节有壁垒 |
| 行业知识壁垒 | 高 | 法规解读、审计逻辑需要领域专家积累 |
| 品牌/信任 | 中 | 审计工具需要高信任度，先发优势明显 |
| 合规认证 | 高 | 如果获得药监局认可或行业认证，构成强壁垒 |

**最可防御的护城河是"行业知识 + 合规认证"的组合。**

---

## 4. 产品蓝图

### 4.1 Phase 1: GMP 专用工具验证（当前 → 3 个月）

**目标**：验证核心循环，获取初始用户反馈

**已完成**：
- [x] LangGraph 4-agent 工作流
- [x] LightRAG 知识图谱（16 个 GMP 章节）
- [x] 8 LLM provider 支持
- [x] SSE 实时进度推送
- [x] 任务管理（创建、运行、取消、审阅门控）
- [x] 飞书通知集成
- [x] PyInstaller 桌面打包
- [x] 完整的 pipeline trace 可观测性

**待完成**（Phase 1 收尾）：
- [ ] 用户测试：邀请 3-5 家药企 QA 试用
- [ ] Bug 修复：根据用户反馈迭代
- [ ] 文档完善：用户手册、部署指南
- [ ] 性能优化：大文档处理速度

### 4.2 Phase 2: 行业模板系统（3-6 个月）

**目标**：支持 2-3 个行业，建立可扩展架构

**里程碑**：

| 时间 | 里程碑 | 交付物 |
|------|--------|--------|
| M1 | 行业配置层重构 | Industry Pack 架构，GMP 迁移为第一个 pack |
| M2 | 医疗器械行业包 | ISO 13485 prompts + regulations + KG |
| M3 | 食品安全行业包 | HACCP prompts + regulations + KG |
| M4 | 行业切换 UI | Settings 页面行业选择器 |
| M5 | 自定义法规上传 | 用户可上传自己的法规文件构建 KG |
| M6 | Beta 测试 | 3 个行业各 3-5 个测试用户 |

**技术工作拆解**：

1. **Prompt 模板系统**（M1，1 周）
   - Jinja2 模板引擎集成
   - manifest.yaml schema 定义
   - 从 `agent/prompts/` 迁移到 `config/industries/gmp_china/prompts/`

2. **Regulation DB 可配置化**（M1，3 天）
   - JSON 格式法规数据库
   - 按行业加载机制
   - `search_regulations()` 接口保持不变

3. **文档类型启发式可配置化**（M1，1 天）
   - `agent/graph.py:89-96` 改为从 manifest 读取关键词

4. **知识图谱多行业支持**（M2，1 周）
   - 按行业组织 KG input/output 目录
   - 行业切换时加载对应索引
   - 构建 API 支持指定行业

5. **医疗器械行业包**（M2，1 周）
   - ISO 13485 prompt 模板
   - ISO 13485 法规数据库（~30 条核心条款）
   - ISO 13485 KG input 文件

6. **食品安全行业包**（M3，1 周）
   - HACCP prompt 模板
   - HACCP/GB 标准法规数据库
   - HACCP KG input 文件

### 4.3 Phase 3: SaaS 平台（6-12 个月）

**目标**：多租户 SaaS 平台，支持多行业

**里程碑**：

| 时间 | 里程碑 | 交付物 |
|------|--------|--------|
| M7 | 数据库迁移 | SQLite → PostgreSQL |
| M8 | 认证系统 | JWT auth, 用户注册, 角色权限 |
| M9 | 多租户架构 | Tenant isolation, Row-level security |
| M10 | 云部署 | Docker, K8s, CI/CD |
| M11 | 计费系统 | Stripe/支付宝集成, 用量计费 |
| M12 | 正式上线 | 公开发布, 营销启动 |

**技术工作拆解**：

1. **数据库迁移**（M7，2 周）
   - SQLAlchemy model 适配 PostgreSQL
   - 数据迁移脚本
   - 连接池配置

2. **认证系统**（M8，2 周）
   - JWT token 认证
   - 用户注册/登录
   - RBAC 角色权限（admin, auditor, viewer）

3. **多租户架构**（M9，2 周）
   - `tenant_id` 字段添加到所有 model
   - Row-level security policies
   - 租户隔离的 KG 索引

4. **云部署**（M10，2 周）
   - Docker 化（backend + frontend + worker）
   - Kubernetes 部署
   - CI/CD pipeline

5. **计费系统**（M11，1 周）
   - 用量追踪（审计次数、文档数量）
   - Stripe/支付宝集成
   - 套餐管理

---

## 5. 风险评估

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| LLM 输出格式不稳定 | 高 | 高 | `json_parser.py` 已有容错；增加输出验证层；few-shot 示例强化 |
| LLM 幻觉导致误判 | 中 | 极高 | 人审门控（已实现）；置信度评分；法规引用验证 |
| 知识图谱质量不足 | 中 | 高 | 持续扩充法规库；用户反馈循环；专业审核 |
| 法规更新滞后 | 高 | 中 | 建立法规更新监控机制；社区贡献法规库 |
| LLM API 成本 | 中 | 中 | 本地小模型方案；缓存机制（已有 LLM response cache） |
| 大文档处理超时 | 低 | 中 | Map-Reduce 已实现；异步处理；进度反馈 |

#### LLM 可靠性专项分析

这是最大的技术风险。当前系统对 LLM 的依赖点：

1. **Regulation Expert**：LLM 分析文档 → 输出法规关联 JSON
2. **Risk Assessor**：LLM 分析文档 + 法规 → 输出 findings JSON
3. **Report Writer**：LLM 生成 Markdown 报告

每个环节都可能产生：
- **格式错误**：JSON 解析失败（`json_parser.py` 已有容错）
- **内容幻觉**：编造不存在的法规条款
- **遗漏**：未识别出真正的合规问题
- **误判**：将合规内容标记为不合规

**缓解策略**：
1. 当前的人审门控（`AWAITING_REVIEW`）是正确的防线
2. 增加"法规引用验证"：LLM 输出的法规条款必须能在法规库中找到
3. 增加"置信度评分"：LLM 对每个 finding 的置信度
4. 长期：建立人工标注数据集，微调专用审计模型

### 5.2 市场风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 大厂入场（Veeva, MasterControl 加 AI） | 中 | 高 | 速度优势；专注 AI 审计引擎；避免正面竞争 |
| 用户不愿为 AI 审计付费 | 中 | 高 | 免费版引流；ROI 量化（节省人工审计时间） |
| 数据安全顾虑 | 高 | 中 | 本地部署方案；数据不出本地；安全认证 |
| 市场教育成本高 | 高 | 中 | 内容营销；行业会议；KOL 合作 |
| 法规解读争议 | 中 | 高 | 免责声明；人工审核兜底；专家顾问团 |

#### 制药行业特殊挑战

制药行业对新技术的接受度相对保守：
- **验证要求**：GMP 要求所有工具经过验证（IQ/OQ/PQ）
- **数据完整性**：ALCOA+ 原则，审计追踪
- **监管审查**：药监局可能对 AI 审计工具提出额外要求

**应对**：将 AuditBee 定位为"辅助工具"而非"替代人工审计"，降低监管风险。

### 5.3 运营风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 技术支持负担 | 高 | 中 | 完善文档；社区支持；分级支持体系 |
| 法规知识维护成本 | 高 | 中 | 社区贡献模式；自动化法规更新抓取 |
| 团队能力不足 | 中 | 高 | 优先招聘有法规背景的产品经理 |
| 现金流压力 | 中 | 高 | 先本地 license 验证；控制 SaaS 投入节奏 |

---

## 6. Go/No-Go 决策矩阵

### 6.1 评分标准

| 维度 | 权重 | 评分标准 |
|------|------|----------|
| 技术可行性 | 25% | 架构成熟度、解耦难度、技术风险 |
| 市场机会 | 25% | 市场规模、痛点程度、竞争格局 |
| 商业可行性 | 20% | 定价空间、获客成本、盈利路径 |
| 团队能力 | 15% | 技术能力、行业知识、执行力 |
| 时机 | 15% | AI 热度、监管趋势、竞争窗口 |

### 6.2 评分结果

| 维度 | 权重 | 得分 (1-10) | 加权分 |
|------|------|-------------|--------|
| 技术可行性 | 25% | 8 | 2.00 |
| 市场机会 | 25% | 7 | 1.75 |
| 商业可行性 | 20% | 6 | 1.20 |
| 团队能力 | 15% | 5 | 0.75 |
| 时机 | 15% | 8 | 1.20 |
| **总分** | **100%** | | **6.90** |

### 6.3 决策结论

**总分 6.90/10 — 有条件 Go。**

| 条件 | 说明 |
|------|------|
| 必须满足 | Phase 1 用户验证成功（3+ 家药企给出积极反馈） |
| 必须满足 | 至少 1 人有制药行业背景（全职或顾问） |
| 建议满足 | 有 6 个月以上的现金流储备 |
| 可选 | 获得行业 KOL 背书或种子客户 |

### 6.4 关键假设验证清单

在全面投入之前，必须验证以下假设：

| # | 假设 | 验证方法 | 验证时间 |
|---|------|----------|----------|
| 1 | QA 人员愿意使用 AI 工具辅助审计 | 用户访谈 + 试用反馈 | 2 周 |
| 2 | LLM 审计结果的准确率 >70% | 人工对比评估 | 1 个月 |
| 3 | 用户愿意为审计 AI 付费 | 预售/LOI 收集 | 1 个月 |
| 4 | 法规知识库能覆盖 80% 常见场景 | 测试集评估 | 2 周 |
| 5 | 单次审计成本 <¥1（LLM API） | 成本核算 | 1 天 |

---

## 7. 行动建议

### 立即行动（本周）

1. **用户访谈**：联系 3-5 家药企 QA 部门，了解当前审计流程和痛点
2. **竞品体验**：注册 Veeva Vault / Qualio 的 demo，体验竞品
3. **准确率评估**：准备 10 份真实 GMP 文档，用 AuditBee 审计，人工评估准确率

### 短期行动（1 个月内）

1. **Phase 1 收尾**：修复已知 bug，完善用户手册
2. **种子用户获取**：通过行业社群、LinkedIn 获取首批试用用户
3. **定价验证**：向种子用户询问付费意愿和价格敏感度

### 中期行动（3 个月内）

1. **行业配置层重构**：实施 2.1 节的通用化方案
2. **医疗器械行业包**：扩展第二个行业
3. **内容营销**：发布"AI 审计"相关的行业文章/案例

---

## 附录 A: 代码文件索引

| 文件路径 | 说明 | 行业耦合度 |
|----------|------|------------|
| `agent/state.py` | AuditState 定义 | 通用 |
| `agent/graph.py` | LangGraph 工作流 | 低（6 行启发式） |
| `agent/agents/supervisor.py` | Supervisor 路由 | 通用 |
| `agent/agents/regulation_expert.py` | 法规专家 Agent | 低（fallback 关键词） |
| `agent/agents/risk_assessor.py` | 风险评估 Agent | 通用 |
| `agent/agents/report_writer.py` | 报告生成 Agent | 通用 |
| `agent/prompts/*.txt` | 3 个 prompt 模板 | 高（纯 GMP） |
| `agent/tools/regulation_db.py` | 法规数据库 | 高（22 条 GMP） |
| `agent/tools/risk_matrix.py` | 风险评分 | 通用 |
| `agent/tools/document_chunker.py` | 文档分块 | 通用 |
| `agent/tools/prompt_loader.py` | 模板加载 | 通用 |
| `agent/tools/lightrag_tool.py` | 知识图谱 | 低（路径配置） |
| `agent/config.py` | LLM 配置 | 通用 |
| `agent/trace.py` | Pipeline trace | 通用 |
| `backend/app/services/task_runner.py` | 任务管理 | 通用 |
| `backend/app/services/event_bus.py` | SSE 推送 | 通用 |
| `backend/app/services/notification.py` | 飞书通知 | 通用（可扩展） |
| `backend/app/core/config.py` | 应用配置 | 通用 |
| `backend/app/core/paths.py` | 路径解析 | 通用 |
| `backend/app/models/*.py` | 数据库模型 | 通用 |
| `frontend/src/**` | 前端代码 | 通用（中文 locale） |
| `graphrag_index/input/*.txt` | 16 个 GMP 法规文件 | 高（纯 GMP） |

## 附录 B: 行业扩展工作量估算

| 行业 | Prompt 编写 | 法规数据库 | KG Input | 测试验证 | 总计 |
|------|-------------|------------|----------|----------|------|
| 医疗器械 ISO 13485 | 2 天 | 2 天 | 3 天 | 3 天 | 10 天 |
| 食品安全 HACCP | 2 天 | 3 天 | 3 天 | 3 天 | 11 天 |
| 金融合规 SOX | 3 天 | 3 天 | 5 天 | 5 天 | 16 天 |
| 化工 ISO 9001 | 2 天 | 2 天 | 3 天 | 3 天 | 10 天 |

注：以上估算假设已有 Industry Pack 架构，不含架构搭建时间。
