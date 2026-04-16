# 📊 美股中期决策支持 Agent PRD

## 1. 概述

本项目是一个**美股中期决策支持 Agent**。

设计目标：
- 在交易决策前生成**结构化分析**
- 辅助人类决策（而非替代）

### 约束条件
- ❌ 无自动交易
- ❌ 无高频/短线交易（< 3 天）
- ❌ 无长期基本面投资（> 6 个月）
- ❌ 无复杂量化模型（如因子模型、高频交易）
- 工程环境、依赖管理和命令执行统一使用 `uv`

### 时间跨度
- 目标持仓周期：**1 周 – 3 个月**


## 2. 核心任务定义

### 输入

```json
{
  "ticker": "string"
}
```

⸻

输出（严格 Schema）
```json
{
  "ticker": "string",
  "analysis_time": "ISO datetime",

  "technical_analysis": {
    "trend": "bullish | bearish | neutral",
    "key_support": ["number"],
    "key_resistance": ["number"],
    "volume_pattern": "string",
    "momentum": "string",
    "technical_summary": "string"
  },

  "fundamental_analysis": {
    "growth": "string",
    "valuation_view": "string",
    "business_quality": "string",
    "fundamental_summary": "string"
  },

  "sentiment_expectations": {
    "news_tone": "positive | neutral | negative",
    "market_expectation": "string",
    "sentiment_summary": "string"
  },

  "event_driven_analysis": {
    "upcoming_catalysts": ["string"],
    "risk_events": ["string"],
    "event_summary": "string"
  },

  "decision_synthesis": {
    "overall_bias": "bullish | neutral | bearish",
    "confidence_score": "0-1 float",
    "actionability_state": "actionable | watch | avoid",
    "conflict_state": "aligned | mixed | conflicted",
    "blocking_flags": ["string"],
    "risks": ["string"]
  },

  "trade_plan": {
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
  },

  "sources": [
    {
      "type": "technical | news | financial | macro",
      "name": "string",
      "url": "string"
    }
  ]
}
```

## 3. 决策逻辑

### 3.1 偏向判断规则

Agent 必须先生成四个模块的结构化结论，再由**决策综合层**统一产出 `decision_synthesis`。

当前系统基线默认启用四个核心模块：

- technical
- fundamental
- sentiment
- event

默认配置权重为：

- technical：0.5
- sentiment：0.2
- event：0.2
- fundamental：0.1

但最终 `overall_bias` 不能简单等同于固定权重求和结果，还必须统一经过：

- 可用模块重归一化
- 冲突状态判断
- 数据完整度压制
- 基本面硬约束压制
- 执行性状态判断

因此，交易计划必须消费 `decision_synthesis.overall_bias`、`actionability_state`、`blocking_flags` 等系统级字段，而不是自行重算方向。



### 3.2 技术分析范围（严格限定）

必须包含：
- 趋势（基于均线/结构）
- 关键支撑与阻力
- 成交量行为（放量/缩量）
- 动量（RSI/MACD 方向）

禁止包含：
- tick 级别/日内剥头皮信号



### 3.3 基本面分析范围（仅轻量级）

仅包含：
- 营收/盈利增长方向
- 基础估值（高估/合理/低估）
- 商业质量（定性）

禁止包含：
- 完整 DCF
- 深度财务建模


### 3.4 情绪分析范围

来源：
- 新闻标题
- 市场叙事
- 分析师预期（可选）

输出：
- 基调分类
- 预期摘要



### 3.5 事件驱动范围

包含：
- 财报日期
- 宏观敏感事件（美联储、CPI）
- 公司特定催化剂

补充约束：

- 事件模块属于正式核心模块，不作为“可选未接入”能力处理
- 事件窗口默认覆盖未来 `0-90` 天，以完整支撑系统定义的 `1 周 - 3 个月` 持仓周期


## 4. 交易计划要求（关键）

每个方案必须满足：

✔ 可执行

差：

在回调时买入

好：

若价格守住 5 日均线，在 $120 支撑位附近买入


✔ 风险明确

每笔交易必须包含：
- 入场条件
- 止损逻辑
- 止盈逻辑


✔ 双向方案

必须始终包含：
- 看涨方案
- 看跌方案


## 5. 存储与迭代（次要目标）

### 5.1 存储分析
```json
{
  "ticker": "...",
  "analysis_time": "...",
  "decision_taken": "buy | sell | no_action",
  "outcome": "profit | loss | unknown"
}
```


### 5.2 再分析能力

系统应支持：
- 对比新旧分析
- 检测以下变化：
  - 趋势
  - 情绪
  - 偏向

## 6. 评估指标

系统应支持评估：
- 偏向判断是否正确？
- 入场时机是否合理？
- 止损是否有效防止重大亏损？

## 7. 非功能性需求
- 输出必须为确定性结构化 JSON
- 必须始终包含来源信息
- Python 依赖以 `pyproject.toml` 和 `uv.lock` 为准
- 默认开发命令通过 `uv run` 执行
