# 分析接口

## 1. 接口说明

### `POST /api/v1/analyses`

输入一个股票代码，返回完整的结构化分析结果，包括：

- 技术分析
- 轻量级基本面分析
- 情绪与预期分析
- 事件驱动分析
- 决策综合结果
- 交易计划
- 来源列表

该接口是系统的主入口，对应设计文档中的完整主流程。

实现上，该接口由 `LangGraph` 驱动的一次完整分析 graph 执行完成，但对客户端仍表现为单个同步业务接口。

机器可读契约见 [openapi.yaml](./openapi.yaml)。

---

## 2. 请求

### 请求头

```http
Content-Type: application/json
Accept: application/json
```

### 请求体

```json
{
  "ticker": "AAPL"
}
```

### 请求规则

- `ticker` 为必填字段
- 必须是非空字符串
- 服务端在校验前应先去除首尾空白
- 对外推荐传入大写代码；若大小写可标准化，则服务端应在标准化后处理
- 若代码格式非法、市场不受支持或关键数据源无法建立最小上下文，接口应返回错误而不是返回伪结果

---

## 2.1 执行语义

`POST /api/v1/analyses` 在服务端对应一次 LangGraph 运行，推荐执行顺序如下：

1. 输入校验与股票代码标准化
2. 公共上下文准备
3. 技术、基本面、情绪、事件模块并行执行
4. 决策综合层汇总
5. 交易计划生成
6. 顶层响应组装
7. 将分析结果与报告快照持久化到 `PostgreSQL`
8. 返回 HTTP 响应

补充约束：

- 不要求客户端理解或感知内部 graph 节点
- 任一节点失败时，服务端应根据系统设计决定返回降级结果还是直接报错
- V1 不暴露 LangGraph 原生流式事件、节点日志或中间 state
- 只有当持久化成功后，才允许返回 `200 OK`

---

## 3. 成功响应

### 状态码

`200 OK`

### 响应示例

