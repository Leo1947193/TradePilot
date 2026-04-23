# PostgreSQL Schema 实现说明

## 1. 文档目标

本文描述当前仓库已经落地的 PostgreSQL 结构，以及这些表如何映射到 graph 输出和数据层对象。重点是：

- 当前有哪些表、字段、约束、索引
- repository 实际往里写什么
- 哪些地方与设计目标还有缺口

SQL 来源：

- `app/db/migrations/0001_init_analysis_reports.sql`
- `app/db/migrations/0002_add_indexes.sql`

---

## 2. 当前表结构总览

当前数据库包含 4 张表：

| 表名 | 用途 |
|---|---|
| `schema_migrations` | 记录已执行 migration 版本 |
| `analysis_reports` | 单次分析主记录 |
| `analysis_module_reports` | 四个模块的快照行 |
| `analysis_sources` | 顶层公开来源列表 |

当前没有：

- provider 原始 payload 表
- source trace 表
- evidence 表
- 缓存表

---

## 3. `schema_migrations`

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | `text primary key` | migration 版本号 |
| `applied_at` | `timestamptz not null default now()` | 应用时间 |

用途：

- 由 `app/db/migrate.py` 管理
- `discover_migrations()` 会扫描 `app/db/migrations/[0-9][0-9][0-9][0-9]_*.sql`

---

## 4. `analysis_reports`

### 4.1 职责

存储单次请求的主报告行，聚合以下内容：

- 请求信息
- 上下文
- diagnostics
- 决策综合结果
- 交易计划
- 最终 API 响应快照

### 4.2 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `uuid primary key` | 主键 |
| `request_id` | `text not null unique` | 请求唯一标识 |
| `storage_schema_version` | `text not null` | 存储 schema 版本 |
| `pipeline_version` | `text not null` | pipeline 版本 |
| `ticker` | `text not null` | 归一化 ticker |
| `raw_ticker` | `text not null` | 原始请求 ticker |
| `market` | `text` | 当前市场 |
| `analysis_time` | `timestamptz not null` | 本次分析时间 |
| `request_payload_json` | `jsonb not null` | 请求快照 |
| `context_json` | `jsonb not null` | graph context |
| `diagnostics_json` | `jsonb not null` | diagnostics 快照 |
| `overall_bias` | `text not null` | 系统总方向 |
| `actionability_state` | `text not null` | 可执行性 |
| `conflict_state` | `text not null` | 冲突状态 |
| `bias_score` | `numeric(6,4)` | 偏向分 |
| `confidence_score` | `numeric(6,4)` | 置信度 |
| `data_completeness_pct` | `numeric(5,2)` | 系统完整度 |
| `degraded_modules` | `jsonb not null` | 降级模块数组 |
| `excluded_modules` | `jsonb not null` | 排除模块数组 |
| `blocking_flags` | `jsonb not null` | 系统阻断标记 |
| `decision_synthesis_json` | `jsonb not null` | 决策综合完整快照 |
| `trade_plan_json` | `jsonb not null` | 交易计划完整快照 |
| `response_json` | `jsonb not null` | 最终 API 响应完整快照 |
| `created_at` | `timestamptz not null default now()` | 写入时间 |
| `updated_at` | `timestamptz not null default now()` | 更新时间 |

### 4.3 约束

当前 SQL 约束了：

- `overall_bias in ('bullish', 'neutral', 'bearish')`
- `actionability_state in ('actionable', 'watch', 'avoid')`
- `conflict_state in ('aligned', 'mixed', 'conflicted')`
- 多个 JSONB 字段必须分别是 object 或 array

### 4.4 当前实现细节

repository 常量：

- `STORAGE_SCHEMA_VERSION = "v1"`
- `PIPELINE_VERSION = "langgraph-v1"`

`request_id` 唯一约束意味着：

- 同一 request id 不能重复插入
- 当前没有 upsert / retry merge 逻辑

---

## 5. `analysis_module_reports`

### 5.1 职责

为每个分析模块各保存一行，当前固定 4 行：

1. `technical`
2. `fundamental`
3. `sentiment`
4. `event`

### 5.2 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `uuid primary key` | 主键 |
| `analysis_report_id` | `uuid not null` | 外键，指向主报告 |
| `module_name` | `text not null` | 模块名 |
| `module_order` | `smallint not null` | 固定顺序 1..4 |
| `report_schema_version` | `text not null` | 模块报告 schema 版本 |
| `status` | `text not null` | `usable/degraded/excluded` |
| `direction` | `text` | 模块方向 |
| `direction_value` | `smallint` | -1/0/1 |
| `data_completeness_pct` | `numeric(5,2)` | 模块完整度 |
| `low_confidence` | `boolean not null` | 低置信度 |
| `summary` | `text` | 模块摘要 |
| `risk_flags` | `jsonb not null` | 当前只写入 `reason` 包装成数组 |
| `report_json` | `jsonb not null` | 模块完整快照 |
| `created_at` | `timestamptz not null default now()` | 写入时间 |

