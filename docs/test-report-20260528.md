# AuditBee exe 端到端测试报告

**测试日期**: 2026-05-28
**测试环境**: dist/AuditBee/AuditBee.exe (frozen=True, port 8003)
**测试状态**: 全部通过

---

## 测试结果总览

| 链路 | 测试项 | 状态 |
|------|--------|------|
| 文档链路 | 上传、查询、详情、删除 | PASS |
| 知识图谱 | 状态、图谱数据、构建状态 | PASS |
| 模型配置 | 配置查询、LLM 模型、更新、占位符验证 | PASS |
| Agent 链路 | 任务创建、Agent 管道执行、报告生成 | PASS |
| 日志检查 | 无 ERROR 级别日志 | PASS |

---

## 1. 文档链路（增删查）

| 端点 | 方法 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| /api/documents/upload | POST | 上传成功 | `{"id":1,"filename":"sample_deviation.txt","status":"uploaded"}` | PASS |
| /api/documents/ | GET | 返回文档列表 | `{"items":[...],"total":1}` | PASS |
| /api/documents/1 | GET | 返回文档详情+内容 | 包含完整偏差报告内容 | PASS |
| /api/documents/1 | DELETE | 删除成功 | `{"status":"success"}` | PASS |

**结论**: 文档增删查链路完整可用。

---

## 2. 知识图谱链路

| 端点 | 方法 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| /api/kg/status | GET | 返回索引状态 | `built=true, file_count=12, input_file_count=16` | PASS |
| /api/kg/graph | GET | 返回节点和边 | `nodes=128, edges=141` | PASS |
| /api/kg/build-status | GET | 返回构建状态 | `building=false` | PASS |

**结论**: 知识图谱查询链路正常，预构建索引可用。

---

## 3. 模型配置链路

| 端点 | 方法 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| /api/config/llm/models | GET | 返回 8 个 provider | 8 个 provider，全部 available=false | PASS |
| /api/config/log_level | PUT | 更新成功 | `{"status":"success"}` | PASS |
| /api/config/deepseek_api_key | PUT | 占位符拒绝 (422) | `HTTP:422, "为占位符值，请填写真实配置"` | PASS |

**结论**: 配置链路正常，占位符验证生效。

---

## 4. Agent 链路

| 测试项 | 预期 | 实际 | 状态 |
|--------|------|------|------|
| 创建审计任务 | 任务创建成功 | `{"id":2,"status":"pending"}` | PASS |
| Agent 管道执行 | 完成（无 LLM key 时降级） | `status=completed, progress=100` | PASS |
| 报告生成 | 生成降级报告 | 报告文件已生成 | PASS |
| 管道节点执行 | 全部节点完成 | 8 个节点全部执行（547ms） | PASS |

**Agent 管道执行详情**:
- 节点: parse_doc → supervisor → regulation_expert → supervisor → risk_assessor → supervisor → report_writer → supervisor → END
- KG 查询: 2 次（lightrag 0 结果，fallback_db 5 结果）
- LLM 调用: 0 次（无 API key，优雅降级）
- 总延迟: 547ms

**结论**: Agent 链路在无 LLM key 时正确降级，管道完整执行，报告生成成功。

---

## 5. 日志检查

| 检查项 | 结果 |
|--------|------|
| ERROR 级别日志 | 无 |
| WARNING 级别日志 | 1 条（`No LLM adapters initialized`，预期行为） |

**结论**: 日志干净，无异常错误。

---

## 总体结论

**dist exe 全部核心链路测试通过**。文档增删查、知识图谱查询、模型配置、Agent 管道执行均正常工作。在无 LLM API key 的情况下，系统正确降级并生成报告。

**可分发状态**: 当前 exe 可作为内测包分发给制药行业 QA/QC 用户。
