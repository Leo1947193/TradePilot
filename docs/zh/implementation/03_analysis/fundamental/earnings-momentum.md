# 盈利动量实现契约

## 1. 目标

实现：

- `eps_beat_streak_quarters`
- `avg_eps_surprise_pct_4q`
- `avg_revenue_surprise_pct_4q`
- `eps_revision_balance_30d/60d`
- `revenue_revision_balance_30d`
- `guidance_trend`
- `current_quarter_bar`
- `earnings_momentum`
- `earnings_score`

---

## 2. 输入

- `quarterly_results`
- `revision_summary`
- `current_quarter_consensus`
- `guidance_history`
- `analysis_time`

最低要求：

- 最近 4 个有效季度结果
- 最近 30/60 天修正摘要

当前 fallback：

- 若只有 `FinancialSnapshot`，允许输出一个 `degraded` 的占位结果，但不要伪造上述字段

---

## 3. 实现步骤

1. 标准化季度结果并按时间排序。
2. 计算 EPS / revenue surprise。
3. 计算 beat streak。
4. 计算 30/60 天修正平衡。
5. 匹配最近有效 guidance。
6. 生成 `earnings_momentum` 标签。
7. 再按 design 映射 `earnings_score`。

实现约束：

- 一致预期修正和 guidance 只能来自明确结构化输入，不允许从普通新闻 summary 逆推
- 缺失数据要进入 `missing_fields`，不要静默按 0 处理

---

## 4. 输出口径

建议 schema：

```text
EarningsMomentumResult(
  earnings_momentum,
  earnings_score,
  metrics,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- beat streak
- revision balance 正负方向
- `guidance_trend` 四态
- 缺少 guidance 时不误判为负面
- 数据过旧时的 degraded/excluded 行为
