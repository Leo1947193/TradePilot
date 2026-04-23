# 财报与已排程事件实现契约

## 1. 目标

实现：

- `days_to_next_earnings`
- `earnings_window_state`
- `scheduled_catalysts`
- `near_term_scheduled_risks`

这份文档覆盖 design overview 里的“财报日期与公司日历”部分。

---

## 2. 输入

- `scheduled_company_events`
- `analysis_time`
- `holding_horizon_days`

最低要求：

- 事件必须至少有 `event_type`、`scheduled_at/event_date`、`event_status`、`source`

实现约束：

- 未知时间点的“将举行某活动”不进入近端窗口计算
- 财报要单独保留盘前/盘后属性

---

## 3. 实现步骤

1. 先筛未来窗口内已排程事件。
2. 单独识别最近一次财报并计算 `days_to_next_earnings`。
3. 按 `0-3 / 4-14 / 15-90` 天分层。
4. 产出 `earnings_window_state` 和 `scheduled_catalysts`。

---

## 4. 输出口径

建议 schema：

```text
ScheduledEventsResult(
  days_to_next_earnings,
  earnings_window_state,
  scheduled_catalysts,
  near_term_scheduled_risks,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 财报在 3 天内
- 财报在 4-14 天
- 非财报公司日历事件排序
- `event_status` 不是 confirmed/scheduled 时的处理
