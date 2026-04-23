# 叙事与拥挤度实现契约

## 1. 目标

实现：

- `dominant_bullish_narratives`
- `dominant_bearish_narratives`
- `dominant_bullish_theme_share`
- `dominant_bearish_theme_share`
- `contradiction_ratio`
- `attention_zscore_7d`
- `crowding_flag`
- `narrative_state`
- `narrative_score`

---

## 2. 输入

- `normalized_news_items`
- `mention_series`
- 可选 `social_mentions`

最低要求：

- 最近 14 天方向性标题
- 最近 90 天 mention baseline

实现约束：

- 主题必须落在固定字典，不允许自由生成新主类别参与主统计
- `attention_zscore_7d` 缺基线时可回退为 0，但必须记 warning

---

## 3. 实现步骤

1. 再次按去重后标题做主题提取。
2. 统计 bullish/bearish theme share。
3. 计算 `contradiction_ratio`。
4. 计算 7 天 attention 与 90 天 baseline 的 z-score。
5. 判 `crowding_flag`。
6. 再生成 `narrative_state` 和 `narrative_score`。

---

## 4. 输出口径

建议 schema：

```text
NarrativeCrowdingResult(
  dominant_bullish_narratives,
  dominant_bearish_narratives,
  dominant_bullish_theme_share,
  dominant_bearish_theme_share,
  contradiction_ratio,
  attention_zscore_7d,
  crowding_flag,
  narrative_state,
  narrative_score,
  theme_trace,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 主题提取固定字典
- contradiction ratio
- attention z-score
- baseline 不足时的回退
- 单一来源放大时的 low confidence
