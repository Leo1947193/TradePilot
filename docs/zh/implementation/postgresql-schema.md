# PostgreSQL 表结构设计

## 1. 目标

本文定义 V1 的 PostgreSQL 持久化结构，用于保存：

- 单次分析请求的主记录
- 技术面、基本面、情绪面、事件面的模块级报告
- 决策综合结果与交易计划
- 顶层响应快照
- 来源列表

设计目标：

- 优先支持按 `ticker + 时间` 查询历史分析
- 优先支持历史全保留，而不是只保留最新结果
- 优先支持按模块回看历史报告
- 优先保持和公共 API、内部 `module_results` 契约的解耦
- 优先保证 V1 可快速演进，避免过早过度范式化

驱动、连接池、migration runner 和 repository 接口约定见 [postgresql-access.md](./postgresql-access.md)。

---

## 2. 设计原则

### 2.1 主表 + 模块子表

V1 采用：

- `analysis_reports`
  - 存单次分析的主记录
- `analysis_module_reports`
  - 存四个模块各自的结构化报告
- `analysis_sources`
  - 存该次分析引用的来源列表

原因：

- 顶层结果与模块结果有明显的一对多关系
- 四个模块天然独立，拆成子表后更利于单模块历史回看
- 相比把所有内容全塞进一张大 JSON 表，更方便做最基础的筛选和统计

### 2.2 JSONB + 少量可索引列

V1 不追求把每个业务字段都拆成单列。

因此：

- 结构化详情保存在 `JSONB`
- 高频过滤字段单独成列

高频过滤字段至少包括：

- `ticker`
- `analysis_time`
- `overall_bias`
- `actionability_state`
- 模块级 `module_name`
- 模块级 `direction`
- 模块级 `status`

### 2.3 不使用 PostgreSQL ENUM

V1 推荐使用 `TEXT + CHECK`，不使用 PostgreSQL ENUM。

原因：

- 文档和实现还在快速迭代
- 枚举值可能随设计演进而调整
- `TEXT + CHECK` 更利于迁移和版本升级

### 2.4 历史全保留

V1 明确采用“历史全保留”策略。

这意味着：

- 每次成功分析都写入一组新的快照记录
- 不因为 `ticker` 相同而覆盖旧记录
- 不因为输入相同而覆盖旧记录
- 不因为同一天重复分析而覆盖旧记录

因此数据库层必须满足：

- 只对 `request_id` 做唯一约束
- 不对 `ticker`、`ticker + analysis_time`、`ticker + trading_day` 设置唯一约束
- 持久化写入使用 `insert`，不使用 `upsert`

这样设计的原因：

- 分析结果天然依赖时间窗口和上游数据快照
- 同一标的在不同时刻的结论都应可回放
- 后续复盘、比较和评估都依赖完整历史，而不是最终覆盖态

---

## 3. 写入边界

V1 只持久化成功生成并成功写库的分析结果。

具体边界：

- `200 OK` 响应必须以持久化成功为前提
- 允许模块 `degraded` / `excluded`
- 但必须至少形成完整的顶层响应与交易计划
- 失败请求不写入主结果表；失败信息由日志系统承担
- 同一 `ticker` 在同一日、同一小时、甚至同一分钟的重复成功分析，仍然应保留多条记录

写入顺序：

1. 写 `analysis_reports`
2. 写 4 条 `analysis_module_reports`
3. 写 `analysis_sources`
4. 同一事务提交

要求：

- 必须使用单事务
- 任一步失败都整体回滚
- 不允许出现主表已写入、模块表缺失一半的半成品记录

---

## 4. 表结构

### 4.1 `analysis_reports`

用途：

