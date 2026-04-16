# 📊 Intermediate-Term U.S. Stock Decision-Support Agent PRD

## 1. Overview

This project is a **U.S. stock intermediate-term decision-support agent**.

It is designed to:
- Generate **structured analysis before trading decisions**
- Assist human decision-making (not replace it)

### Constraints
- ❌ No automatic trading
- ❌ No high-frequency / short-term trading (< 3 days)
- ❌ No long-term fundamental investing (> 6 months)
- ❌ No complex quantitative models (e.g., factor models, HFT)

### Time Horizon
- Target holding period: **1 week – 3 months**


## 2. Core Task Definition

### Input

```json
{
  "ticker": "string"
}
```

⸻

Output (Strict Schema)
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

  "trade_plan": {
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
  },

  "confidence_score": "0-1 float",

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

## 3. Decision Logic

### 3.1 Bias Determination Rule

The agent MUST determine overall bias based on:

bias =
  technical_signal (weight 0.5) +
  sentiment_signal (weight 0.2) +
  event_signal (weight 0.2) +
  fundamental_signal (weight 0.1)

Mapping rules:
	•	bullish = +1
	•	neutral = 0
	•	bearish = -1

Final decision:
	•	score > 0.3 → bullish
	•	score < -0.3 → bearish
	•	otherwise → neutral



### 3.2 Technical Analysis Scope (STRICT)

Must include:
	•	Trend (based on MA / structure)
	•	Key support & resistance
	•	Volume behavior (expansion / contraction)
	•	Momentum (RSI / MACD direction)

Must NOT include:
	•	Tick-level / intraday scalping signals



### 3.3 Fundamental Analysis Scope (LIGHT ONLY)

Only include:
	•	Revenue / earnings growth direction
	•	Basic valuation (overvalued / fair / undervalued)
	•	Business quality (qualitative)

Must NOT include:
	•	Full DCF
	•	Deep financial modeling


### 3.4 Sentiment Analysis Scope

Sources:
	•	News headlines
	•	Market narratives
	•	Analyst expectations (optional)

Output:
	•	tone classification
	•	summarized expectation



### 3.5 Event-Driven Scope

Include:
	•	Earnings date
	•	Macro-sensitive events (Fed, CPI)
	•	Company-specific catalysts


## 4. Trade Plan Requirements (CRITICAL)

Each scenario MUST be:

✔ Executable

Bad:

buy on pullback

Good:

buy near $120 support if price holds above 5-day MA


✔ Risk-defined

Each trade must include:
	•	entry condition
	•	stop loss logic
	•	take profit logic


✔ Two-sided

Must always include:
	•	bullish scenario
	•	bearish scenario


## 5. Storage & Iteration (Secondary Goals)

### 5.1 Store Analysis
```json
{
  "ticker": "...",
  "analysis_time": "...",
  "decision_taken": "buy | sell | no_action",
  "outcome": "profit | loss | unknown"
}
```


### 5.2 Reanalysis Capability

System should support:
	•	Compare old vs new analysis
	•	Detect changes in:
	•	trend
	•	sentiment
	•	bias

## 6. Evaluation Metrics

The system should allow evaluating:
	•	Was bias correct?
	•	Was entry timing reasonable?
	•	Did stop-loss prevent large loss?

## 7. Non-Functional Requirements
	•	Output must be deterministic structured JSON
	•	Must always include sources
