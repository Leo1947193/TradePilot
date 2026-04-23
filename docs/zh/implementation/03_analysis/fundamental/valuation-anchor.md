# 估值锚点实现契约

## 1. 目标

实现：

- `primary_metric_used`
- `historical_percentile`
- `peer_relative_ratio`
- `peg_flag`
- `space_rating`
- `valuation_score`

---

## 2. 输入

- 当前估值 snapshot
- 历史估值序列
- 同行估值样本
- PEG 所需增长数据

最低要求：

- 至少要能选择一个有效主指标并计算一个可比较锚点

---

## 3. 实现步骤

1. 根据公司类型和行业选择主指标。
2. 计算历史分位。
3. 计算同行相对估值。
4. 若适用则计算 PEG 与 `peg_flag`。
5. 最后生成 `space_rating` 和 `valuation_score`。

实现约束：

- 主指标选择规则必须是固定决策表，不允许多指标平均后“灵活解释”
- 当前倍数为负值或不可比较时，要显式降级，不要偷偷换口径但不记录

---

## 4. 输出口径

建议 schema：

```text
ValuationAnchorResult(
  primary_metric_used,
  historical_percentile,
  peer_relative_ratio,
  peg_flag,
  space_rating,
  valuation_score,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 主指标选择决策表
- 历史分位窗口不足
- 同行样本不足
- PEG 不适用时的回退路径
- `space_rating` 四态
