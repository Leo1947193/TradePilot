# Provider 契约实现说明

## 1. 文档目标

本文定义数据层的代码契约，面向以下对象：

- `app/services/providers/interfaces.py` 中的 provider 协议
- `app/services/providers/dtos.py` 中的 DTO
- graph node 对 provider 返回值和异常的消费方式

重点是“如何写可接入、可替换、可测试的 provider”，不是介绍外部数据源本身。

---

## 2. 当前 provider 接口

当前系统使用 `Protocol` 定义 provider 能力，所有实现都必须是异步方法。

### 2.1 `MarketDataProvider`

```python
async def get_daily_bars(symbol: str, *, lookback_days: int) -> list[MarketBar]
async def get_benchmark_bars(symbol: str, *, lookback_days: int) -> list[MarketBar]
```

实现要求：

- 返回值必须是 `MarketBar[]`
- 空数据返回空列表，不返回 `None`
- `symbol` 应按大写口径输出到 DTO
- `timestamp` 必须是 UTC aware datetime

### 2.2 `FinancialDataProvider`

```python
async def get_financial_snapshot(symbol: str) -> FinancialSnapshot | None
```

实现要求：

- 查无数据时返回 `None`
- 返回 DTO 时必须带 `source`
- 当前接口只定义“单个财务快照”，不适合直接承载季度序列

### 2.3 `CompanyEventsProvider`

```python
async def get_company_events(symbol: str, *, days_ahead: int) -> list[CompanyEvent]
```

实现要求：

- 只返回未来窗口内事件
- 结果为空时返回空列表
- `scheduled_at` 必须是 UTC aware datetime

### 2.4 `NewsDataProvider`

```python
async def get_company_news(symbol: str, *, limit: int) -> list[NewsArticle]
```

实现要求：

- provider 可以自行裁剪，也可以返回更多数据后由 adapter 再裁剪
- 当前 `FinnhubNewsProvider` 已在 provider 内按时间倒序和 `limit` 截断
- `published_at` 必须是 UTC aware datetime

### 2.5 `MacroCalendarProvider`

```python
async def get_macro_events(*, market: str, days_ahead: int) -> list[MacroCalendarEvent]
```

实现要求：

- 必须按 market 做过滤
- 只返回未来窗口内事件
- `scheduled_at` 必须是 UTC aware datetime

---

## 3. 当前 DTO 契约

DTO 定义在 `app/services/providers/dtos.py`，统一继承 `ProviderDto`，并启用 `extra="forbid"`。这意味着：

- provider 不得偷偷返回未声明字段
- DTO 是当前数据层最稳定的契约面

### 3.1 `ProviderSourceRef`

字段：

| 字段 | 类型 | 约束 |
|---|---|---|
| `name` | `str` | 必填 |
| `url` | `AnyUrl \| None` | 可空 |
| `fetched_at` | `datetime` | 必须是 UTC aware |

用途：

- 标识某条 provider 数据来自哪个供应方
- 为后续计算 `staleness_days`、source trace、持久化抓取时间提供基础

当前限制：

- graph 公共 `Source` 没有 `fetched_at`
- repository 也没有把该字段从 provider source 透传进 `analysis_sources`

### 3.2 `MarketBar`

字段：

