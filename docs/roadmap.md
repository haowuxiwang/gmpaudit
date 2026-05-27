# AuditBee 改进路线图

本文档记录项目已知限制和后续改进计划，按优先级排列。

---

## P0 - 当前版本已知限制（v1.0.3）

用户需知晓的当前版本限制：

| 编号 | 限制 | 影响 | 规避方案 |
|------|------|------|----------|
| P0-1 | ~~文档内容截断 3000 字符~~ | ~~长 SOP/偏差报告末尾内容丢失~~ | 已通过 Map-Reduce 策略解决 (v1.1) |
| P0-2 | 审批操作重新执行整个 agent 链路 | 2x LLM 成本，结果可能不一致 | 使用 auto_approve 跳过审批 |
| P0-3 | 嵌入模型需单独下载（1.3GB） | 无网络环境无法使用知识图谱 | 预下载 model/ 目录 |
| P0-4 | risk_score=-1 表示评估失败 | 用户可能误解为真实分数 | 查看报告中的"评估失败"标记 |
| P0-5 | ~~LightRAG LLM 调用无重试机制~~ | ~~知识图谱查询偶发失败~~ | httpx client 复用 + agent LLM 重试已实现 (v1.1) |
| P0-6 | 单文档处理串行执行 | 多文档审计耗时线性增长 | 逐个文档审计 |

---

## P1 - 近期改进（v1.1 目标）

### 1.1 数据闭环增强

| 编号 | 改进项 | 描述 | 预期效果 |
|------|--------|------|----------|
| P1-1 | ~~文档分块策略~~ | ~~替代 3000 字符截断，按段落/章节分块送入 LLM~~ | Done: 结构感知分块 + stuff/map_reduce 策略自动选择 |
| P1-2 | 审计结果缓存 | 相同文档+相同配置的审计结果缓存，避免重复 LLM 调用 | 降低 LLM 成本 |
| P1-3 | 审批不重跑链路 | approve 操作直接完成任务，不重新执行 agent 链路 | 节省 50% LLM 成本 |
| P1-4 | 文档处理失败重试 | 添加手动重新处理按钮 + 自动重试机制 | 提升用户体验 |

### 1.2 Human-in-the-Loop 增强

| 编号 | 改进项 | 描述 | 预期效果 |
|------|--------|------|----------|
| P1-5 | Finding 级别审批 | 支持逐条 findings 审批/拒绝/修改 | 精细化质量控制 |
| P1-6 | 审批批注 | 审批时添加批注说明，记录在 audit_log 中 | 审计追溯 |
| P1-7 | 审计前确认 | 触发审计前显示预估 LLM 调用次数和成本 | 用户知情决策 |

### 1.3 性能优化

| 编号 | 改进项 | 描述 | 预期效果 |
|------|--------|------|----------|
| P1-8 | ~~LightRAG httpx client 复用~~ | ~~使用单例 AsyncClient 替代每次新建~~ | Done |
| P1-9 | ~~Prompt 模板缓存~~ | ~~模块级缓存 prompt 模板，避免每次读磁盘~~ | Done: agent/tools/prompt_loader.py |
| P1-10 | Per-LLM-call timeout | 每个 LLM 调用独立超时（60s），而非全局 300s | 更精确的超时控制 |
| P1-11 | LightRAG LLM 调用重试 | 为 LightRAG 的 httpx 调用添加重试机制 | 提升知识图谱可靠性 |
| P1-12 | ~~启动器模型名称配置~~ | ~~启动动器支持自定义模型名称，无需进入设置页~~ | Done |
| P1-13 | ~~设置批量保存优化~~ | ~~.env 文件批量写入，避免逐 key 重写~~ | Done |
| P1-14 | 文件夹扫描 / 自动发现 | 配置扫描目录，自动导入新文档并创建审计任务 | 减少手动上传，环境感知 |
| P1-15 | 审计记忆积累 | 将审计发现持久化为 JSONL，供未来审计上下文参考 | 跨审计知识积累 |
| P1-16 | Map-Reduce 文档分析 | 长文档分块 → 逐块 LLM 分析 → 聚合 findings | 完整覆盖 8-50 页文档 |
| P1-17 | 结构感知分块 | 按章节标题/段落分块，携带章节路径元数据 | findings 可追溯到具体章节 |
| P1-18 | 审计-KG 分块联动 | 每个 chunk 独立查询 LightRAG，法规匹配覆盖全文 | 法规匹配覆盖率提升 |
| P1-19 | 策略自动选择 | ≤60K 字符用 Stuff，>60K 用 Map-Reduce | 平衡成本与覆盖率 |

---

## P2 - 中期改进（v1.2 目标）

### 2.1 功能丰富

| 编号 | 改进项 | 描述 |
|------|--------|------|
| P2-1 | Observability/Tracing | 集成 LangSmith 或 OpenTelemetry，追踪 agent 调用链 |
| P2-2 | Token 用量统计 | 记录每次审计的 LLM token 消耗，支持成本报告 |
| P2-3 | 评估框架 | Golden-file 测试，agent 输出回归检测 |
| P2-4 | 批量审计 | 支持选择多个文档一次性批量审计 |
| P2-5 | 审计历史对比 | 支持同一文档多次审计结果对比 |

### 2.2 Agent 增强

