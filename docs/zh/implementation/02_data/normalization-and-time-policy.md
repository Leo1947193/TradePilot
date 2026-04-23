# 归一化与时间口径实现说明

## 1. 文档目标

本文定义数据层的统一口径，解决后续编码中最容易发散的几件事：

- ticker、market、benchmark 如何归一化
- 时间统一用什么时区
- 各 provider 的查询窗口如何与分析窗口对齐
- `staleness_days`、事件窗口、抓取时间分别按什么定义

本文是全局口径；模块内部更细的阈值仍以各模块实现文档为准。

---

## 2. 全局归一化入口

当前全局入口在 graph 前两步：

1. `validate_request`
2. `prepare_context`

其中 `prepare_context` 当前会补齐默认值：

- `analysis_time = datetime.now(timezone.utc)`，如果上游未提供
- `market = "US"`
- `benchmark = "SPY"`
- `analysis_window_days = (7, 90)`

因此数据层必须假设：

- 没有显式上下文时，系统默认分析美股
- 所有窗口计算都以 `analysis_time` 为基准
- 当前 V1 的持仓相关窗口是 `7-90` 天

---

## 3. ticker 与 market 口径

### 3.1 ticker

当前代码消费的 ticker 都以 `normalized_ticker` 为准。

实现要求：

- provider 调用参数使用 `normalized_ticker`
- DTO 输出中的 `symbol` 也统一写大写 ticker
- 持久化同时保留 `raw_ticker` 和 `normalized_ticker`

### 3.2 market

当前 `GraphContext.market` 的默认值是 `US`。

当前作用：

- 事件模块传给 `MacroCalendarProvider.get_macro_events(market=...)`
- 持久化时写入 `analysis_reports.market`

注意：

- 当前 `StaticMacroCalendarProvider` 是把 `market` 直接和 `country` 比较
- 这在美股场景可用，但它不是通用的市场映射方案

目标态建议：

- 将 `market`、`country`、`trading_calendar` 拆开
- 数据层内部统一维护映射表，例如 `US -> {country=US, timezone=America/New_York}`

---

## 4. 时间与时区口径

### 4.1 当前硬约束

所有 provider DTO 中的 datetime 都必须是 UTC aware。

包括：

- `ProviderSourceRef.fetched_at`
- `MarketBar.timestamp`
- `CompanyEvent.scheduled_at`
- `NewsArticle.published_at`
- `MacroCalendarEvent.scheduled_at`

### 4.2 统一原则

实现时区规则如下：

1. 外部 API 若返回本地时区，provider 先转 UTC，再构造 DTO。
2. 系统内部计算窗口时一律使用 UTC。
3. 面向最终用户的本地市场时间展示，不在 provider 层做。

---

## 5. 当前查询窗口口径

### 5.1 技术模块

当前 `run_technical` 用：

- `lookback_days = analysis_window_days[1]`

在默认上下文下等于：

- `lookback_days = 90`

当前口径是自然日，不是交易日。

实现影响：

- `YFinanceProvider` 用 `period="90d"` 拉数
- 实际 bar 数由交易日数量决定，通常少于 90

### 5.2 情绪模块

当前 `FinnhubNewsProvider` 固定请求最近 30 天：

- `from = fetched_at.date() - 30 days`
- `to = fetched_at.date()`

然后 `run_sentiment` 只消费前 5 条文章。

这与设计文档的关系：

- 设计中 `news_tone` 的分析窗口是 `7` 天主窗口、`30` 天辅窗口
- 当前 provider 的 30 天窗口是合理的 raw 输入范围
- 但 node 层只取前 5 条，尚不足以完成设计中的统计

### 5.3 事件模块

当前 `run_event` 用：

- `days_ahead = analysis_window_days[1]`

默认等于：

- `days_ahead = 90`

这与设计文档要求的未来 `0-90` 天窗口一致。

### 5.4 基本面模块

当前 `FinancialDataProvider` 没有窗口参数，只提供“当前可得财务快照”。

这意味着：

- 财务窗口和序列选择尚未下沉到数据层
- 后续一旦要实现季度同比、TTM、历史估值，需要新增 richer dataset，而不是继续复用当前单点快照

---

## 6. `fetched_at`、`analysis_time`、事件发生时间的区分

数据层必须区分三类时间：

