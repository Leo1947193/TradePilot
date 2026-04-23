# Source Trace 与 Evidence 实现说明

## 1. 文档目标

设计文档要求结果“可追溯、可解释、可复现”，但当前仓库只实现了最外层 `sources`。本文定义三层追溯对象：

- 对外公开的 `sources`
- 面向模块内部与持久化的 `source_trace`
- 面向解释与审计的 `evidence`

目标是让后续 coding agent 知道：

- 哪些字段当前已经存在
- 哪些结构必须新增
- 应该把什么写到哪里

---

## 2. 当前仓库已实现的追溯对象

### 2.1 `ProviderSourceRef`

定义位置：`app/services/providers/dtos.py`

当前字段：

- `name`
- `url`
- `fetched_at`

这是最底层的 provider 来源引用，粒度是“某条 provider 记录来自哪里”。

### 2.2 API `Source`

定义位置：`app/schemas/api.py`

当前字段：

- `type`
- `name`
- `url`

这是公开响应层来源，粒度是“本次分析引用了哪些公共来源”。

### 2.3 `state.sources`

graph node 当前会把 provider 的 source 摘要合并到 `TradePilotState.sources`，最后由 `assemble_response` 去重。

当前限制：

- 不保留 `fetched_at`
- 不区分该来源支撑了哪个模块、哪个子结论
- 不区分 source 是数据供应商还是文章/事件原始 URL

### 2.4 数据库存储

当前 repository 会把 `payload.sources` 写入 `analysis_sources`，但：

- `fetched_at` 被硬编码成 `NULL`
- 没有 source 粒度的 evidence
- 没有 source trace JSON

---

## 3. 三层对象的职责边界

### 3.1 `sources`

职责：

- 对外 API 公示本次分析用到了哪些数据来源
- 给最终用户一个可点击的公共来源列表

不负责：

- 解释某条结论具体来自哪条新闻/哪根 K 线/哪个事件
- 记录去重簇、抽取器版本、缺失字段

### 3.2 `source_trace`

职责：

- 记录模块级或数据集级追溯信息
- 支撑调试、回放、模块级降级判断
- 支撑设计文档要求的 `source`、`fetched_at`、`staleness_days`、`missing_fields`

不负责：

- 面向最终用户的阅读体验

### 3.3 `evidence`

职责：

- 解释“为什么模块得出了这个方向/风险/总结”
- 给出可追溯样本，例如：
  - 哪几条 canonical headlines 支撑了 `news_tone`
  - 哪个财报日期触发了 `earnings_within_3d`
  - 哪几个关键价格点支撑了技术结论

不负责：

- 代替完整原始数据集

---

## 4. 当前态与目标态差异

| 追溯对象 | 当前态 | 目标态 |
|---|---|---|
| `sources` | 已实现 | 继续保留 |
| `source_trace` | 未实现统一模型 | 需要新增统一 schema |
| `evidence` | 未实现统一模型 | 需要新增统一 schema |
| `dedupe_cluster_id` | 未实现 | 情绪模块必须新增 |
| `theme_trace` | 未实现 | 情绪/事件模块建议新增 |

当前 repo 中唯一接近 trace 的信息是：

- DTO 里的 `source.fetched_at`
- module result 里的 `reason`
- diagnostics 中的 `degraded_modules` / `warnings` / `errors`

这些信息还不足以支撑设计里的可追溯要求。

---

## 5. 推荐的 `source_trace` 目标态结构

建议先不要建独立数据库表，先把 `source_trace` 放入各模块的 `report_json` 中； schema 稳定后再决定是否拆表。

### 5.1 通用结构

```json
{
  "dataset": "news_items | market_bars | financial_snapshot | company_events | macro_events",
  "source": "finnhub | yfinance | static_macro_calendar | ...",
  "source_url": "https://...",
  "fetched_at": "2026-04-17T12:00:00Z",
  "staleness_days": 0,
  "missing_fields": [],
  "record_count": 12,
  "coverage_window": {
    "from": "2026-03-18T00:00:00Z",
    "to": "2026-04-17T12:00:00Z"
  },
  "notes": []
}
```

