# Design Doc - Overview

## 1. System Overview

This system is an intermediate-term U.S. stock analysis agent that generates structured, decision-oriented analysis for a given stock ticker.

The system takes a ticker symbol as the external user input and produces deterministic structured JSON outputs that cover:

- technical analysis signals
- lightweight fundamental analysis signals
- sentiment and expectation signals
- event-driven analysis signals
- synthesized decision outputs
- executable bullish and bearish trade-plan drafts

---

## 2. System Objective

The goal is to standardize pre-trade analysis and reduce subjective decision-making by enforcing a consistent analytical framework.

The system is:

- a decision-support tool, not an automated trading system
- optimized for a 1 week to 3 months holding period
- focused on interpretable and explainable outputs, not complex quantitative modeling

---

## 3. High-Level Architecture

The system is implemented as a multi-stage analysis pipeline.

### 3.1 Data Retrieval and Normalization Layer

Responsible for collecting and normalizing:

- market data
- benchmark data
- news and sentiment sources
- financial summaries
- event and calendar metadata

This layer is also responsible for:

- schema normalization
- benchmark mapping
- missing-data flags
- reproducible `as_of_date` snapshots

---

### 3.2 Analysis Modules

The system decomposes analysis into independent modules:

- Technical Analysis Module
- Fundamental Analysis Module
- Sentiment Analysis Module
- Event Detection Module

Each module:

- consumes normalized input data from the shared data layer
- produces a structured intermediate signal object
- owns only its domain judgment
- must not emit the final system recommendation

---

### 3.3 Decision Layer

Responsible for:

- aggregating signals from all analysis modules
- computing the overall system bias
- resolving conflicts across modules
- assigning the final decision label used by downstream consumers

This layer enforces:

- consistent decision logic
- weighted signal combination
- cross-module conflict handling

---

### 3.4 Trade Plan Generator

Responsible for:

- converting module outputs into executable scenario drafts
- producing both bullish and bearish plans
- using technical levels as planning inputs rather than accepting prebuilt plans from analysis modules

Each plan must include:

- entry conditions
- invalidation or stop logic
- take-profit logic
- scenario assumptions

---

### 3.5 Storage Layer

Provides persistence and evaluation capabilities:

- stores historical analyses
- supports comparison across time
- enables post-trade evaluation

---

## 4. Key Design Principles

### 4.1 Structured Output First

All outputs must conform to strict JSON schemas.

### 4.2 Deterministic Behavior

The system should minimize randomness and ensure reproducible outputs from the same normalized inputs.

### 4.3 Explainability

All conclusions must be traceable to:

- input data
- intermediate analysis
- referenced sources or calculation rules

### 4.4 Modularity

Each component should:

- be independently replaceable
- evolve without breaking the system
- expose a stable interface to downstream layers

---

## 5. System Boundary

### Included

- structured stock analysis
- module-level signal generation
- decision-support outputs
- bullish and bearish trade-plan generation
- historical analysis tracking

### Excluded

- automatic trade execution
- high-frequency trading logic
- long-term investment modeling
- opaque black-box quantitative strategies

---

## 6. Input / Output Contract

### External Input

- ticker symbol

### Internal Working Input

- normalized analysis request with `ticker`, `as_of_date`, and shared market-data bundle

### Output

- deterministic structured JSON objects defined by the system schemas

---

## 7. Design Goals

- Consistency over creativity
- Interpretability over complexity
- Practical usability over theoretical completeness
- Clear module boundaries over duplicated logic