### 6.1 `analysis_time`

含义：

- 本次系统分析的统一基准时间

来源：

- `GraphContext.analysis_time`

用途：

- 计算窗口
- 计算 `staleness_days`
- 判断事件是否在未来窗口内

### 6.2 `fetched_at`

含义：

- provider 抓到这批数据的时间

来源：

- `ProviderSourceRef.fetched_at`

用途：

- 评估原始数据抓取是否过旧
- 形成 source trace

注意：

- 当前 `analysis_sources.fetched_at` 没有真正写入 provider 抓取时间
- `state.sources` 也不保留这个字段

### 6.3 领域时间

含义示例：

- `MarketBar.timestamp`
- `NewsArticle.published_at`
- `CompanyEvent.scheduled_at`
- `FinancialSnapshot.as_of_date`

这些时间代表“数据说的是哪一天/哪个事件时点”，不能与 `fetched_at` 混用。

---

## 7. `staleness_days` 的统一定义

设计文档多处要求 `staleness_days`，但当前代码层还没有统一实现。后续建议用下面的全局规则。

### 7.1 统一公式

对“以某个参考时间代表数据有效日期”的数据集：

```text
staleness_days = floor(analysis_time_utc - reference_time_utc_or_date)
```

其中 `reference_time` 按数据集选取：

| 数据集 | 建议参考时间 |
|---|---|
| 日线行情 | 最新一根 `MarketBar.timestamp` |
| 新闻数据集 | 最新一条有效 `NewsArticle.published_at` |
| 财务快照 | `FinancialSnapshot.as_of_date` |
| 公司事件数据集 | provider `fetched_at`，不是 `scheduled_at` |
| 宏观日历数据集 | provider `fetched_at`，不是 `scheduled_at` |

原因：

- `scheduled_at` 代表未来事件发生时间，不代表数据抓取是否新鲜
- 事件数据的新鲜度应该衡量“你何时查询到这个日历/事件状态”

### 7.2 当前状态

当前仓库里：

- DTO 已有 `fetched_at`
- 但 graph 和 repository 还没把它真正转成统一的 `staleness_days`
- 各分析器目前用的是简化数据，不足以输出设计文档要求的 staleness 字段

因此后续实现顺序应为：

1. 先在 dataset adapter 中显式计算 `staleness_days`
2. 再把它传入模块聚合器
3. 最后再决定是否落库和暴露给 API

---

## 8. 自然日、交易日与事件窗口

### 8.1 当前默认

当前代码中的 `lookback_days`、`days_ahead` 都按自然日解释。

### 8.2 何时必须引入交易日历

以下场景不能再只用自然日：

- 技术指标依赖固定 bar 数
- 判断“最近 3 个交易日”而不是“最近 3 天”
- 财报前后交易窗口需要排除非交易日

当前仓库还没有交易日历抽象，因此：

- V1 数据层文档先把自然日口径写死
- 若模块需要交易日历，应新增独立服务，不要把逻辑塞进 provider

### 8.3 事件窗口建议

对事件相关设计，推荐固定区分以下窗口：

- `0-3` 天：近端硬风险窗口
- `4-14` 天：短期高敏感窗口
- `15-90` 天：背景催化剂窗口

这是对 event 模块聚合器有用的标准切片，不要求所有 provider 都按这三段返回。

---

## 9. 缺失数据与空值口径

实现中应区分以下几种情况：

| 情况 | provider 返回 | 节点语义 |
|---|---|---|
| 无结果但请求成功 | `[]` 或 `None` | 允许降级 |
| 上游异常 | 抛异常 | 节点捕获并降级 |
| 字段非法 | DTO 校验异常 | 视作 provider 错误 |
| 未注入 provider | 不调用 | 直接占位降级 |

不要混用：

- 不要用空列表表示“系统异常”
- 不要用 `None` 表示“列表型数据为空”

---

## 10. 对 coding agent 的直接建议

- 一旦开始实现 `staleness_days`，必须先确定 reference time，不能按数据集随意选时间字段。
- 若要补交易日口径，不要直接替换当前自然日语义；应新增明确命名的字段或 helper。
- `fetched_at` 与业务时间必须同时保留，不能二选一。
- 后续 richer 数据集应在 adapter 层完成归一化，避免每个分析模块自己解释时间窗口。