```json
{
  "ticker": "AAPL",
  "analysis_time": "2026-04-16T08:30:00Z",
  "technical_analysis": {
    "technical_signal": "bullish",
    "trend": "bullish",
    "key_support": [198.5, 194.2],
    "key_resistance": [205.0, 209.8],
    "volume_pattern": "accumulation",
    "momentum": "daily and weekly momentum remain constructive",
    "entry_trigger": "price holds above 198.5 and reclaims 205.0 on expanding volume",
    "target_price": 214.0,
    "stop_loss_price": 194.2,
    "risk_reward_ratio": 2.3,
    "risk_flags": [],
    "setup_state": "watch",
    "technical_summary": "Trend remains constructive, but a fresh breakout confirmation is still required."
  },
  "fundamental_analysis": {
    "fundamental_bias": "bullish",
    "composite_score": 74.5,
    "growth": "earnings revisions remain positive",
    "valuation_view": "valuation is elevated but still acceptable versus quality",
    "business_quality": "cashflow quality and balance sheet remain solid",
    "key_risks": ["valuation_compression_risk"],
    "data_completeness_pct": 100.0,
    "fundamental_summary": "Fundamentals support the long case, but upside is sensitive to valuation compression."
  },
  "sentiment_expectations": {
    "sentiment_bias": "bullish",
    "news_tone": "positive",
    "market_expectation": "expectations are constructive but not euphoric",
    "key_risks": ["expectation_bar_rising"],
    "data_completeness_pct": 92.0,
    "sentiment_summary": "News flow remains supportive, though the market is no longer under-positioned."
  },
  "event_driven_analysis": {
    "event_bias": "neutral",
    "upcoming_catalysts": ["next earnings release within 21 days"],
    "risk_events": ["earnings window approaching"],
    "event_risk_flags": [],
    "data_completeness_pct": 100.0,
    "event_summary": "No immediate binary event blocks the trade, but the next earnings date is entering the watch window."
  },
  "decision_synthesis": {
    "overall_bias": "bullish",
    "bias_score": 0.42,
    "confidence_score": 0.78,
    "actionability_state": "watch",
    "conflict_state": "mixed",
    "data_completeness_pct": 97.0,
    "weight_scheme_used": {
      "configured_weights": {
        "technical": 0.5,
        "fundamental": 0.1,
        "sentiment": 0.2,
        "event": 0.2
      },
      "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
      "disabled_modules": [],
      "enabled_weight_sum": 1.0,
      "available_weight_sum": 1.0,
      "available_weight_ratio": 1.0,
      "applied_weights": {
        "technical": 0.5,
        "fundamental": 0.1,
        "sentiment": 0.2,
        "event": 0.2
      },
      "renormalized": false
    },
    "blocking_flags": [],
    "module_contributions": [
      {
        "module": "technical",
        "enabled": true,
        "status": "usable",
        "direction": "bullish",
        "direction_value": 1,
        "configured_weight": 0.5,
        "applied_weight": 0.5,
        "contribution": 0.5,
        "data_completeness_pct": 100.0,
        "low_confidence": false
      },
      {
        "module": "fundamental",
        "enabled": true,
        "status": "usable",
        "direction": "bullish",
        "direction_value": 1,
        "configured_weight": 0.1,
        "applied_weight": 0.1,
        "contribution": 0.1,
        "data_completeness_pct": 100.0,
        "low_confidence": false
      },
      {
        "module": "sentiment",
        "enabled": true,
        "status": "usable",
        "direction": "bullish",
        "direction_value": 1,
        "configured_weight": 0.2,
        "applied_weight": 0.2,
        "contribution": 0.2,
        "data_completeness_pct": 92.0,
        "low_confidence": false
      },
      {
        "module": "event",
        "enabled": true,
        "status": "usable",
        "direction": "neutral",
        "direction_value": 0,
        "configured_weight": 0.2,
        "applied_weight": 0.2,
        "contribution": 0.0,
        "data_completeness_pct": 100.0,
        "low_confidence": false
      }
    ],
    "risks": [
      "valuation remains somewhat elevated",
      "breakout confirmation has not completed yet"
    ]
  },
  "trade_plan": {
    "overall_bias": "bullish",
    "bullish_scenario": {
      "entry_idea": "Consider a long entry only if price holds above 198.5 and confirms strength through 205.0 with volume expansion.",
      "take_profit": "Take partial profits into the 214 area and reassess if momentum continues.",
      "stop_loss": "Exit if price loses 194.2 on a failed breakout structure."
    },
    "bearish_scenario": {
      "entry_idea": "Only consider the short case if price loses 194.2 and fails to reclaim it quickly.",
      "take_profit": "Use the next lower support zone as the first downside objective after confirmation.",
      "stop_loss": "Cover if price recovers above the failed-breakdown level and breadth improves."
    },
    "do_not_trade_conditions": [
      "Do not open a new position immediately before a newly confirmed binary event window.",
      "Do not trade if breakout volume confirmation does not appear."
    ]
  },
  "sources": [
    {
      "type": "technical",
      "name": "Market Data Provider",
      "url": "https://example.com/market-data/aapl"
    },
    {
      "type": "financial",
      "name": "Financial Statement Provider",
      "url": "https://example.com/financials/aapl"
    }
  ]
}
```

---

## 4. 响应语义约束

- `decision_synthesis.overall_bias` 是系统级最终方向，优先级高于任何单一模块方向
- `trade_plan.overall_bias` 必须与 `decision_synthesis.overall_bias` 完全一致
- `trade_plan` 必须始终同时包含 `bullish_scenario` 与 `bearish_scenario`
- `sources` 必须始终存在，至少包含本次分析实际使用的数据来源
- 当风险较高或置信度不足时，允许方向存在，但 `actionability_state` 必须压制为 `watch` 或 `avoid`

---

## 5. 错误响应

### 常见状态码

| 状态码 | `error.code` | 说明 |
|---|---|---|
| `400` | `invalid_request` | 请求体非法、缺少 `ticker`、字段类型错误 |
| `404` | `ticker_not_supported` | 股票代码无法识别或不在支持范围内 |
| `422` | `insufficient_data` | 代码有效，但无法建立最小分析上下文 |
| `503` | `upstream_unavailable` | 关键数据源暂时不可用 |
| `500` | `internal_error` | 非预期服务端错误 |

### 错误示例

```json
{
  "error": {
    "code": "invalid_request",
    "message": "ticker is required",
    "details": [
      {
        "field": "ticker",
        "reason": "missing"
      }
    ]
  }
}
```