- 保存单次分析的主记录
- 作为模块表和来源表的父表

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `uuid` | 是 | 主键 |
| `request_id` | `text` | 是 | 对应一次分析请求的唯一 ID |
| `storage_schema_version` | `text` | 是 | 持久化结构版本，如 `v1` |
| `pipeline_version` | `text` | 是 | 分析流程版本，如 `langgraph-v1` |
| `ticker` | `text` | 是 | 标准化后的股票代码 |
| `raw_ticker` | `text` | 是 | 用户原始输入 |
| `market` | `text` | 否 | 市场标识，如 `US` |
| `analysis_time` | `timestamptz` | 是 | 分析结果生成时间，UTC |
| `request_payload_json` | `jsonb` | 是 | 原始请求快照 |
| `context_json` | `jsonb` | 是 | 运行时上下文快照 |
| `diagnostics_json` | `jsonb` | 是 | 降级、警告、错误等诊断信息 |
| `overall_bias` | `text` | 是 | `bullish / neutral / bearish` |
| `actionability_state` | `text` | 是 | `actionable / watch / avoid` |
| `conflict_state` | `text` | 是 | `aligned / mixed / conflicted` |
| `bias_score` | `numeric(6,4)` | 是 | 系统方向分数 |
| `confidence_score` | `numeric(6,4)` | 是 | 系统置信度 |
| `data_completeness_pct` | `numeric(5,2)` | 是 | 顶层完整度 |
| `degraded_modules` | `jsonb` | 是 | 降级模块列表 |
| `excluded_modules` | `jsonb` | 是 | 排除模块列表 |
| `blocking_flags` | `jsonb` | 是 | 系统阻断标记 |
| `decision_synthesis_json` | `jsonb` | 是 | 完整 `decision_synthesis` |
| `trade_plan_json` | `jsonb` | 是 | 完整 `trade_plan` |
| `response_json` | `jsonb` | 是 | 完整顶层响应快照 |
| `created_at` | `timestamptz` | 是 | 入库时间 |
| `updated_at` | `timestamptz` | 是 | 更新时间，V1 通常等于创建时间 |

约束建议：

- `primary key (id)`
- `unique (request_id)`
- `check (overall_bias in ('bullish','neutral','bearish'))`
- `check (actionability_state in ('actionable','watch','avoid'))`
- `check (conflict_state in ('aligned','mixed','conflicted'))`
- `check (jsonb_typeof(request_payload_json) = 'object')`
- `check (jsonb_typeof(context_json) = 'object')`
- `check (jsonb_typeof(diagnostics_json) = 'object')`
- `check (jsonb_typeof(degraded_modules) = 'array')`
- `check (jsonb_typeof(excluded_modules) = 'array')`
- `check (jsonb_typeof(blocking_flags) = 'array')`
- `check (jsonb_typeof(decision_synthesis_json) = 'object')`
- `check (jsonb_typeof(trade_plan_json) = 'object')`
- `check (jsonb_typeof(response_json) = 'object')`

说明：

- `storage_schema_version` 用于后续表结构演进
- `pipeline_version` 用于区分规则和编排版本
- `request_payload_json` 用于还原当时到底传入了什么
- `context_json` 用于保留市场、基准、分析窗口等运行时上下文
- `diagnostics_json` 用于保留 `degraded_modules` 之外的更完整诊断信息
- `response_json` 用于完整回放当时对外返回了什么
- `decision_synthesis_json` 和 `trade_plan_json` 单独存，是为了避免每次都从 `response_json` 中解析
- 不单独拆出 `technical_analysis`、`fundamental_analysis` 等顶层字段，因为这四块在模块子表中已有更清晰的归属

### 4.2 `analysis_module_reports`

用途：

- 保存单次分析中的四个模块报告
- 支持按模块维度查询历史

固定一条主记录对应最多 4 条模块记录：

- `technical`
- `fundamental`
- `sentiment`
- `event`

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `uuid` | 是 | 主键 |
| `analysis_report_id` | `uuid` | 是 | 外键，指向 `analysis_reports.id` |
| `module_name` | `text` | 是 | `technical / fundamental / sentiment / event` |
| `module_order` | `smallint` | 是 | 固定顺序：1-4 |
| `report_schema_version` | `text` | 是 | 模块报告结构版本 |
| `status` | `text` | 是 | `usable / degraded / excluded` |
| `direction` | `text` | 否 | 方向结论；基本面允许 `disqualified` |
| `direction_value` | `smallint` | 否 | 归一化方向值：`-1 / 0 / 1` |
| `data_completeness_pct` | `numeric(5,2)` | 否 | 模块完整度 |
| `low_confidence` | `boolean` | 是 | 是否低置信度 |
| `summary` | `text` | 否 | 模块摘要字段的公共投影 |
| `risk_flags` | `jsonb` | 是 | 模块级风险或阻断标记 |
| `report_json` | `jsonb` | 是 | 模块完整结构化结果 |
| `created_at` | `timestamptz` | 是 | 入库时间 |

约束建议：

- `primary key (id)`
- `foreign key (analysis_report_id) references analysis_reports(id) on delete cascade`
- `unique (analysis_report_id, module_name)`
- `check (module_name in ('technical','fundamental','sentiment','event'))`
- `check (module_order in (1,2,3,4))`
- `check (status in ('usable','degraded','excluded'))`
- `check (direction_value in (-1,0,1) or direction_value is null)`
- `check (jsonb_typeof(risk_flags) = 'array')`
- `check (jsonb_typeof(report_json) = 'object')`

`direction` 取值建议：

