# Schema 与错误契约

本文件是对外 API 的说明版 Schema 文档。

- 机器可读的正式契约以 [openapi.yaml](./openapi.yaml) 为准
- `docs/zh/design` 中定义的模块/子模块输出，属于内部设计与组装契约，不默认等同于公共 HTTP 响应
- 若说明文档与 OpenAPI 存在冲突，应优先修正，使两者保持一致

## 1. 请求 Schema

### `POST /api/v1/analyses`

```json
{
  "ticker": "string"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `ticker` | `string` | 是 | 非空；建议使用美股常见代码格式；服务端应先 `trim` 再校验 |

---

## 2. 成功响应 Schema

```json
{
  "ticker": "string",
  "analysis_time": "ISO 8601 datetime",
  "technical_analysis": "object",
  "fundamental_analysis": "object",
  "sentiment_expectations": "object",
  "event_driven_analysis": "object",
  "decision_synthesis": "object",
  "trade_plan": "object",
  "sources": ["object"]
}
```

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ticker` | `string` | 是 | 标准化后的股票代码 |
| `analysis_time` | `string` | 是 | 本次系统输出生成时间，`ISO 8601` UTC |
| `technical_analysis` | `object` | 是 | 技术分析结果 |
| `fundamental_analysis` | `object` | 是 | 轻量级基本面分析结果 |
| `sentiment_expectations` | `object` | 是 | 情绪与预期分析结果 |
| `event_driven_analysis` | `object` | 是 | 事件分析结果 |
| `decision_synthesis` | `object` | 是 | 系统级综合结论 |
| `trade_plan` | `object` | 是 | 双向交易计划 |
| `sources` | `object[]` | 是 | 数据来源列表，允许为空数组但不建议 |

---

## 3. 模块对象

### 3.1 `technical_analysis`

| 字段 | 类型 | 必填 | 枚举 / 说明 |
|---|---|---|---|
| `technical_signal` | `string` | 是 | `bullish` \| `neutral` \| `bearish` |
| `trend` | `string` | 是 | `bullish` \| `neutral` \| `bearish` |
| `key_support` | `number[]` | 是 | 关键支撑位，允许空数组 |
| `key_resistance` | `number[]` | 是 | 关键阻力位，允许空数组 |
| `volume_pattern` | `string` | 是 | `accumulation` \| `distribution` \| `neutral` \| `pullback_healthy` \| `bounce_weak` |
| `momentum` | `string` | 是 | 动量摘要文本 |
| `entry_trigger` | `string` | 否 | 触发条件文本 |
| `target_price` | `number` | 否 | 目标价锚点 |
| `stop_loss_price` | `number` | 否 | 止损价锚点 |
| `risk_reward_ratio` | `number` | 否 | 风险收益比 |
| `risk_flags` | `string[]` | 是 | 技术风险标记 |
| `setup_state` | `string` | 是 | `actionable` \| `watch` \| `avoid` |
| `technical_summary` | `string` | 是 | 技术摘要 |

说明：

- 该对象是对技术模块内部丰富字段的对外收敛版本
- 模块内部聚合与子 Agent 字段见 `docs/zh/design/technical_analysis_agent/*`
- 若实现层需要暴露更多技术指标，应先更新设计文档与本契约

### 3.2 `fundamental_analysis`

| 字段 | 类型 | 必填 | 枚举 / 说明 |
|---|---|---|---|
| `fundamental_bias` | `string` | 是 | `bullish` \| `neutral` \| `bearish` \| `disqualified` |
| `composite_score` | `number` | 是 | 基本面综合分数 |
| `growth` | `string` | 是 | 盈利或增长摘要 |
| `valuation_view` | `string` | 是 | 估值观点摘要 |
| `business_quality` | `string` | 是 | 商业质量摘要 |
| `key_risks` | `string[]` | 是 | 关键风险列表 |
| `data_completeness_pct` | `number` | 是 | 范围 `0-100` |
| `fundamental_summary` | `string` | 是 | 基本面摘要 |

说明：

- 该对象是基本面模块内部输出的公共投影
- 模块内部的 `weight_scheme_used`、`source_trace`、`low_confidence_modules` 等字段可在内部保留，但只有在公共契约显式声明后才可对外暴露

### 3.3 `sentiment_expectations`

| 字段 | 类型 | 必填 | 枚举 / 说明 |
|---|---|---|---|
| `sentiment_bias` | `string` | 是 | `bullish` \| `neutral` \| `bearish` |
| `news_tone` | `string` | 是 | `positive` \| `neutral` \| `negative` |
| `market_expectation` | `string` | 是 | 预期摘要 |
| `key_risks` | `string[]` | 是 | 情绪和预期风险 |
| `data_completeness_pct` | `number` | 是 | 范围 `0-100` |
| `sentiment_summary` | `string` | 否 | 情绪摘要 |

说明：

- 该对象是情绪模块聚合结果的公共投影
- 内部实现可保留 `direction_signals`、`low_confidence_details` 等解释字段，但不应默认进入对外 API

### 3.4 `event_driven_analysis`

| 字段 | 类型 | 必填 | 枚举 / 说明 |
|---|---|---|---|
| `event_bias` | `string` | 是 | `bullish` \| `neutral` \| `bearish` |
| `upcoming_catalysts` | `string[]` | 是 | 未来 `0-90` 天催化剂 |
| `risk_events` | `string[]` | 是 | 会直接影响执行性的事件 |
| `event_risk_flags` | `string[]` | 是 | `binary_event_imminent` \| `earnings_within_3d` \| `regulatory_decision_imminent` \| `macro_event_high_sensitivity` |
| `data_completeness_pct` | `number` | 是 | 范围 `0-100` |
| `event_summary` | `string` | 否 | 事件摘要 |