- `symbol`
- `timeframe`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`

当前强约束：

- `timestamp` 必须是 UTC
- `timeframe` 当前默认固定为 `1d`

### 3.3 `FinancialSnapshot`

字段：

- `symbol`
- `as_of_date`
- `currency`
- `revenue`
- `net_income`
- `eps`
- `gross_margin_pct`
- `operating_margin_pct`
- `pe_ratio`
- `market_cap`
- `source`

当前强约束：

- `gross_margin_pct`、`operating_margin_pct` 限制在 `0..100`

### 3.4 `CompanyEvent`

字段：

- `symbol`
- `event_type`
- `title`
- `scheduled_at`
- `category`
- `url`
- `source`

当前缺口：

- 没有 `event_status`
- 没有 `event_state`
- 没有 `direction_hint`
- 没有 `event_id`

因此它现在更接近“轻量日历事件”，还不是设计目标里的完整公司催化剂对象。

### 3.5 `NewsArticle`

字段：

- `symbol`
- `title`
- `published_at`
- `source_name`
- `url`
- `summary`
- `category`
- `source`

当前缺口：

- 没有 `source_type`
- 没有 `relevance_score`
- 没有 `dedupe_cluster_id`
- 没有 `classifier_version`

### 3.6 `MacroCalendarEvent`

字段：

- `event_name`
- `country`
- `category`
- `scheduled_at`
- `importance`
- `source`

当前缺口：

- 没有事件唯一标识
- 没有 revision / 发布批次
- `country` 与 `market` 的关系目前只是字符串比较

---

## 4. UTC 与时间字段硬约束

当前 DTO 测试已经固定以下规则：

- `ProviderSourceRef.fetched_at` 必须是 UTC aware
- `MarketBar.timestamp` 必须是 UTC aware
- `CompanyEvent.scheduled_at` 必须是 UTC aware
- `NewsArticle.published_at` 必须是 UTC aware
- `MacroCalendarEvent.scheduled_at` 必须是 UTC aware

实现要求：

1. provider 在拿到本地时区时间后，必须先转为 UTC 再构造 DTO。
2. 不允许把 naive datetime 交给 DTO 验证器碰碰运气。
3. 新增 DTO 时，凡是时间戳都应沿用这一约束。

---

## 5. 异常与 fallback 契约

### 5.1 当前仓库实际语义

provider 负责“如实返回数据或抛错”，graph node 决定如何降级。

当前代码中：

- `FinnhubNewsProvider` 会直接透传 `httpx.HTTPStatusError`
- `StaticMacroCalendarProvider` 对非法文件结构直接抛 `ValueError`
- `YFinanceProvider` 不主动包装第三方错误
- `run_technical` / `run_fundamental` / `run_sentiment` / `run_event` 会捕获 provider 异常并退回占位版 `degraded`

因此当前契约是：

- provider 不必把异常转换成统一错误码
- node 必须把“异常 / 空结果 / provider 未注入”统一映射为模块降级

### 5.2 编码建议

后续新增 provider 时，保持下面约定：

- 网络层、鉴权层、反序列化层错误可以抛异常
- “无可用记录”用空列表或 `None`
- 不要在 provider 内直接返回“degraded result”或模块摘要

这可以让 provider 保持纯数据层职责。

---

## 6. provider factory 契约

工厂定义在 `app/services/providers/factory.py`。

当前行为：

- 不支持的 provider 名称立即抛 `ProviderConfigurationError`
- `NEWS_API_KEY` 缺失时拒绝构建新闻 provider
- `MACRO_CALENDAR_PATH` 缺失时拒绝构建宏观 provider
- `FinancialDataProvider` 和 `CompanyEventsProvider` 都复用 `YFinanceProvider`

实现建议：

1. 新增 provider 时，先扩 `Settings`，再扩 factory。
2. 不要让 graph node 直接感知环境变量。
3. 若引入 primary/fallback provider 链，应在 factory 产出组合 provider，而不是改 node 逻辑。

---

## 7. LLM provider adapter 契约（新增）

数据 provider 解决“取什么数据”，LLM adapter 解决“同一段业务能力如何切换不同模型厂商与模型”。两者都属于 service adapter，但职责不同，不应混成一个接口体系。

目标约束：

- 通过 `.env` 中的 `LLM_PROVIDER` 和 `LLM_MODEL` 切换厂商与模型
- 切换时不修改 graph node、analysis 模块或 prompt 调用点
- 业务层不感知 OpenAI / Anthropic / Gemini 等厂商请求格式差异

### 7.1 配置与工厂契约

推荐配置入口：

- `LLM_PROVIDER`
- `LLM_MODEL`
- 厂商专属凭证，例如 `MINIMAX_API_KEY`、`OPENROUTER_API_KEY`
- 厂商专属 base URL，例如 `MINIMAX_BASE_URL`、`OPENROUTER_BASE_URL`

实现要求：

1. `Settings` 负责读取上述变量，业务层不直接读环境变量。
2. `factory.py` 是唯一允许判断 `llm_provider` 的地方。
3. `LLM_MODEL` 默认保存厂商原生 model id；若兼容第三方 OpenAI 适配层需要做极小写法归一化，必须在 factory 中显式、可测试地完成。
4. 只有当前被选中的 `LLM_PROVIDER` 需要校验对应凭证；未选中的厂商配置可缺失。
5. 不支持的 `LLM_PROVIDER` 或缺失当前厂商凭证时，应在构建阶段快速失败。

### 7.2 目录与接口边界

建议新增目录：

```text
app/services/llm/
  interfaces.py
  dtos.py
  factory.py
  openai_adapter.py
  anthropic_adapter.py
  gemini_adapter.py