### 5.2 最小字段要求

| 字段 | 必需性 | 说明 |
|---|---|---|
| `dataset` | 必需 | 数据集名称，不是模块名 |
| `source` | 必需 | provider 或供应方标识 |
| `source_url` | 可选但推荐 | 公共可追溯链接 |
| `fetched_at` | 必需 | 原始抓取时间 |
| `staleness_days` | 必需 | 按统一时间口径计算 |
| `missing_fields` | 必需 | 缺失的关键字段列表；没有缺失时写空数组 |
| `record_count` | 推荐 | 本批有效记录数 |

### 5.3 数据集命名建议

- `market_bars`
- `benchmark_bars`
- `financial_snapshot`
- `quarterly_financials`
- `estimate_revisions`
- `news_items`
- `company_events`
- `macro_events`

不要把 `dataset` 命名成：

- `technical`
- `sentiment`
- `event`

因为那是模块，不是数据集。

---

## 6. 推荐的 `evidence` 目标态结构

### 6.1 通用结构

```json
{
  "kind": "headline | event | price_level | metric",
  "label": "Apple earnings scheduled in 2 days",
  "value": "2026-04-19T20:30:00Z",
  "why": "Triggers earnings_within_3d",
  "source_name": "Reuters",
  "source_url": "https://example.com/article",
  "published_at": "2026-04-17T09:20:00Z",
  "dedupe_cluster_id": "optional",
  "theme_trace": ["optional", "tags"]
}
```

### 6.2 模块级 evidence 建议

技术模块：

- `kind = price_level | pattern | metric`
- 应能回溯到 bar 区间或计算窗口

基本面模块：

- `kind = metric`
- 应能标识指标窗口，例如 `latest_quarter`、`ttm`

情绪模块：

- `kind = headline`
- 必须记录 `source_name`、`source_url`
- 目标态必须支持 `dedupe_cluster_id`

事件模块：

- `kind = event`
- 必须记录事件时间、事件类型、来源 URL

---

## 7. `sources`、`source_trace`、`evidence` 的映射关系

推荐规则：

1. `sources` 是所有 `source_trace.source_url` 的去重公共子集。
2. `source_trace` 是数据集级，通常一份数据集 1 条或数条。
3. `evidence` 是结论级，数量少但需要更精确。

示例：

- `FinnhubNewsProvider` 拉到 30 条新闻
  - `sources`：`[{type: "news", name: "finnhub", url: "https://finnhub.io"}]`
  - `source_trace`：1 条 `dataset = news_items`
  - `evidence`：3 条 canonical headline

---

## 8. 情绪模块的额外要求

设计文档对情绪模块追溯要求最高，后续实现必须单独满足：

- canonical headline 选择结果
- `dedupe_cluster_id`
- `source_name`
- 原始 `url`
- `classifier_version` 或规则版本
- 必要时记录 `theme_trace`

实现建议：

1. 不要把 `dedupe_cluster_id` 塞进当前 `NewsArticle`，除非整个新闻适配链都改成 richer DTO。
2. 优先新增 `NormalizedNewsItem` 或 `NewsEvidenceItem` 这类内部模型。

---

## 9. 当前持久化建议

在数据库结构未扩展前，建议按以下顺序落地：

1. 继续保留顶层 `analysis_sources`
2. 在各模块 `report_json` 中新增：
   - `source_trace`
   - `evidence`
3. 若某模块已有复杂追溯对象，先落在 `analysis_module_reports.report_json`

这样可以避免过早建很多难以稳定的关系表。

---

## 10. 对 coding agent 的直接建议

- 面向 API 的 `sources` 继续保持轻量，不要把内部 trace 直接塞进去。
- 一旦开始做模块级 evidence，必须与模块输出结论一一对应，避免“有证据但不知道支撑哪个结论”。
- 若字段只用于调试，不要混入 `sources`；优先放 `source_trace` 或 `diagnostics`。
- 在 schema 未稳定前，优先把 trace/evidence 放到 `report_json`，不要抢先设计复杂 SQL 关联表。
