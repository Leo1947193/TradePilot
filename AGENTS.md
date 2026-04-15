# TradePilot — Agent System Guide

## Project Overview

TradePilot is a **U.S. stock intermediate-term decision-support system** built as a multi-agent analysis pipeline. It takes a stock ticker as input and produces a deterministic, structured JSON analysis report with executable trading plans.

- Target holding period: **1 week – 3 months**
- This is a **decision-support tool**, not an automated trading system
- All outputs must be explainable, traceable to sources, and conform to the defined JSON schema

---

## System Pipeline

```
User Input (ticker)
  → Data Validation
  → [Parallel] Technical Analysis | Fundamental Analysis | Sentiment Analysis | Event Analysis
  → Decision Synthesis
  → Trade Plan Generation
  → Structured JSON Output
```

---

## Agent Definitions

### 1. Agent Task Dispatcher

**Role:** Entry point. Validates input and fans out tasks to all analysis agents in parallel.

**Input:**
```json
{ "ticker": "string" }
```

**Responsibilities:**
- Validate that the ticker is a real U.S. equity symbol
- Dispatch to all four analysis modules simultaneously
- Pass market data (OHLCV, options, short interest) and dispatch instructions (ticker, time window, priority) downstream

**Must NOT:**
- Block on any single module before dispatching others
- Make analysis judgments

---

### 2. Technical Analysis Module

This module is itself composed of sub-agents that run in parallel, then aggregate.

#### 2a. Multi-Timeframe Structure Analysis
- Analyzes daily + weekly chart resonance
- Identifies MA alignment and key price levels (support/resistance)

#### 2b. Momentum & Strength Quantification
- Computes RSI, MACD, ADX
- Calculates relative strength vs. SPY

#### 2c. Price-Volume Relationship Analysis
- Detects breakout confirmation or low-volume pullbacks
- Computes OBV and identifies divergences

#### 2d. Pattern Recognition
- Identifies chart patterns: Flag, Cup-and-Handle, VCP
- Calculates target price and stop-loss from pattern geometry

#### 2e. Risk Metric Calculation
- Computes ATR, Beta, Bollinger Band Width
- Measures recent max drawdown

**Aggregated output schema:**
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

**Scope constraints:**
- Include: trend (MA/structure), key support/resistance, volume behavior, momentum (RSI/MACD)
- Exclude: tick-level or intraday scalping signals

---

### 3. Fundamental Analysis Module

**Role:** Lightweight qualitative fundamental assessment. Not a deep financial model.

**Output schema:**
```json
{
  "growth": "string",
  "valuation_view": "string",
  "business_quality": "string",
  "fundamental_summary": "string"
}
```

**Scope constraints:**
- Include: revenue/earnings growth direction, basic valuation (overvalued/fair/undervalued), business quality (qualitative)
- Exclude: full DCF, complex financial modeling

---

### 4. Sentiment Analysis Module

**Role:** Classify news tone and summarize market narrative.

**Sources:**
- News headlines
- Market narratives
- Analyst expectations (optional)

**Output schema:**
```json
{
  "news_tone": "positive | neutral | negative",
  "market_expectation": "string",
  "sentiment_summary": "string"
}
```

---

### 5. Event Detection Module

**Role:** Identify upcoming catalysts and risk events.

**Output schema:**
```json
{
  "upcoming_catalysts": ["string"],
  "risk_events": ["string"],
  "event_summary": "string"
}
```

**Must cover:**
- Earnings dates
- Macro-sensitive events (Fed meetings, CPI releases)
- Company-specific catalysts

---

### 6. Decision Synthesis Agent (Master Scheduler Agent)

**Role:** Aggregate signals from all four modules into a unified bias score and overall verdict.

**Bias scoring formula:**

```
bias_score =
  technical_signal  × 0.5 +
  sentiment_signal  × 0.2 +
  event_signal      × 0.2 +
  fundamental_signal × 0.1
```

Signal mapping: `bullish = +1`, `neutral = 0`, `bearish = -1`

Final bias decision:
- `score > 0.3` → `bullish`
- `score < -0.3` → `bearish`
- otherwise → `neutral`

**Responsibilities:**
- Enforce the weighted scoring formula — do not override with subjective judgment
- Produce `confidence_score` (0–1 float) reflecting signal agreement
- Aggregate `risks` list from all modules
- Collect all `sources` used across modules

---

### 7. Trade Plan Generator

**Role:** Produce executable, risk-defined, two-sided trading scenarios.

**Output schema:**
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

**Critical requirements:**

Every scenario MUST include all three: `entry_idea`, `take_profit`, `stop_loss`.

Entry ideas must be specific and executable:
- Bad: `"buy on pullback"`
- Good: `"buy near $120 support if price holds above 5-day MA"`

Both bullish and bearish scenarios are always required, regardless of bias.

---

### 8. Risk Management Agent

**Role:** Downstream consumer. Translates the final report into position sizing and stop-loss advice for the user.

This agent reads the structured JSON output — it does not produce analysis independently.

---

## Final Output Schema

All agents collectively produce one deterministic JSON:

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

## Design Principles for All Agents

1. **Structured output first** — every agent produces output that conforms to its defined schema. No free-form narrative without a schema-backed field.
2. **Deterministic behavior** — minimize randomness; same inputs should yield the same outputs.
3. **Explainability** — every conclusion must be traceable to input data and referenced sources. Always populate the `sources` array.
4. **Modularity** — each agent is independently replaceable. An agent must not assume the internal implementation of another agent.
5. **No automatic trading** — agents provide analysis and suggestions only. Final decisions belong to the human.

---

## Scope Boundaries

| In scope | Out of scope |
|---|---|
| Structured stock analysis | Automatic trade execution |
| Decision-support outputs | High-frequency / intraday trading |
| Trade plan generation | Long-term investing (> 6 months) |
| Historical analysis tracking | Complex quantitative / factor models |

---

## Storage & Reanalysis (Secondary)

Analyses may be persisted with:

```json
{
  "ticker": "...",
  "analysis_time": "...",
  "decision_taken": "buy | sell | no_action",
  "outcome": "profit | loss | unknown"
}
```

The system should support comparing old vs. new analyses to detect changes in trend, sentiment, or bias over time.
