# 决策综合输出实现契约

## 1. 文档目标

本文档定义 `decision_synthesis` 的最终输出对象如何构造，以及它和下游 `trade_plan` 的边界。

相关代码：

- [`app/schemas/api.py`](/Users/leo/Dev/TradePilot/app/schemas/api.py:1)
- [`app/graph/nodes/synthesize_decision.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/synthesize_decision.py:1)
- [`app/analysis/trade_plan.py`](/Users/leo/Dev/TradePilot/app/analysis/trade_plan.py:1)

---

## 2. 当前实现事实

当前输出对象已经稳定为 `DecisionSynthesis`：

- `overall_bias`
- `bias_score`
- `confidence_score`
- `actionability_state`
- `conflict_state`
- `data_completeness_pct`
- `weight_scheme_used`
- `blocking_flags`
- `module_contributions`
- `risks`

这一层已经被：

- `assemble_response`
- `persist_analysis`
- `generate_trade_plan`

共同消费，因此字段名短期内不要改。

---

## 3. 当前实现的主要问题

### 3.1 输出对象兼具“内部事实”和“过渡字段”

当前 `module_contributions` 既是解释对象，也承担了部分适配结果角色。后续应让：

- `NormalizedModuleSignal` 负责内部适配
- `ModuleContribution` 只负责最终输出

### 3.2 `blocking_flags` 还不是受控设计集合

当前只会输出：

- `event_risk_block`

但 design 要求的系统级阻断更细。

### 3.3 `risks` 目前只是轻量提示

当前 `_build_risks(...)` 只会输出三类摘要：

- 只有降级模块结果
- 关键模块证据不足
- 降级模块较多

目标态需要从模块级风险和系统级约束中按优先级提取。

---

## 4. `weight_scheme_used` 输出规则

当前实现已经较接近目标态，建议保留：

- `configured_weights`
- `enabled_modules`
- `disabled_modules`
- `enabled_weight_sum`
- `available_weight_sum`
- `available_weight_ratio`
- `applied_weights`
- `renormalized`

实现要求：

- number 精度继续保持当前 4 位小数
- 即使未来引入独立适配层，这个 public shape 也应继续保持
- `applied_weights` 对 unavailable 模块必须显式为 `null`

---

## 5. `module_contributions` 输出规则

当前 `module_contributions` 已经满足：

- 固定四项
- 顺序固定
- 每项都带启用状态、方向、权重、贡献、完整度、低置信度

后续要求：

1. 保留这个 public shape 不动。
2. 不要在这里扩塞模块内部原始字段。
3. richer 审计字段应放内部 schema 或 persistence JSON，而不是 public `DecisionSynthesis`。

实现约束：

- `contribution` 必须来自未舍入内部值后再输出 4 位小数
- `bias_score` 与所有非空 contribution 求和的差异只能来自舍入

---

## 6. `blocking_flags` 输出规则

后续应把当前自由字符串收敛到受控集合：

- `technical_setup_avoid`
- `fundamental_long_disqualified`
- `binary_event_imminent`
- `earnings_within_3d`
- `regulatory_decision_imminent`
- `macro_event_high_sensitivity`
- `all_enabled_modules_excluded`

迁移策略：

1. 先保留当前 `event_risk_block`，但仅作为过渡实现标记。
2. 引入适配层和事件聚合器后，再切换到受控枚举。
3. 切换时同步更新：
   - `trade_plan`
   - tests
   - persistence 文档

---

## 7. `risks` 输出规则

当前 `risks` 应继续视为系统级摘要，而不是完整风险明细。

后续实现要求：

1. 先汇总系统级压制原因。
2. 再汇总模块级高优先风险。
3. 去重。
4. 截断到最多 6 条。

来源优先级建议：

1. 系统级硬约束
2. 冲突与证据覆盖不足
3. 技术关键风险
4. 基本面 key risks
5. 情绪 key risks
6. 事件剩余风险

---

## 8. 与 `trade_plan` 的边界

`trade_plan` 只能消费系统级字段，不应回读模块内部细节。

当前已有正确边界：

- `build_trade_plan_from_decision(decision: DecisionSynthesis)`

后续仍要保持：

- `trade_plan` 不读 `module_results`
- `trade_plan` 不读 provider payload
- `trade_plan` 不重算 bias

因此，`decision_synthesis` 必须对 `trade_plan` 提供足够但克制的字段：

- `overall_bias`
- `confidence_score`
- `actionability_state`
- `conflict_state`
- `data_completeness_pct`
- `blocking_flags`

---

## 9. 当前实现与目标实现差异

| 主题 | 当前实现 | 目标实现 |
|---|---|---|
| 输出 schema | 已稳定 | 保持稳定 |
| blocking flags | 自由字符串、仅一条 | 受控系统级枚举 |
| risks | 轻量摘要 | 带优先级的系统级摘要 |
| module contributions | 兼具输出和部分适配角色 | 只做最终输出解释 |

---

## 10. 测试重点

- `DecisionSynthesis` schema 仍可校验
- 四条 `module_contributions` 固定顺序
- `applied_weights` 对 unavailable 模块为 `null`
- `blocking_flags` 迁移时兼容 `trade_plan`
- `risks` 去重与截断稳定
