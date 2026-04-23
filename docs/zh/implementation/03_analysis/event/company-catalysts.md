# 公司催化剂实现契约

## 1. 目标

实现：

- `company_catalysts`
- `binary_event_state`
- `catalyst_direction`
- `risk_event_candidates`

这里覆盖监管、诉讼、并购、产品节点等 richer 公司事件。

---

## 2. 输入

- `company_catalyst_events`
- `analysis_time`
- `holding_horizon_days`

最低要求：

- 每条事件至少有：
  - `event_id`
  - `event_type`
  - `event_state`
  - `expected_date`
  - `direction_hint`
  - `source`

实现约束：

- `rumored`、`unknown` 只能作为低置信度背景信息
- `binary` 事件可以产生风险状态，但不能在结果未知时硬写 bullish/bearish

---

## 3. 实现步骤

1. 按事件状态标准化。
2. 按时间窗口和确认度筛选。
3. 区分：
   - confirmed directional catalysts
   - binary events
   - unresolved negative risks
4. 产出 `catalyst_direction` 和风险候选项。

---

## 4. 输出口径

建议 schema：

```text
CompanyCatalystsResult(
  company_catalysts,
  binary_event_state,
  catalyst_direction,
  risk_event_candidates,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- confirmed positive catalyst
- confirmed negative catalyst
- binary imminent but unresolved
- rumored 事件不误给方向
