# 决策综合评分与冲突实现契约

## 1. 文档目标

本文档定义系统级评分、方向、冲突和可执行性判定的落地方式。

相关代码：

- [`app/analysis/decision.py`](/Users/leo/Dev/TradePilot/app/analysis/decision.py:1)
- [`app/graph/nodes/synthesize_decision.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/synthesize_decision.py:1)

---

## 2. 当前实现事实

当前系统已经实现：

- 固定配置权重：
  - technical `0.5`
  - fundamental `0.1`
  - sentiment `0.2`
  - event `0.2`
- 可用模块归一化
- `bias_score = sum(contribution)`
- `aligned/mixed/conflicted`
- `confidence_score`
- `actionability_state`

当前实现还与 design 明显不同：

### 2.1 方向阈值不同

当前代码：

- `bias_score >= 0.15` -> bullish
- `bias_score <= -0.15` -> bearish

design 目标：

- `> 0.30`
- `< -0.30`

这意味着当前实现更敏感、更容易给单边方向。

### 2.2 压制规则缺失

design 要求：

- `available_weight_ratio < 0.70` 压 neutral
- `conflicted` 压 neutral
- `data_completeness_pct < 60` 压 neutral
- `fundamental_long_disqualified` 禁止净看多

当前实现没有这些显式压制链，只是在 `confidence_score` 和 `actionability_state` 上做弱化。

### 2.3 阻断标记过于简化

当前 `_build_blocking_flags(...)` 只有一条：

- event module direction 为 `bearish/disqualified` -> `event_risk_block`

这不是 design 定义的受控系统级阻断集合。

### 2.4 `actionability_state` 过于依赖 blocking_flags

当前规则：

- 没有 usable 模块或有任意 blocking flag -> `avoid`
- neutral / low confidence / conflicted -> `watch`
- 其他 -> `actionable`

这仍是轻量版，并未显式接通技术 `setup_state` 与事件近端风险旗标。

---

## 3. 推荐代码组织

推荐把当前 [`app/analysis/decision.py`](/Users/leo/Dev/TradePilot/app/analysis/decision.py:1) 演进为：

```text
app/analysis/synthesis/scoring.py
```

内部至少拆成 5 组纯函数：

- `calculate_weight_scheme(...)`
- `calculate_bias_score(...)`
- `determine_conflict_state(...)`
- `apply_direction_constraints(...)`
- `calculate_confidence_and_actionability(...)`

这样可以把“先打分，再压制，再算置信度”的顺序写死。

---

## 4. 评分顺序

后续实现必须固定如下顺序：

1. 计算 `enabled_weight_sum`
2. 计算 `available_weight_sum`
3. 计算 `available_weight_ratio`
4. 计算 `applied_weight`
5. 计算每个模块 `contribution`
6. 计算原始 `bias_score`
7. 计算 `conflict_state`
8. 计算 `data_completeness_pct`
9. 生成 `overall_bias_preliminary`
10. 应用方向压制
11. 生成最终 `overall_bias`
12. 计算 `confidence_score`
13. 计算 `actionability_state`

实现要求：

- 不要先算最终方向再回头改 `bias_score`
- `bias_score` 是事实分数，压制只改 `overall_bias`

---

## 5. 当前保留与目标迁移

### 5.1 当前阶段应保留的逻辑

- 配置权重值
- `contribution = direction_value * applied_weight`
- `mixed/conflicted` 的 gap 规则
- `0.55/0.45` 的 confidence 基础配比
- `0.1/0.2` 的冲突惩罚

这些已经被当前 tests 和 response schema 固化，短期内不要直接推翻。

### 5.2 下一阶段必须补上的逻辑

- `overall_bias_preliminary`
- 方向压制链
- 受控 `blocking_flags`
- 技术 `setup_state = avoid` 对 `actionability_state` 的显式驱动
- 事件近端风险对 `actionability_state` 的显式驱动
- 基本面 `disqualified` 的净看多压制

---

## 6. `bias_score` 与 `conflict_state`

当前 `conflict_state` 判定本身与 design 大体一致，可继续保留：

- 只有单侧方向或无方向 -> `aligned`
- 双侧都有方向且 gap >= 0.30 -> `mixed`
- 双侧都有方向且 gap < 0.30 -> `conflicted`

实现约束：

- `neutral` 不计入 bullish/bearish 权重
- `disqualified` 计入 bearish 侧

---

## 7. `confidence_score`

当前实现：

```text
raw_score =
  available_weight_ratio * 0.55 +
  supporting_weight * 0.45 -
  low_confidence_penalty -
  conflict_penalty
```

这套公式当前可保留，但应补两个约束：

1. `overall_bias` 被压制为 neutral 后，`confidence_score` 仍然代表“证据稳定度”，不自动归零。
2. 若 `available_weight_sum = 0`，则 `confidence_score = 0.0`。

---

## 8. `actionability_state`

当前实现应视为过渡版。

目标落地应改成显式消费：

- 技术模块 `setup_state`
- 事件模块 `event_risk_flags`
- 系统级 `blocking_flags`
- `confidence_score`
- `overall_bias`

建议顺序：

1. 若所有已启用模块都 excluded -> `avoid`
2. 若存在系统级硬阻断 -> `avoid`
3. 若技术聚合器给 `avoid` -> `avoid`
4. 若 `overall_bias = neutral` 或 `confidence_score` 低 -> `watch`
5. 其他 -> `actionable`

---

## 9. 当前实现与目标实现差异

| 主题 | 当前实现 | 目标实现 |
|---|---|---|
| 方向阈值 | `±0.15` | preliminary `±0.30` + 压制链 |
| 系统阻断 | 仅 `event_risk_block` | 受控阻断枚举 |
| 基本面否决 | 数值上按 bearish 参与 | 还要禁止净看多 |
| 技术 avoid | 未接入 | 显式压制 actionability |
| 事件近端风险 | 未接入 | 显式压制 actionability |

---

## 10. 测试重点

- 方向阈值边界
- `mixed/conflicted` gap 边界
- `available_weight_ratio < 0.70` 压制链
- `fundamental disqualified` 禁止净看多
- 技术 `setup_state = avoid` 与事件风险旗标对 `actionability_state` 的影响
