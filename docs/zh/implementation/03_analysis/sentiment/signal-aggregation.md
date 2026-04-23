# 情绪模块聚合实现契约

## 1. 目标

聚合器负责：

- 映射新闻/预期/叙事三个方向子信号
- 计算内部规范分数 `normalized_composite_score`
- 生成 `sentiment_bias`
- 生成 `market_expectation`
- 提取 `key_risks`
- 计算 `data_completeness_pct`

当前 `analyze_news_sentiment(...)` 只是占位版统一打分器；后续应由独立 `aggregate.py` 替代。

---

## 2. 输入

- `NewsToneResult`
- `ExpectationShiftResult`
- `NarrativeCrowdingResult`

固定权重：

- `news = 0.40`
- `expectation = 0.35`
- `narrative = 0.25`

---

## 3. 实现步骤

1. 先判断三个子模块的 `usable / degraded / excluded`。
2. 先做方向子信号映射。
3. 再对可用模块做权重归一化。
4. 生成 `sentiment_bias`。
5. 再生成 `market_expectation` 说明文本。

实现约束：

- `market_expectation` 必须由结构化字段模板生成，不允许直接拼接 provider 原文
- `available_weight_sum < 0.70` 时不能给出强方向
- 若外层仍保留 `composite_score` 兼容字段，其值必须与 `normalized_composite_score` 一致

---

## 4. 输出到当前 runtime 的映射

模块总入口应返回：

- richer `SentimentAggregateResult`
- 当前兼容 `AnalysisModuleResult`

映射规则：

- `direction <- sentiment_bias`
- `summary <- sentiment_summary / market_expectation`
- `data_completeness_pct`
- `low_confidence`

---

## 5. 测试重点

- 三个方向子信号映射
- 权重归一化
- `market_expectation` 模板分支
- `key_risks` 去重与截断
- `available_weight_sum < 0.70` 压制