说明：

- 该对象是事件模块聚合结果的公共投影
- `event_risk_flags` 是当前唯一进入公共契约的系统级事件风险标记字段

---

## 4. `decision_synthesis`

```json
{
  "overall_bias": "bullish | neutral | bearish",
  "bias_score": 0.0,
  "confidence_score": 0.0,
  "actionability_state": "actionable | watch | avoid",
  "conflict_state": "aligned | mixed | conflicted",
  "data_completeness_pct": 0.0,
  "weight_scheme_used": {},
  "blocking_flags": [],
  "module_contributions": [],
  "risks": []
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `overall_bias` | `string` | 是 | `bullish` \| `neutral` \| `bearish` |
| `bias_score` | `number` | 是 | 范围 `[-1.00, 1.00]` |
| `confidence_score` | `number` | 是 | 范围 `[0.00, 1.00]` |
| `actionability_state` | `string` | 是 | `actionable` \| `watch` \| `avoid` |
| `conflict_state` | `string` | 是 | `aligned` \| `mixed` \| `conflicted` |
| `data_completeness_pct` | `number` | 是 | 范围 `[0, 100]` |
| `weight_scheme_used` | `object` | 是 | 权重与归一化信息 |
| `blocking_flags` | `string[]` | 是 | 系统级阻断标记 |
| `module_contributions` | `object[]` | 是 | 固定 4 项，顺序为 `technical`、`fundamental`、`sentiment`、`event` |
| `risks` | `string[]` | 是 | 系统级风险摘要 |

### 4.1 `weight_scheme_used`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `configured_weights` | `object` | 是 | 固定包含四个模块权重 |
| `enabled_modules` | `string[]` | 是 | 已启用模块 |
| `disabled_modules` | `string[]` | 是 | 未启用模块 |
| `enabled_weight_sum` | `number` | 是 | 启用模块权重和 |
| `available_weight_sum` | `number` | 是 | 当前可用模块权重和 |
| `available_weight_ratio` | `number` | 是 | `available_weight_sum / enabled_weight_sum` |
| `applied_weights` | `object` | 是 | 参与打分的实际权重；不可用模块为 `null` |
| `renormalized` | `boolean` | 是 | 是否发生重归一化 |

### 4.2 `module_contributions[]`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `module` | `string` | 是 | `technical` \| `fundamental` \| `sentiment` \| `event` |
| `enabled` | `boolean` | 是 | 是否启用 |
| `status` | `string` | 是 | `usable` \| `degraded` \| `excluded` \| `not_enabled` |
| `direction` | `string` | 是 | `bullish` \| `neutral` \| `bearish` \| `disqualified` |
| `direction_value` | `number` | 是 | `-1` \| `0` \| `1` |
| `configured_weight` | `number` | 是 | 配置权重 |
| `applied_weight` | `number \| null` | 是 | 实际应用权重 |
| `contribution` | `number \| null` | 是 | 模块对总分的贡献 |
| `data_completeness_pct` | `number \| null` | 是 | 模块完整度 |
| `low_confidence` | `boolean` | 是 | 是否低置信度 |

---

## 5. `trade_plan`

```json
{
  "overall_bias": "bullish | neutral | bearish",
  "bullish_scenario": {
    "entry_idea": "string",
    "take_profit": "string",
    "stop_loss": "string"
  },
  "bearish_scenario": {
    "entry_idea": "string",
    "take_profit": "string",
    "stop_loss": "string"
  },
  "do_not_trade_conditions": ["string"]
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `overall_bias` | `string` | 是 | 必须与 `decision_synthesis.overall_bias` 一致 |
| `bullish_scenario` | `object` | 是 | 永远存在 |
| `bearish_scenario` | `object` | 是 | 永远存在 |
| `do_not_trade_conditions` | `string[]` | 是 | 可为空数组，但高风险场景下不应为空 |

### `bullish_scenario` / `bearish_scenario`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_idea` | `string` | 是 | 入场条件，必须是完整句子 |
| `take_profit` | `string` | 是 | 止盈逻辑，必须是完整句子 |
| `stop_loss` | `string` | 是 | 止损逻辑，必须是完整句子 |

---

## 6. `sources`

```json
{
  "type": "technical | financial | news | macro | event",
  "name": "string",
  "url": "string"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `string` | 是 | 来源类别 |
| `name` | `string` | 是 | 来源名称 |
| `url` | `string` | 是 | 可回溯地址 |

---

## 7. 错误 Schema

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": [
      {
        "field": "string",
        "reason": "string"
      }
    ]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `error.code` | `string` | 是 | 稳定错误码 |
| `error.message` | `string` | 是 | 人类可读错误信息 |
| `error.details` | `object[]` | 否 | 字段级错误明细 |

### 推荐错误码

| 错误码 | HTTP 状态码 | 说明 |
|---|---|---|
| `invalid_request` | `400` | 请求体或字段格式错误 |
| `ticker_not_supported` | `404` | 股票代码不在支持范围内 |
| `insufficient_data` | `422` | 数据不足，无法形成最小分析上下文 |
| `upstream_unavailable` | `503` | 关键上游数据源不可用 |
| `internal_error` | `500` | 未分类服务端错误 |
