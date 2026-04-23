# 数据持久化流程实现说明

## 1. 文档目标

本文说明单次分析结果如何从 graph state 写入 PostgreSQL，包括：

- 何时触发持久化
- 持久化前置条件
- repository 写入顺序
- 失败语义
- 当前实现缺口

本文只讨论“分析结果持久化”，不讨论缓存或 checkpoint。

---

## 2. 当前主链路位置

当前主请求链路中，持久化发生在：

1. `validate_request`
2. `prepare_context`
3. `run_technical`
4. `run_fundamental`
5. `run_sentiment`
6. `run_event`
7. `synthesize_decision`
8. `generate_trade_plan`
9. `assemble_response`
10. `persist_analysis`

关键结论：

- 持久化发生在最终响应组装之后
- 因此数据库中保存的是完整快照，而不是中间半成品

---

## 3. `persist_analysis` 节点契约

代码位置：`app/graph/nodes/persist_analysis.py`

### 3.1 输入前置条件

当前节点要求以下字段必须已经存在：

- `response`
- `decision_synthesis`
- `trade_plan`
- `normalized_ticker`
- `context.analysis_time`

任一缺失都会立即抛 `ValueError`。

### 3.2 构造的 payload

节点会构造 `AnalysisReportPayload`，包含：

- `request_id`
- `raw_ticker`
- `normalized_ticker`
- `analysis_time`
- `request`
- `context`
- `module_results`
- `decision_synthesis`
- `trade_plan`
- `response`
- `sources`
- `diagnostics`

这说明当前持久化的输入面已经覆盖：

- 请求上下文
- 四模块快照
- 系统级决策
- 最终响应
- 顶层来源与 diagnostics

但还没有覆盖：

- provider 原始 payload
- `source_trace`
- `evidence`

---

## 4. repository 写入流程

实现位于 `PostgreSQLAnalysisReportRepository.save_analysis_report()`。

### 4.1 单事务顺序

当前严格顺序如下：

1. 生成 `report_id`
2. 生成 `persisted_at`
3. 构建主表行
4. 构建 4 条模块行
5. 构建 N 条来源行
6. 开启事务
7. 插入 `analysis_reports`
8. 插入 `analysis_module_reports` x4
9. 插入 `analysis_sources` xN
10. 事务提交

测试 `tests/repositories/test_postgresql_analysis_reports.py` 已固定了这个顺序。

### 4.2 为什么顺序重要

- 主表先写，才能让子表外键成立
- 模块表固定写 4 行，保证历史记录结构稳定
- 来源表最后写，数量随模块成功接线情况变化

---

## 5. 当前持久化对象的粒度

### 5.1 主表粒度

一行代表“一次完整分析请求”。

### 5.2 模块表粒度

一行代表“本次分析中的一个模块输出”。

当前固定要求四个模块都要有结果对象，即使是 `degraded`。

### 5.3 来源表粒度

一行代表“对外公开的一条来源”。

注意这不是 provider 原始记录，也不是 evidence。

---

## 6. 当前失败语义

### 6.1 节点内失败处理

若 repository 抛异常：

- `persist_analysis` 会先在节点内部校验后的 state 对象上把 `persistence` 更新为：
  - `status = FAILED`
  - `record_id = None`
  - `persisted_at = None`
  - `error = str(exc)`
- 然后再抛 `RuntimeError("analysis report persistence failed")`

这意味着：

- 持久化失败不是静默错误
- 主请求链路会感知失败
- 节点内部仍保留原始错误字符串，便于诊断，但该 failed state 不会作为成功 graph 输出返回给 API

### 6.2 成功语义

成功时返回新 state，并写入：

- `persistence.status = SUCCEEDED`
- `persistence.record_id = repository 返回的 record_id`
- `persistence.persisted_at = repository 返回的 persisted_at`

---

## 7. 当前实现的幂等性与重试语义

### 7.1 当前事实

- `analysis_reports.request_id` 唯一
- repository 使用 `INSERT`，不是 `UPSERT`

因此：

- 同一个 `request_id` 重复写入会违反唯一约束
- 当前没有“同请求覆盖旧记录”的实现

### 7.2 实现建议

如果后续需要持久化重试，先明确语义：

方案 A：`request_id` 真正代表一次不可重放请求

- 继续保持唯一插入
- 重试需生成新 request id

方案 B：`request_id` 代表同一次分析逻辑幂等键

- 需要改成 `upsert`
- 还要定义哪些字段允许覆盖

在语义没定之前，不要贸然把 repository 改成 upsert。

---

## 8. 当前持久化缺口

### 8.1 `fetched_at` 没写进来源表

数据库列已有，但 repository 当前写 `None`。

### 8.2 `provider_payloads` 没进 payload

`TradePilotState` 已预留 `provider_payloads`，但：

- 节点不写
- payload 不带
- repository 不存

### 8.3 模块级追溯对象缺失

当前 `report_json` 只保存 `AnalysisModuleResult` 的轻量快照，不包含：

- `source_trace`
- `evidence`
- richer 风险条目
- 模块级原始数据摘要

### 8.4 状态枚举与 schema 不完全一致

graph schema 有 `not_enabled`，但模块表 SQL 不支持。

---

## 9. 推荐的目标态演进顺序

### 9.1 第一阶段

保持现有三表结构不变，只增强 payload 内容：

- 给来源链补 `fetched_at`
- 在 `report_json` 中加入 `source_trace`
- 在 `report_json` 中加入 `evidence`

### 9.2 第二阶段

如果模块内部中间数据需要回放，再考虑把 `provider_payloads` 或 adapter 输出摘要写到主表 JSON。

### 9.3 第三阶段

只有当查询需求明确后，再新增关系表：

- `analysis_source_traces`
- `analysis_evidence_items`

---

## 10. 对 coding agent 的直接建议

- 只要改了持久化 payload 或写入顺序，就必须同步更新 `tests/graph/nodes/test_persist_analysis.py` 和 `tests/repositories/test_postgresql_analysis_reports.py`。
- 若只是补 richer 模块追溯，优先改 `report_json`，不要一开始就改 SQL schema。
- 若要让持久化支持重试，先明确 `request_id` 语义；否则唯一约束会让行为不一致。
- 不要把持久化移到后台异步任务；当前设计和测试都假设它是主链路同步步骤。