- `technical`：`bullish / neutral / bearish`
- `fundamental`：`bullish / neutral / bearish / disqualified`
- `sentiment`：`bullish / neutral / bearish`
- `event`：`bullish / neutral / bearish`

摘要字段映射建议：

- `technical` -> `technical_summary`
- `fundamental` -> `fundamental_summary`
- `sentiment` -> `sentiment_summary`
- `event` -> `event_summary`

风险字段映射建议：

- `technical` -> `risk_flags`
- `fundamental` -> `key_risks`
- `sentiment` -> `key_risks`
- `event` -> `event_risk_flags` 与 `risk_events` 的合并投影

顺序映射建议：

- `technical` -> `1`
- `fundamental` -> `2`
- `sentiment` -> `3`
- `event` -> `4`

### 4.3 `analysis_sources`

用途：

- 保存单次分析实际使用的来源列表
- 保留顶层 `sources` 的输出顺序

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `uuid` | 是 | 主键 |
| `analysis_report_id` | `uuid` | 是 | 外键，指向 `analysis_reports.id` |
| `source_order` | `integer` | 是 | 首次使用顺序，从 `0` 开始 |
| `source_type` | `text` | 是 | `technical / financial / news / macro / event` |
| `module_name` | `text` | 否 | 来源主要归属模块；允许为空 |
| `name` | `text` | 是 | 来源名称 |
| `url` | `text` | 是 | 来源 URL |
| `created_at` | `timestamptz` | 是 | 入库时间 |

约束建议：

- `primary key (id)`
- `foreign key (analysis_report_id) references analysis_reports(id) on delete cascade`
- `unique (analysis_report_id, source_order)`
- `unique (analysis_report_id, source_type, name, url)`
- `check (source_type in ('technical','financial','news','macro','event'))`
- `check (module_name in ('technical','fundamental','sentiment','event') or module_name is null)`
- `check (length(trim(url)) > 0)`

---

## 5. 推荐 DDL

```sql
create table analysis_reports (
    id uuid primary key,
    request_id text not null unique,
    storage_schema_version text not null,
    pipeline_version text not null,
    ticker text not null,
    raw_ticker text not null,
    market text,
    analysis_time timestamptz not null,
    request_payload_json jsonb not null,
    context_json jsonb not null,
    diagnostics_json jsonb not null,
    overall_bias text not null check (overall_bias in ('bullish', 'neutral', 'bearish')),
    actionability_state text not null check (actionability_state in ('actionable', 'watch', 'avoid')),
    conflict_state text not null check (conflict_state in ('aligned', 'mixed', 'conflicted')),
    bias_score numeric(6,4) not null,
    confidence_score numeric(6,4) not null,
    data_completeness_pct numeric(5,2) not null,
    degraded_modules jsonb not null default '[]'::jsonb,
    excluded_modules jsonb not null default '[]'::jsonb,
    blocking_flags jsonb not null default '[]'::jsonb,
    decision_synthesis_json jsonb not null,
    trade_plan_json jsonb not null,
    response_json jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (jsonb_typeof(request_payload_json) = 'object'),
    check (jsonb_typeof(context_json) = 'object'),
    check (jsonb_typeof(diagnostics_json) = 'object'),
    check (jsonb_typeof(degraded_modules) = 'array'),
    check (jsonb_typeof(excluded_modules) = 'array'),
    check (jsonb_typeof(blocking_flags) = 'array'),
    check (jsonb_typeof(decision_synthesis_json) = 'object'),
    check (jsonb_typeof(trade_plan_json) = 'object'),
    check (jsonb_typeof(response_json) = 'object')
);

create table analysis_module_reports (
    id uuid primary key,
    analysis_report_id uuid not null references analysis_reports(id) on delete cascade,
    module_name text not null check (module_name in ('technical', 'fundamental', 'sentiment', 'event')),
    module_order smallint not null check (module_order in (1, 2, 3, 4)),
    report_schema_version text not null,
    status text not null check (status in ('usable', 'degraded', 'excluded')),
    direction text,
    direction_value smallint check (direction_value in (-1, 0, 1) or direction_value is null),
    data_completeness_pct numeric(5,2),
    low_confidence boolean not null default false,
    summary text,
    risk_flags jsonb not null default '[]'::jsonb,
    report_json jsonb not null,
    created_at timestamptz not null default now(),
    unique (analysis_report_id, module_name),
    check (jsonb_typeof(risk_flags) = 'array'),
    check (jsonb_typeof(report_json) = 'object')
);

create table analysis_sources (
    id uuid primary key,
    analysis_report_id uuid not null references analysis_reports(id) on delete cascade,
    source_order integer not null,
    source_type text not null check (source_type in ('technical', 'financial', 'news', 'macro', 'event')),
    module_name text check (module_name in ('technical', 'fundamental', 'sentiment', 'event') or module_name is null),
    name text not null,
    url text not null,
    created_at timestamptz not null default now(),
    unique (analysis_report_id, source_order),
    unique (analysis_report_id, source_type, name, url),
    check (length(trim(url)) > 0)
);
```

