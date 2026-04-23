# 交易计划风险约束与降级实现契约

## 1. 文档目标

本文档定义：

- `do_not_trade_conditions` 如何生成
- `watch/avoid` 如何压制交易计划
- 当前简单实现和目标实现之间的迁移顺序

---

## 2. 当前实现事实

当前 `do_not_trade_conditions` 只来自 5 类条件：

1. `confidence_score < 0.55`
2. `actionability_state = avoid`
3. `blocking_flags`
4. `conflict_state = conflicted`
5. `data_completeness_pct < 60`

当前实现已经做对的部分：

- 条件是确定性的
- 会去重
- 不会重算方向

当前缺口：

- 没有 risk-reward 约束
- 没有事件型说明到具体不交易条件的模板化转写
- `watch` 只体现在场景文案里，没有单独的回避条件语义

---

## 3. 生成顺序

后续实现必须固定：

1. 先加入系统级硬条件
2. 再加入 evidence / completeness 条件
3. 再加入锚点质量条件
4. 最后去重并截断

原因：

- 系统级条件优先级最高
- 风险收益和锚点不足只能在“允许计划生成”之后判断

---

## 4. 当前应保留的硬条件

以下条件和当前代码、tests 已经绑定，短期不要改名：

- `confidence_score_below_0_55`
- `actionability_state_avoid`
- `conflict_state_conflicted`
- `data_completeness_below_60`
- 各 `blocking_flags` 原样透传

这些字符串已经被 [`test_generate_trade_plan.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_generate_trade_plan.py:1) 固化。

---

## 5. 目标新增条件

当 richer context 接入后，建议新增：

- `risk_reward_below_2`
- `no_valid_entry_anchor`
- `near_term_event_risk`
- `technical_setup_watch_only`

实现约束：

- 新增条件前先更新 tests 和 implementation 文档
- 不要把自然语言长句直接作为 condition id

---

## 6. `watch` 与 `avoid`

当前实现只把 `avoid` 写入 `do_not_trade_conditions`，这可以保留。

但目标态应明确区分：

- `watch`
  - 场景保守
  - 不一定进入 `do_not_trade_conditions`
- `avoid`
  - 必须进入 `do_not_trade_conditions`
  - 场景进入回避模板

---

## 7. 降级策略

### 7.1 缺少 `DecisionSynthesis`

保持当前行为：

- 直接 `raise ValueError("decision_synthesis is required to generate trade plan")`

### 7.2 只有系统级输入、没有锚点 context

允许：

- 继续生成保守模板化 `TradePlan`

### 7.3 有锚点 context，但数据不完整

要求：

- 回退到模板，不得拼装半真半假的价格计划

---

## 8. 与 `03_analysis` / `04_synthesis` 的边界

- 风险收益不足只影响交易计划，不回写 `DecisionSynthesis`
- `blocking_flags` 的语义来源于 `04_synthesis`
- 交易计划层不应反向修改综合层 `risks`

---

## 9. 测试重点

- 当前五类硬条件仍然稳定
- 去重顺序稳定
- 缺锚点时回退到模板
- `avoid` 必进 `do_not_trade_conditions`
- future 条件加入后不破坏旧测试
