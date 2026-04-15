# TradePilot — Agent 系统指南

## 项目概述

TradePilot 是一个**美股次中期决策支持系统**，基于多智能体分析流水线构建。系统以股票代码作为输入，生成确定性的结构化 JSON 分析报告和可执行的交易计划。

- 目标持仓周期：**1 周 – 3 个月**
- 这是一个**决策支持工具**，而非自动化交易系统
- 所有输出必须可解释、可追溯至数据源，并符合定义的 JSON schema

---

## 系统流水线

```
用户输入（股票代码）
  → 数据验证
  → [并行] 技术分析 | 基本面分析 | 情绪分析 | 事件分析
  → 决策综合
  → 交易计划生成
  → 结构化 JSON 输出
```

---

## Agent 定义

### 1. Agent 任务分发器

**角色：** 入口点。验证输入并将任务并行分发至所有分析 Agent。

**输入：**
```json
{ "ticker": "string" }
```

**职责：**
- 验证股票代码是否为真实的美股代码
- 同时将任务分发至四个分析模块
- 向下游传递市场数据（OHLCV、期权、卖空兴趣）和分发指令（代码、时间窗口、优先级）

**禁止：**
- 在分发其他模块前阻塞任何单个模块
- 做出分析判断

---

### 2. 技术分析模块

该模块由并行运行后聚合的子 Agent 组成。

#### 2a. 多周期结构分析
- 分析日线 + 周线图共振
- 识别均线排列和关键价格位（支撑/阻力）

#### 2b. 动量与强度量化
- 计算 RSI、MACD、ADX
- 计算相对于 SPY 的相对强度

#### 2c. 价量关系分析
- 检测突破确认或低量回调
- 计算 OBV 并识别背离

#### 2d. 形态识别
- 识别图表形态：旗形、杯柄形、VCP
- 根据形态几何计算目标价和止损位

#### 2e. 风险指标计算
- 计算 ATR、Beta、布林带宽度
- 测量近期最大回撤

**聚合输出 schema：**
```json
{
  "trend": "bullish | bearish | neutral",
  "key_support": ["number"],
  "key_resistance": ["number"],
  "volume_pattern": "string",
  "momentum": "string",
  "technical_summary": "string"
}
```

**范围约束：**
- 包含：趋势（均线/结构）、关键支撑/阻力、成交量行为、动量（RSI/MACD）
- 排除：tick 级别或日内剥头皮信号

---

### 3. 基本面分析模块

**角色：** 轻量级定性基本面评估，并非深度财务模型。

**输出 schema：**
```json
{
  "growth": "string",
  "valuation_view": "string",
  "business_quality": "string",
  "fundamental_summary": "string"
}
```

**范围约束：**
- 包含：营收/盈利增长方向、基础估值（高估/合理/低估）、商业质量（定性）
- 排除：完整 DCF、复杂财务建模

---

### 4. 情绪分析模块

**角色：** 对新闻基调进行分类并概括市场叙事。

**来源：**
- 新闻标题
- 市场叙事
- 分析师预期（可选）

**输出 schema：**
```json
{
  "news_tone": "positive | neutral | negative",
  "market_expectation": "string",
  "sentiment_summary": "string"
}
```

---

### 5. 事件检测模块

**角色：** 识别即将到来的催化剂和风险事件。

**输出 schema：**
```json
{
  "upcoming_catalysts": ["string"],
  "risk_events": ["string"],
  "event_summary": "string"
}
```

**必须覆盖：**
- 财报日期
- 宏观敏感事件（美联储会议、CPI 发布）
- 公司特定催化剂

---

### 6. 决策综合 Agent（主调度 Agent）

**角色：** 将所有四个模块的信号聚合为统一的偏向分数和总体判断。

**偏向评分公式：**

```
bias_score =
  technical_signal  × 0.5 +
  sentiment_signal  × 0.2 +
  event_signal      × 0.2 +
  fundamental_signal × 0.1
```

信号映射：`bullish = +1`，`neutral = 0`，`bearish = -1`

最终偏向判断：
- `score > 0.3` → `bullish`（看涨）
- `score < -0.3` → `bearish`（看跌）
- 其他 → `neutral`（中性）

**职责：**
- 严格执行加权评分公式——不得以主观判断覆盖
- 生成 `confidence_score`（0–1 浮点数），反映信号一致性
- 汇总所有模块的 `risks` 列表
- 收集所有模块使用的 `sources`

---

### 7. 交易计划生成器

**角色：** 生成可执行、风险明确、双向的交易方案。

**输出 schema：**
```json
{
  "bias": "bullish | neutral | bearish",
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

**关键要求：**

每个方案必须包含全部三项：`entry_idea`、`take_profit`、`stop_loss`。

入场思路必须具体且可执行：
- 差：`"在回调时买入"`
- 好：`"若价格守住 5 日均线，在 $120 支撑位附近买入"`

无论偏向如何，看涨和看跌方案均为必填。

---

### 8. 风险管理 Agent

**角色：** 下游消费者。将最终报告转化为仓位大小和止损建议提供给用户。

该 Agent 读取结构化 JSON 输出——不独立进行分析。

---

## 最终输出 Schema

所有 Agent 共同生成一个确定性 JSON：

```json
{
  "ticker": "string",
  "analysis_time": "ISO datetime",
  "technical_analysis": { ... },
  "fundamental_analysis": { ... },
  "sentiment_expectations": { ... },
  "event_driven_analysis": { ... },
  "trade_plan": { ... },
  "confidence_score": "0–1 float",
  "risks": ["string"],
  "sources": [
    {
      "type": "technical | news | financial | macro",
      "name": "string",
      "url": "string"
    }
  ]
}
```

---

## 所有 Agent 的设计原则

1. **结构化输出优先** — 每个 Agent 的输出必须符合其定义的 schema。不得在 schema 字段之外自由叙述。
2. **确定性行为** — 最小化随机性；相同输入应产生相同输出。
3. **可解释性** — 每个结论必须可追溯至输入数据和引用来源。始终填充 `sources` 数组。
4. **模块化** — 每个 Agent 可独立替换。Agent 不得假设另一个 Agent 的内部实现。
5. **禁止自动交易** — Agent 仅提供分析和建议。最终决策属于人类。

---

## 范围边界

| 范围内 | 范围外 |
|---|---|
| 结构化股票分析 | 自动交易执行 |
| 决策支持输出 | 高频/日内交易 |
| 交易计划生成 | 长期投资（> 6 个月） |
| 历史分析追踪 | 复杂量化/因子模型 |

---

## 存储与再分析（次要功能）

分析结果可通过以下字段持久化存储：

```json
{
  "ticker": "...",
  "analysis_time": "...",
  "decision_taken": "buy | sell | no_action",
  "outcome": "profit | loss | unknown"
}
```

系统应支持对比新旧分析，以检测趋势、情绪或偏向随时间的变化。
