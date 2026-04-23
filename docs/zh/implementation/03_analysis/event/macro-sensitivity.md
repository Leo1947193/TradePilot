# 宏观敏感性实现契约

## 1. 目标

实现：

- `macro_event_exposure`
- `macro_sensitivity_level`
- `macro_risk_flag`
- `macro_risk_events`

---

## 2. 输入

- `macro_events`
- `macro_sensitivity_context`
- `analysis_time`
- `holding_horizon_days`

最低要求：

- 每条宏观事件要有时间、类别、重要性、来源
- 标的敏感性上下文至少要能区分是否高敏感

当前 fallback：

- 若没有敏感性上下文，只能做宏观日历存在性判断，最多输出 `degraded`

---

## 3. 实现步骤

1. 先筛未来窗口内宏观事件。
2. 再按行业/风格上下文判定敏感性等级。
3. 只对高敏感近端事件生成 `macro_risk_flag`。
4. 普通宏观事件保留为背景催化剂，不直接改写方向。

---

## 4. 输出口径

建议 schema：

```text
MacroSensitivityResult(
  macro_event_exposure,
  macro_sensitivity_level,
  macro_risk_flag,
  macro_risk_events,
  staleness_days,
  missing_fields,
  low_confidence,
  warnings,
)
```

---

## 5. 测试重点

- 高敏感资产 + 近端高重要性事件
- 低敏感资产不误触发 risk flag
- 缺敏感性上下文时的 degraded 路径
