# 情绪模块实现架构

## 1. 文档目标

本文档定义情绪模块在实现阶段的代码拆分、标准化输入和迁移路径。

当前实现入口：

- [`app/analysis/sentiment.py`](/Users/leo/Dev/TradePilot/app/analysis/sentiment.py:1)
- [`app/graph/nodes/run_sentiment.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_sentiment.py:1)
- [`tests/graph/nodes/test_run_sentiment.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_sentiment.py:1)

---

## 2. 当前实现事实

当前情绪模块只有关键词命中：

- 输入：最多 5 条 `NewsArticle`
- 规则：标题/摘要里命中 bullish/bearish terms
- 输出：统一 `SentimentSignal`

当前还没有：

- 标题去重
- 相关性过滤
- 新闻基调与时效加权
- 分析师动作和目标价修正
- 叙事主题与拥挤度
- `market_expectation`

---

## 3. 推荐代码组织

```text
app/analysis/sentiment/
  __init__.py
  schemas.py
  module.py
  aggregate.py
  normalize.py
  news_tone.py
  expectation_shift.py
  narrative_crowding.py
```

职责：

- `normalize.py`
  - 标题标准化、去重键、canonical headline
- `news_tone.py`
  - 新闻基调、时效加权、来源覆盖
- `expectation_shift.py`
  - 分析师动作、目标价修正、代理标签
- `narrative_crowding.py`
  - 主导叙事、分歧率、attention spike、crowding
- `aggregate.py`
  - 权重、`sentiment_bias`、`market_expectation`、`key_risks`
- `module.py`
  - 模块总入口

---

## 4. 输入数据契约

当前稳定输入只有：

- `NewsArticle[]`

目标实现至少需要：

- `normalized_news_items`
- `analyst_actions`
- `expectation_proxy_events`
- `mention_series`
- 可选 `social_mentions`

实现要求：

- 标题去重和相关性过滤优先在 normalization 层完成
- 子模块不要直接消费 provider 原始 payload
- `source_trace`、`dedupe_cluster_id`、`classifier_version` 必须在内部模型保留

---

## 5. 输出契约

模块内部聚合结果至少应包含：

- `sentiment_bias`
- `composite_score`
- `news_tone`
- `market_expectation`
- `key_risks`
- `data_completeness_pct`
- `low_confidence_modules`
- `weight_scheme_used`

然后映射为当前 `AnalysisModuleResult`：

- `direction <- sentiment_bias`
- `summary <- sentiment_summary`
- `data_completeness_pct`
- `low_confidence`

---

## 6. 与 runtime 的对接方式

`run_sentiment` 应收敛为：

1. 取标准化情绪数据集
2. 调 `analyze_sentiment_module(...)`
3. 映射回 `AnalysisModuleResult`
4. 维护 diagnostics 与 public source

不要继续在 node 内：

- 做关键词分类
- 拼 summary
- 决定 `market_expectation`

---

## 7. 编码顺序

推荐顺序：

1. `normalize.py`
2. `schemas.py`
3. `news_tone.py`
4. `aggregate.py`
5. `expectation_shift.py`
6. `narrative_crowding.py`

原因：

- 没有标准化和去重层，后面的评分会一直漂

---

## 8. 测试落点

- `tests/analysis/sentiment/test_normalize.py`
- `tests/analysis/sentiment/test_news_tone.py`
- `tests/analysis/sentiment/test_expectation_shift.py`
- `tests/analysis/sentiment/test_narrative_crowding.py`
- `tests/analysis/sentiment/test_aggregate.py`
- 现有 [`test_run_sentiment.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_sentiment.py:1) 保留 node 契约
