# 新闻基调实现契约

## 1. 目标

实现：

- `news_tone`
- `recency_weighted_tone`
- `positive_headline_ratio_7d`
- `negative_headline_ratio_7d`
- `source_diversity_7d`
- `headline_relevance_coverage`
- `news_score`
- evidence 级 canonical headlines

---

## 2. 输入

- `normalized_news_items`
- `analysis_time`
- `company identity context`

最低要求：

- 最近 7/30 天窗口内的标题级记录
- 每条记录可回溯到 `url`

实现约束：

- 去重必须早于情绪统计
- `headline` 是主判断源，`summary` 只能补充，不能反转标题方向

---

## 3. 实现步骤

1. 标题标准化。
2. 去重并生成 `dedupe_cluster_id`。
3. 过滤低相关记录。
4. 对有效标题打固定事件/情绪标签。
5. 计算 7 天正负占比和 30 天时效加权。
6. 生成 `news_tone` 与 `news_score`。
7. 选取少量 canonical headlines 作为 evidence。

---

## 4. 输出口径

建议 schema：

```text
NewsToneResult(
  news_tone,
  recency_weighted_tone,
  positive_headline_ratio_7d,
  negative_headline_ratio_7d,
  source_diversity_7d,
  headline_relevance_coverage,
  news_score,
  evidence,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 去重优先级
- relevance coverage
- recency weighting
- 样本不足时的 degraded 路径
- evidence 标题与 `dedupe_cluster_id` 可追溯