```

边界要求：

- 上层只依赖 `interfaces.py` 和统一 DTO
- 具体厂商 SDK、HTTP 请求体、响应解析留在 `*_adapter.py`
- 不把 OpenAI / Anthropic / Gemini 的原生对象泄漏到 graph、analysis、schema 层

公共接口应按“能力”设计，而不是按厂商设计。允许的能力例如：

- 文本生成
- 结构化 JSON 生成
- 结构化结果摘要

不建议把厂商特有参数直接暴露到业务层，例如：

- `response_format` 的厂商私有写法
- `tool_choice` 的私有枚举
- 各 SDK 自己的 message object 类型

### 7.3 adapter 职责与非职责

adapter 负责：

- 认证、超时、重试和请求发送
- 把统一输入 DTO 映射为厂商请求
- 把厂商响应归一化为统一输出 DTO
- 透出最终实际使用的 `provider` 和 `model`，便于追踪与持久化

adapter 不负责：

- 技术/基本面/情绪/事件规则判断
- 决策综合与交易计划分支
- graph state 的直接写入
- 用 LLM 结果覆盖结构化确定性字段

### 7.4 异常与 fallback 契约

建议沿用当前 data provider 的职责边界：

- adapter 可以抛网络、鉴权、限流、序列化错误
- 调用方决定是否降级、回退或直接失败
- 不要在 adapter 内返回伪造的“degraded summary”来掩盖失败

若某节点引入了 LLM 能力，应保持以下语义：

- 厂商切换是配置问题，不是业务分支
- provider/model 切换不改变节点输入输出 schema
- 若 LLM 只用于摘要类字段，失败时应优先回退到 deterministic fallback，而不是污染主结论

### 7.5 对本项目的直接约束

- `LLM_PROVIDER` 与 `LLM_MODEL` 的组合应足以完成模型切换；不要再在业务代码里增加第二套模型路由开关
- 综合评分、冲突处理、blocking flag、trade plan 分支仍由确定性规则实现
- 若未来保留 `llm_summary` 一类字段，它只能总结结构化结果，不得重写结构化结论

---

## 8. 目标态扩展方式

设计文档需要 richer 数据，但当前接口较薄。推荐扩展策略如下。

### 8.1 可以继续复用现有接口的场景

- 只是更换供应商，但输出仍然是 `MarketBar[]`
- 只是把新闻源从 Finnhub 改成别的公司新闻 API，输出仍然是 `NewsArticle[]`
- 只是把宏观日历从静态文件改成线上 API，输出仍然是 `MacroCalendarEvent[]`
- 只是把 LLM 厂商从 A 切到 B，但业务层消费的统一接口和输出 DTO 不变

### 8.2 应新增 adapter 层而不是直接改接口的场景

- 需要把多个 raw feed 合成统一财务数据集
- 需要做新闻去重、分类、evidence 选取
- 需要把公司事件扩成 richer schema
- 需要为每个数据集统一补 `staleness_days`、`missing_fields`、`source_trace`
- 需要同时支持多家 LLM 厂商，并在不改业务代码的前提下切换 `provider/model`

### 8.3 必须扩 DTO 或新增 DTO 的场景

- 设计要求的字段无法从当前 DTO 表达
- 同一数据域出现多条记录之间的关联关系，例如 `dedupe_cluster_id`
- 需要把 provider 原始标识、版本号、抽取器版本写入可追溯对象
- 需要统一记录 LLM 调用返回的 `provider`、`model`、usage 或 finish reason

---

## 9. 对 coding agent 的直接约束

- 新 provider 的公共方法签名必须与 `interfaces.py` 一致，除非先修改实现文档和所有消费方。
- provider 返回 DTO 时必须带 `source`，不要返回裸 dict。
- provider 不负责填 `diagnostics`、`warnings`、`degraded_modules`。
- 如果设计需要 richer 数据，不要污染现有 graph node 的简单路径；优先新增 adapter 或 richer dataset model。
- 新增 LLM adapter 时，同样先定义公共接口与 DTO，再落具体厂商实现，不要让业务层直接依赖某家 SDK。
