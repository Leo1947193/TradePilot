# 财务健康实现契约

## 1. 目标

实现：

- `overall_rating`
- `disqualify`
- `hard_risk_reasons`
- `checks`
- `health_score`
- `data_staleness_days`

这是基本面模块里最先影响系统约束的子模块。

---

## 2. 输入

- 最近 4 个季度：
  - CFO
  - Capex
  - Net income
  - Cash
  - Short-term debt
  - Current assets / liabilities
  - Interest expense
  - EBITDA 或可替代口径

最低要求：

- 能完整计算 design 中的硬风险规则，否则最多输出 `degraded`

---

## 3. 实现步骤

1. 先计算基础指标：
   - FCF
   - `FCF / Net Income`
   - `CFO / Net Income`
   - `cash_to_short_term_debt`
   - `interest_coverage`
   - `current_ratio`
   - `net_debt_to_ebitda`
2. 再生成 4 类 check。
3. 再判红旗。
4. 最后执行 `disqualify`。

实现约束：

- `disqualify` 必须晚于指标计算、早于模块聚合
- 只有 design 明确列出的近端硬风险可以触发否决；不要把一般“高风险”直接升级成 `disqualify`

---

## 4. 输出口径

建议 schema：

```text
FinancialHealthResult(
  overall_rating,
  disqualify,
  hard_risk_reasons,
  checks,
  health_score,
  data_staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 与聚合器的关系

- 聚合器必须先读 `disqualify`
- 触发时直接压制 `fundamental_bias = disqualified`
- `hard_risk_reasons` 是 `key_risks` 的最高优先级来源

---

## 6. 测试重点

- 三条硬风险规则
- `overall_rating` 高风险但未取消资格
- 缺关键字段时不能误触发 `disqualify`
- 时效性超过阈值时的压制行为
