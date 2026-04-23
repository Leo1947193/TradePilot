# 数据源实现说明

## 1. 文档目标

本文只回答实现层问题：

- 当前仓库有哪些数据入口已经落地
- 每类数据由哪个 provider 接口负责
- graph 节点如何消费这些数据
- 当前实现与设计目标之间还差什么

本文不复述各分析模块的业务规则；重点是让后续 coding agent 能直接实现 provider、fallback、原始数据接线与数据扩展。

---

## 2. 当前数据源总览

当前仓库已经定义了 5 组 provider 契约，见 `app/services/providers/interfaces.py`：

| 数据域 | Provider 接口 | 当前实现 | 主要消费方 | 当前状态 |
|---|---|---|---|---|
| 行情 K 线 | `MarketDataProvider` | `YFinanceProvider` | `run_technical` | 已接线 |
| 财务摘要 | `FinancialDataProvider` | `YFinanceProvider` | `run_fundamental` | 已接线，但字段较少 |
| 公司事件 | `CompanyEventsProvider` | `YFinanceProvider` | `run_event` | 已接线，但只覆盖财报日 |
| 公司新闻 | `NewsDataProvider` | `FinnhubNewsProvider` | `run_sentiment` | 已接线 |
| 宏观日历 | `MacroCalendarProvider` | `StaticMacroCalendarProvider` | `run_event` | 已接线，静态文件驱动 |

当前 graph 节点使用方式：

- `run_technical` 读取 `get_daily_bars(symbol, lookback_days=analysis_window_days[1])`
- `run_fundamental` 读取 `get_financial_snapshot(symbol)`
- `run_sentiment` 读取 `get_company_news(symbol, limit=5)`
- `run_event` 并行读取 `get_company_events(symbol, days_ahead=analysis_window_days[1])` 和 `get_macro_events(market, days_ahead=analysis_window_days[1])`

默认上下文由 `prepare_context` 提供：

- `market = "US"`
- `benchmark = "SPY"`
- `analysis_window_days = (7, 90)`

---

## 3. 当前已实现数据源

### 3.1 行情数据: `YFinanceProvider`

代码位置：`app/services/providers/yfinance_provider.py`

当前能力：

- 下载 `1d` 日线历史数据
- 输出 `MarketBar[]`
- 每条 bar 都带 `ProviderSourceRef(name="yfinance", url="https://finance.yahoo.com", fetched_at=UTC now)`
- `get_benchmark_bars()` 当前只是复用 `get_daily_bars()`

当前限制：

- 只有日线，没有周线、月线或盘中数据
- 没有显式缓存、限速、重试
- 没有返回缺失字段说明或原始 payload
- benchmark 与个股共用同一实现，没有单独的指数口径处理

适用模块：

- 技术分析主输入
- 后续若要实现相对强弱或 beta，对 benchmark 数据也应继续复用这一接口

### 3.2 财务数据: `YFinanceProvider.get_financial_snapshot`

当前能力：

- 从 `ticker.info` 和 `ticker.calendar` 拼出 `FinancialSnapshot`
- 已映射字段：
  - `currency`
  - `revenue`
  - `net_income`
  - `eps`
  - `gross_margin_pct`
  - `operating_margin_pct`
  - `pe_ratio`
  - `market_cap`
  - `as_of_date`
- 若 `calendar` 中存在财报时间，`as_of_date` 使用财报日期；否则回退到当天日期

当前限制：

- 这是“摘要快照”，不是完整报表
- 没有季度序列、TTM 序列、分析师预期、同行对比
- `as_of_date` 的含义是“当前可取到的参考日期”，不是严格的 filing date
- 设计文档要求的 `source`、`fetched_at`、`staleness_days`、`missing_fields` 目前没有作为独立数据集对象暴露

适用模块：

- 当前只够支撑占位版基本面分析
- 不足以直接实现 `earnings_momentum`、`financial_health`、`valuation_anchor` 的目标态

### 3.3 公司事件: `YFinanceProvider.get_company_events`

当前能力：

- 仅从 `ticker.calendar` 提取未来 `days_ahead` 窗口内的下一次财报时间
- 输出单条 `CompanyEvent(event_type="earnings")`

当前限制：

- 不覆盖 Investor Day、产品发布、诉讼、并购、FDA、监管裁决等设计中要求的事件
- 没有 `event_status`、`direction_hint`、`event_state` 等 richer schema
- 只能回答“未来窗口内是否有财报”，不能支撑完整公司催化剂分析

适用模块：

- 当前只够支撑 `event` 模块中的财报近端风险占位逻辑

### 3.4 新闻数据: `FinnhubNewsProvider`

代码位置：`app/services/providers/finnhub_news_provider.py`

当前能力：

- 调用 `/company-news`
- 拉取最近 30 天窗口：`from = now - 30d`，`to = now`
- 输出 `NewsArticle[]`
- 结果按 `published_at desc` 排序，并在 provider 内截断为 `limit`
- 每条文章带 `ProviderSourceRef(name="finnhub", url="https://finnhub.io", fetched_at=UTC now)`

当前限制：