### 5.3 当前约束与实际差异

SQL 约束：

- `module_name in ('technical', 'fundamental', 'sentiment', 'event')`
- `module_order in (1, 2, 3, 4)`
- `status in ('usable', 'degraded', 'excluded')`

注意这个约束与当前 API schema 存在差异：

- API/graph schema 支持 `not_enabled`
- 数据库表目前不支持 `not_enabled`

这意味着：

- 当前持久化层还没有为“部署未启用”这个状态预留数据库枚举
- 若未来真的落地 `not_enabled`，必须先补 migration

### 5.4 当前 repository 写法

`PostgreSQLAnalysisReportRepository._build_module_rows()` 会：

- 强制要求四个模块结果都存在
- `risk_flags` 当前只从 `module_result.reason` 派生
- `report_json` 直接保存 `AnalysisModuleResult.model_dump(mode="json")`

当前没有单独写入：

- `source_trace`
- `evidence`
- richer 模块级风险列表

---

## 6. `analysis_sources`

### 6.1 职责

保存最终公开的来源列表，对应 API `sources`。

### 6.2 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `uuid primary key` | 主键 |
| `analysis_report_id` | `uuid not null` | 外键，指向主报告 |
| `source_type` | `text not null` | `technical/financial/news/macro/event` |
| `source_name` | `text not null` | 来源名 |
| `source_url` | `text not null` | 来源 URL |
| `fetched_at` | `timestamptz` | 抓取时间 |
| `created_at` | `timestamptz not null default now()` | 写入时间 |

### 6.3 当前实现缺口

repository 当前写 source 行时：

- `source_type = source.type.value`
- `source_name = source.name`
- `source_url = str(source.url)`
- `fetched_at = None`

因此数据库虽然有 `fetched_at` 列，但当前永远写 `NULL`。

原因不是数据库不支持，而是上游 `Source` schema 本身没有 `fetched_at`。

---

## 7. 当前索引

### 7.1 `analysis_reports`

- `(ticker, analysis_time DESC, id DESC)`
- `(overall_bias, analysis_time DESC)`
- `(actionability_state, analysis_time DESC)`
- `(analysis_time DESC)`
- `(pipeline_version, analysis_time DESC)`

这说明当前查询优化重点是：

- 按 ticker 看历史
- 按总体方向筛报告
- 按可执行性筛报告
- 按 pipeline 版本看批次

### 7.2 `analysis_module_reports`

- `(module_name, status)`
- `(module_name, direction)`
- `(analysis_report_id)`
- `(module_name, direction, analysis_report_id)`

这说明当前模块表预期会支持：

- 按模块状态检索
- 按模块方向过滤
- 从主表反查模块行

当前没有为 `analysis_sources` 建索引，说明它主要作为附属展示数据，而不是高频过滤条件。

---

## 8. 持久化与 schema 的关系

当前持久化顺序在单事务内完成：

1. `analysis_reports`
2. 四条 `analysis_module_reports`
3. N 条 `analysis_sources`

任一步失败，事务回滚。

这与设计要求一致：

- 持久化是主链路的一部分
- 不是异步后台任务

---

## 9. 目标态 schema 扩展建议

优先级从高到低如下。

### 9.1 优先补齐现有列没用上的能力

优先做：

- 让 `analysis_sources.fetched_at` 真正写入 provider 抓取时间

这是最小改动，收益明确。

### 9.2 在 `report_json` 中承载 richer trace

建议先把这些字段写进 `analysis_module_reports.report_json`：

- `source_trace`
- `evidence`
- richer `risk_flags`
- 模块内部中间摘要

原因：

- 不需要立即改 SQL schema
- 与当前 `report_json` 的设计兼容

### 9.3 何时新增关系表

只有在以下需求稳定后，再考虑拆表：

- 需要按 evidence 做 SQL 级搜索
- 需要按来源追溯跨报告比较
- 需要统计某类 source 的历史命中率

在这之前，优先用 JSONB。

---

## 10. 对 coding agent 的直接建议

- 若要新增 `not_enabled` 持久化，先写 migration，再改 repository 和测试。
- 若只是补 trace/evidence，不要先改很多表，优先扩 `report_json`。
- 若要让 `analysis_sources.fetched_at` 生效，需要同时扩 API/graph source 传递链，单改 repository 不够。
- 所有 schema 变更都必须同步更新 `tests/db` 和 `tests/repositories`。