---

## 6. 索引建议

### 6.1 主表索引

```sql
create index idx_analysis_reports_ticker_time
    on analysis_reports (ticker, analysis_time desc, id desc);

create index idx_analysis_reports_bias_time
    on analysis_reports (overall_bias, analysis_time desc);

create index idx_analysis_reports_actionability_time
    on analysis_reports (actionability_state, analysis_time desc);

create index idx_analysis_reports_analysis_time
    on analysis_reports (analysis_time desc);

create index idx_analysis_reports_pipeline_time
    on analysis_reports (pipeline_version, analysis_time desc);
```

### 6.2 模块表索引

```sql
create index idx_analysis_module_reports_module_status
    on analysis_module_reports (module_name, status);

create index idx_analysis_module_reports_module_direction
    on analysis_module_reports (module_name, direction);

create index idx_analysis_module_reports_analysis_report_id
    on analysis_module_reports (analysis_report_id);

create index idx_analysis_module_reports_module_direction_report
    on analysis_module_reports (module_name, direction, analysis_report_id);
```

### 6.3 可选 JSONB 索引

若后续需要按顶层阻断标记或模块报告内部字段做检索，可再增加：

```sql
create index idx_analysis_reports_blocking_flags_gin
    on analysis_reports using gin (blocking_flags);

create index idx_analysis_module_reports_report_json_gin
    on analysis_module_reports using gin (report_json);
```

V1 默认不要求先建这些 GIN 索引，除非出现明确查询压力。

---

## 7. 典型查询

### 7.1 查询某只股票最近 20 次分析

```sql
select
    request_id,
    ticker,
    analysis_time,
    overall_bias,
    actionability_state,
    confidence_score
from analysis_reports
where ticker = $1
order by analysis_time desc
limit 20;
```

### 7.2 查询某次分析的四个模块报告

```sql
select
    module_name,
    status,
    direction,
    data_completeness_pct,
    summary,
    report_json
from analysis_module_reports
where analysis_report_id = $1
order by case module_name
    when 'technical' then 1
    when 'fundamental' then 2
    when 'sentiment' then 3
    when 'event' then 4
    else 99
end;
```

### 7.3 查询最近处于 `avoid` 的分析

```sql
select
    ticker,
    analysis_time,
    overall_bias,
    actionability_state,
    blocking_flags
from analysis_reports
where actionability_state = 'avoid'
order by analysis_time desc
limit 100;
```

### 7.4 查询每只股票最近一次分析

```sql
select distinct on (ticker)
    ticker,
    request_id,
    analysis_time,
    overall_bias,
    actionability_state,
    confidence_score
from analysis_reports
order by ticker, analysis_time desc, id desc;
```

---

## 8. 历史全保留下的维护策略

V1 默认不删除历史分析记录。

维护约束：

- 不对旧分析做就地覆盖更新
- 不以“最新结果”反写旧记录
- 除数据修复外，不对 `response_json` 和 `report_json` 做事后改写

推荐做法：

- 把“最新结果”定义为查询逻辑，而不是单独维护一张最新表
- 当数据量显著增长后，再评估按 `analysis_time` 做月分区
- 若未来需要归档，优先做冷热分层，不破坏主键和外键关系

---

## 9. 为什么不只用一张表

不推荐把所有内容都塞进一张 `analysis_reports` 大表，只保留一个 `response_json`。

原因：

- 模块级历史查询会非常笨重
- 无法方便地区分四个模块各自的 `status / direction / completeness`
- 后续要做单模块统计时会被迫过度依赖 JSON 路径查询

也不推荐在 V1 过度拆表，例如：

- 单独为技术、基本面、情绪、事件各建一张专表
- 再为决策综合和交易计划单独拆专表

原因：

- 当前字段仍在演进
- 过度范式化会显著增加迁移成本
- V1 的核心目标是“稳定持久化”和“可回看”，不是复杂报表系统

---

## 10. V1 默认结论

除非用户明确要求修改，否则 V1 默认：

- 使用 3 张核心表：`analysis_reports`、`analysis_module_reports`、`analysis_sources`
- 历史分析全量保留，不做业务去重覆盖
- 模块详细内容存 `JSONB`
- 高频筛选字段单独成列
- 每次成功分析写入 1 条主记录、4 条模块记录、N 条来源记录
- 使用事务保证一次分析的持久化原子性
