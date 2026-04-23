# 交易计划模块实现架构

## 1. 文档目标

本文档定义 `05_trade_plan` 的实现边界、代码拆分和迁移顺序。

当前实现入口：

- [`app/analysis/trade_plan.py`](/Users/leo/Dev/TradePilot/app/analysis/trade_plan.py:1)
- [`app/graph/nodes/generate_trade_plan.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/generate_trade_plan.py:1)
- [`tests/graph/nodes/test_generate_trade_plan.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_generate_trade_plan.py:1)

---

## 2. 当前实现事实

当前 `trade_plan` 仍是轻量模板版：

- 唯一输入：`DecisionSynthesis`
- 始终输出 `bullish_scenario` 和 `bearish_scenario`
- `do_not_trade_conditions` 只来自：
  - `confidence_score < 0.55`
  - `actionability_state = avoid`
  - `blocking_flags`
  - `conflict_state = conflicted`
  - `data_completeness_pct < 60`
- 场景文案完全是固定模板，没有消费技术锚点和事件上下文

当前还没有：

- 输入锚点解析层
- 技术锚点和事件上下文的显式只读输入面
- 带价格锚点的 entry/stop/target 生成
- risk-reward 约束
- “watch/avoid” 模式下的细化退化逻辑

---

## 3. 推荐代码组织

推荐演进为：

```text
app/analysis/trade_plan/
  __init__.py
  schemas.py
  module.py
  anchors.py
  scenarios.py
  constraints.py
```

职责：

- `schemas.py`
  - 内部输入上下文与中间结果 schema
- `module.py`
  - 交易计划总入口
- `anchors.py`
  - 解析技术锚点、事件说明上下文
- `scenarios.py`
  - 生成 bullish / bearish 两个场景
- `constraints.py`
  - `do_not_trade_conditions`、降级、回避逻辑

在迁移过程中，当前 [`build_trade_plan_from_decision(...)`](/Users/leo/Dev/TradePilot/app/analysis/trade_plan.py:11) 可以保留为兼容入口，但内部应逐步下沉到以上四层。

---

## 4. 输入边界

### 4.1 当前稳定输入

当前 runtime 只稳定提供：

- `DecisionSynthesis`

这意味着当前实现必须继续满足：

- 不回读 `module_results`
- 不回读 provider payload
- 不重算方向

### 4.2 目标输入

目标态在不破坏边界的前提下，可新增只读 planning context：

- `decision_synthesis`
- `technical_planning_context`
- `event_planning_context`

其中：

- `decision_synthesis` 仍是唯一分支输入
- 技术/事件上下文只能补参数，不能改写系统结论

---

## 5. 推荐内部输入结构

建议新增：

```text
TradePlanInput(
  decision,
  technical_context,
  event_context,
)
```

其中：

- `decision`
  - 必填
- `technical_context`
  - 可空
  - 只包含计划参数锚点
- `event_context`
  - 可空
  - 只包含计划说明和事件型回避条件

这样后续可以保持：

- 决策综合层负责方向和系统级约束
- 交易计划层负责场景化表达和价格锚点落地

---

## 6. 输出边界

当前 public `TradePlan` schema 已稳定：

- `overall_bias`
- `bullish_scenario`
- `bearish_scenario`
- `do_not_trade_conditions`

实现约束：

- 不要扩 public `TradePlan` 字段，除非 API 契约明确升级
- richer 内部锚点信息可放内部 schema 或未来 persistence JSON，不要直接塞到 public output

---

## 7. 与前后层的边界

### 7.1 上游 `04_synthesis`

交易计划层只能消费：

- `overall_bias`
- `confidence_score`
- `actionability_state`
- `conflict_state`
- `data_completeness_pct`
- `blocking_flags`
- `risks`

### 7.2 下游 `assemble_response`

`assemble_response` 只负责把已经生成好的 `TradePlan` 放进 response，不应再改写交易计划内容。

---

## 8. 编码顺序

推荐顺序：

1. `schemas.py`
2. `constraints.py`
3. `scenarios.py`
4. `anchors.py`
5. `module.py`

原因：

- 当前系统已经依赖 `DecisionSynthesis` -> `TradePlan` 这条链，先把约束层稳定最重要
- 锚点层可以晚于约束层接入

---

## 9. 测试落点

- `tests/analysis/trade_plan/test_constraints.py`
- `tests/analysis/trade_plan/test_scenarios.py`
- `tests/analysis/trade_plan/test_anchors.py`
- `tests/analysis/trade_plan/test_module.py`
- 现有 [`test_generate_trade_plan.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_generate_trade_plan.py:1) 保留 node 契约测试
