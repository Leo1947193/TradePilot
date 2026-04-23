# 事件风险与方向聚合实现契约

## 1. 目标

聚合器负责：

- 统一时间权重
- 生成 `event_bias`
- 生成 `upcoming_catalysts`
- 生成 `risk_events`
- 生成受控 `event_risk_flags`
- 计算 `data_completeness_pct`

当前 `analyze_event_inputs(...)` 是占位版统一计数器；后续应由独立 `aggregate.py` 替代。

---

## 2. 输入

- `ScheduledEventsResult`
- `MacroSensitivityResult`
- `CompanyCatalystsResult`

---

## 3. 实现步骤

1. 先收集近端风险项。
2. 先生成受控 `event_risk_flags`：
   - `binary_event_imminent`
   - `earnings_within_3d`
   - `regulatory_decision_imminent`
   - `macro_event_high_sensitivity`
3. 再看是否存在已确认且方向明确的正/负面催化剂。
4. 最后产出 `event_bias`。

实现约束：

- 风险旗标优先服务执行性，不直接等价于 bearish
- 未确认二元事件优先压制执行性，不优先改写方向

---

## 4. 输出到当前 runtime 的映射

模块总入口应返回：

- richer `EventAggregateResult`
- 当前兼容 `AnalysisModuleResult`

映射规则：

- `direction <- event_bias`
- `summary <- event_summary`
- `data_completeness_pct`
- `low_confidence`

系统级 `blocking_flags` 由 `decision_synthesis` 消费 `event_risk_flags` 后再决定，不在事件模块内直接生成系统总状态。

---

## 5. 测试重点

- `earnings_within_3d`
- `binary_event_imminent`
- `macro_event_high_sensitivity`
- 有风险但方向仍 neutral 的场景
- confirmed positive/negative catalyst 对 `event_bias` 的影响