| 编号 | 改进项 | 描述 |
|------|--------|------|
| P2-6 | LLM-based Supervisor | 使用 LLM 推理决定路由，替代当前 flag-based 状态机 |
| P2-7 | LangGraph Checkpointer | 添加 MemorySaver，支持中断恢复和状态检查 |
| P2-8 | 并行 agent 执行 | regulation_expert 和 risk_assessor 并行执行 |
| P2-9 | 结构化状态验证 | 使用 Pydantic 替代 TypedDict，运行时校验 |
| P2-16 | 并行 Map 分析 | LangGraph Send API 实现 chunk 并行分析 |
| P2-17 | 递归 Reduce | 超多 chunk 时分批递归合并 findings |
| P2-18 | 文档结构可视化 | 报告中标注每个 finding 的章节来源 |

### 2.3 文档完善

| 编号 | 改进项 | 描述 |
|------|--------|------|
| P2-10 | API Reference | 独立的请求/响应 schema 文档 |
| P2-11 | 配置参考 | 每个环境变量的详细说明和影响 |
| P2-12 | 部署指南 | Docker Compose 部署方案 |
| P2-13 | Agent 自我反思 | 审计完成后评估报告质量，识别遗漏风险 |
| P2-14 | 历史上下文注入 | 将过去审计发现注入 prompt，提升分析深度 |
| P2-15 | 文件系统监听 | 基于 watchdog 的实时文件检测，替代定时扫描 |

---

## P3 - 长期愿景（v2.0 目标）

| 编号 | 改进项 | 描述 |
|------|--------|------|
| P3-1 | **GPU 推理支持** | 嵌入模型自动检测 GPU/CPU，支持 CUDA 推理加速 |
| P3-2 | **Docker 部署** | 提供 Dockerfile + docker-compose.yml，一键部署 |
| P3-3 | LangGraph Human-in-the-Loop | 使用 interrupt() 机制实现真正的交互式审批 |
| P3-4 | 多文档并行处理 | 文档处理和 agent 执行支持并行 |
| P3-5 | 多语言支持 | 法规库支持英文、日文等多语言 GMP 标准 |
| P3-6 | 插件系统 | 支持自定义 agent 节点和评估规则 |

---

## 已完成的改进

| 版本 | 改进项 | 状态 |
|------|--------|------|
| v1.0.3 | LightRAG 传递依赖打包 (nano_vectordb, aiohttp 等) | Done |
| v1.0.3 | 预构建知识图谱索引打包 + 首次运行 seeding | Done |
| v1.0.3 | asyncio.Lock 竞态修复 | Done |
| v1.0.3 | risk_assessor 静默失败修复 | Done |
| v1.0.3 | supervisor error detection 扩展 | Done |
| v1.0.3 | 安全配置默认值 (CORS, host binding) | Done |
| v1.0.3 | Tkinter 启动器 GUI (LLM 配置 + 模型下载) | Done |
| v1.0.3 | PDF 报告导出 (xhtml2pdf) | Done |
| v1.0.3 | PyInstaller 路径解析统一 (paths.py) | Done |
| v1.0.2 | PDF export native dependency 修复 (weasyprint→xhtml2pdf) | Done |
| v1.0.2 | RapidOCR ONNX 模型打包 | Done |
| v1.0.2 | PyInstaller collect_all 替代 hiddenimports | Done |
| v1.1 | 统一 Provider Registry (backend/app/core/providers.py) | Done |
| v1.1 | Agent LLM 缓存清理 (clear_llm_cache) | Done |
| v1.1 | Prompt 模板缓存 (agent/tools/prompt_loader.py) | Done |
| v1.1 | LightRAG httpx client 单例复用 | Done |
| v1.1 | Map-Reduce 长文档处理 (stuff/map_reduce 策略) | Done |
| v1.1 | 结构感知分块器 (agent/tools/document_chunker.py) | Done |
| v1.1 | settings save NameError 修复 (os 未导入) | Done |
| v1.1 | LLM reload 超时保护 (asyncio.wait_for 10s) | Done |
| v1.1 | _get_anthropic_llm 读取 ANTHROPIC_MODEL env | Done |

---

## 设计决策：Agent 智能化方向

### 关于 "breath/dream/grow/hold/pulse/trace"

这些不是 Claude Code 的官方功能名称，而是社区对 agent 行为的比喻性描述。Claude Code 实际的 agent 能力来自：
- **文件驱动的上下文注入**（CLAUDE.md 体系）
- **工具集**（Read/Write/Bash/Glob/Grep）
- **按需环境扫描**（git status + 文件搜索）
- **文件驱动的记忆系统**（memory/*.md）

### 可借鉴的模式

| 模式 | 说明 | 适用性 |
|------|------|--------|
| 文件驱动上下文注入 | 启动时加载规范/历史知识到 state | 高 — 可立即应用 |
| 环境扫描节点 | 解析文档特征，自动调整审计策略 | 高 — P1-14 |
| 渐进式知识积累 | 审计发现写入 JSONL，供后续参考 | 中 — P1-15 |
| 工具使用审计 | 记录每个 agent 的工具调用 | 中 — P2-1 (tracing) |
| 自省循环 | 审计完成后反思质量 | 低 — 需 LLM 额外调用 |

### 不适用的模式

- **后台反思/学习**：AuditBee 是按需执行，非持续运行
- **神经网络级别成长**：使用确定性 supervisor 路由，非 LLM 决策
- **并行推理**：当前 pipeline 是线性顺序，改动成本高

### 记忆机制设计（P1-15 详设）

- **存储位置**：`data/memory/findings.jsonl`
- **记录格式**：`{timestamp, document_type, severity, title, regulation_ref, risk_score}`
- **注入方式**：regulation_expert 读取相关历史 findings，作为 LLM prompt 的补充上下文
- **无需向量数据库**，JSONL + 关键词匹配足够轻量
