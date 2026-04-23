# 预期变化实现契约

## 1. 目标

实现：

- `analyst_action_balance_30d`
- `target_revision_median_pct_30d`
- `expectation_headline_balance_14d`
- `estimate_attention_level`
- `expectation_shift`
- `expectation_score`

---

## 2. 输入

- `analyst_actions`
- `expectation_proxy_events`
- `analysis_time`

最低要求：

- 最近 30/60 天分析师动作
- 最近 14 天预期代理标签

实现约束：

- 分析师动作和代理标签都要去重
- 不能拿普通新闻情绪代替预期变化输入

---

## 3. 实现步骤

1. 标准化动作方向和目标价口径。
2. 按稳定去重键去重。
3. 计算动作平衡、目标价中位数修正。
4. 聚合 14 天代理标签平衡。
5. 映射 `estimate_attention_level`。
6. 生成 `expectation_shift` 和 `expectation_score`。

---

## 4. 输出口径

建议 schema：

```text
ExpectationShiftResult(
  expectation_shift,
  expectation_score,
  analyst_action_balance_30d,
  target_revision_median_pct_30d,
  expectation_headline_balance_14d,
  estimate_attention_level,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 分析师动作去重
- 目标价上修/下修中位数
- 代理标签平衡
- 样本量不足时的 low confidence
- 数据过旧时的 degraded/excluded