- 当前 DTO 只保留标题、发布时间、媒体名、URL、摘要、分类
- 没有 `source_type`、`relevance_score`、`dedupe_cluster_id`、`classifier_version`
- 没有做去重、canonical headline 选取和主题链路聚合
- 节点层目前只拿前 5 条文章给占位版情绪分析器

适用模块：

- 当前足够支撑占位版情绪模块
- 不足以直接支撑 `news_tone` 设计中的去重、证据和分类约束

### 3.5 宏观事件数据: `StaticMacroCalendarProvider`

代码位置：`app/services/providers/static_macro_calendar.py`

当前能力：

- 从本地 JSON 文件加载宏观事件列表
- 过滤 `country == market`
- 过滤未来 `days_ahead` 窗口
- 输出按 `scheduled_at` 升序排序的 `MacroCalendarEvent[]`

当前限制：

- 数据源不是实时 feed，而是静态文件
- 没有 revision、版本号、发布源抓取时间
- `market` 目前等同于 `country`，只做简单字符串匹配
- 不包含“该股票对宏观事件的敏感性”这部分上下文，敏感性仍需上层模块自行判断

适用模块：

- 当前可支撑事件模块的宏观事件占位实现

---

## 4. 当前数据源接入与 fallback 规则

### 4.1 provider 构建

工厂位置：`app/services/providers/factory.py`

当前固定映射：

- `MARKET_DATA_PROVIDER=yfinance` -> `YFinanceProvider`
- `NEWS_PROVIDER=finnhub` -> `FinnhubNewsProvider`
- `MACRO_CALENDAR_PATH` -> `StaticMacroCalendarProvider`
- `FinancialDataProvider`、`CompanyEventsProvider` 目前也复用 `YFinanceProvider`

当前没有多 provider 优先级链，也没有自动二级回退。

### 4.2 graph 层 fallback

当前 repo 的回退不是在 provider 层完成，而是在 graph node 完成：

- provider 未注入 -> 模块直接进入 `degraded`
- provider 调用抛异常 -> 节点吞掉异常并回退到占位版 `degraded`
- provider 返回空数据 -> 节点回退到占位版 `degraded`

这意味着当前实现语义是：

- “无数据” 与 “上游失败” 最终都会体现在模块降级
- 对外响应不会暴露具体 provider 错误类型
- 错误明细只会变成 `diagnostics.warnings` 或 `reason`

### 4.3 当前公开 source 的写法

节点只把 provider 的公共来源信息映射到 `state.sources`：

- technical -> 第一条 bar 的 `source`
- fundamental -> snapshot 的 `source`
- sentiment -> 第一条 article 的 `source`
- event -> 所有公司事件与宏观事件的 `source`

重复 source 会按 `(type, name, url)` 去重。

---

## 5. 目标态数据源分层

设计文档对数据层的要求明显高于当前代码。后续实现建议按下面三层扩展，而不是直接在 node 里堆逻辑。

### 5.1 Raw Provider 层

职责：

- 与外部 API/文件系统通信
- 做鉴权、超时、重试、分页、速率控制
- 输出严格 DTO
- 保留 `fetched_at`

禁止：

- 在 provider 内做模块结论
- 在 provider 内做跨数据域聚合

### 5.2 Dataset Adapter 层

职责：

- 把 raw DTO 组装成模块真正消费的数据集
- 计算 `staleness_days`
- 补充 `missing_fields`
- 形成 `source_trace`
- 必要时执行 primary/fallback 选择

当前仓库缺口：

- 这一层还不存在
- `TradePilotState.provider_payloads` 已预留，但当前节点没有写入

### 5.3 Module Input 层

职责：

- 只消费统一数据集对象
- 不直接依赖第三方 SDK 返回形态
- 只在这里执行模块规则、聚合与证据选择

---

## 6. 目标态数据覆盖建议

按设计要求，后续至少还要补齐以下数据能力：

| 模块 | 当前缺口 | 建议新增数据集 |
|---|---|---|
| technical | 只有日线基础 bars | benchmark bars、可能的 corporate actions、缺失交易日处理 |
| fundamental | 只有单次 snapshot | 季度财务序列、TTM、分析师预期、估值历史、同行比较 |
| sentiment | 只有文章列表 | canonical headlines、去重簇、分类结果、relevance、主题链路 |
| event | 只有财报和静态宏观日历 | 公司催化剂 feed、监管/诉讼/并购事件、事件状态机 |

实现建议：

1. 不要先改 graph node 输出，先补 dataset adapter 和 DTO。
2. 新 provider 接入时，优先保持 `interfaces.py` 不变；必要时新增 richer DTO，而不是在 node 中塞原始 dict。
3. 若设计要求超过当前 provider 能力，优先在文档里把“当前态”和“目标态”分开，不要把目标字段硬塞进现有 DTO。

---

## 7. 对 coding agent 的直接建议

- 需要新增数据源时，先判断是扩展现有接口，还是新增 adapter 层；默认优先新增 adapter。
- 需要补充多源回退时，不要把 fallback 写进 graph node；应放在 provider factory 或 dataset adapter。
- 若只需要让现有占位模块跑通，复用当前 5 个 provider 即可。
- 若要开始实现 design 文档中的完整模块，当前 `FinancialSnapshot`、`CompanyEvent`、`NewsArticle` 都不够用，应先扩 DTO 和内部数据集契约。
