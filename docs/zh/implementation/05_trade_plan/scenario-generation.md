# 交易场景生成实现契约

## 1. 文档目标

本文档定义如何从系统级结论生成：

- `bullish_scenario`
- `bearish_scenario`

并明确主场景、备选场景和保守模板之间的切换规则。

---

## 2. 当前实现事实

当前场景生成规则非常简单：

- 若 `overall_bias = bullish` 且 `actionability_state = actionable`
  - bullish 场景输出固定积极模板
- 若 `overall_bias = bearish` 且 `actionability_state = actionable`
  - bearish 场景输出固定积极模板
- 其他情况
  - 两个方向都输出 `wait for clearer ... confirmation`

当前没有：

- `neutral` 时的双向保守细化
- `watch` 与 `avoid` 的差异化模板
- 基于技术锚点的场景参数填充

---

## 3. 主次场景规则

固定规则：

- `overall_bias = bullish` -> `bullish_scenario` 为主场景
- `overall_bias = bearish` -> `bearish_scenario` 为主场景
- `overall_bias = neutral` -> 无主场景，两个场景同等保守

实现约束：

- 始终输出两个方向
- 不允许因为 `overall_bias` 单边化而省略另一边

---

## 4. 模板层级

建议场景模板分为 3 层：

### 4.1 积极模板

条件：

- `actionability_state = actionable`
- 场景方向与 `overall_bias` 一致
- 没有系统级硬阻断

### 4.2 观察模板

条件：

- `actionability_state = watch`
- 或 `overall_bias = neutral`
- 或该场景是备选场景

### 4.3 回避模板

条件：

- `actionability_state = avoid`
- 或有系统级硬阻断

实现要求：

- `watch` 与 `avoid` 不应共用完全相同的文案
- `watch` 是“等待确认”
- `avoid` 是“当前不建立该方向新仓”

---

## 5. 当前阶段与目标阶段

### 5.1 当前阶段

在没有锚点 context 的情况下：

- 仍继续使用模板化场景
- 但建议把模板函数拆成：
  - `build_actionable_bullish_scenario(...)`
  - `build_actionable_bearish_scenario(...)`
  - `build_watch_scenario(...)`
  - `build_avoid_scenario(...)`

### 5.2 目标阶段

引入 `technical_context` 后：

- entry / stop / target 文案优先从锚点生成
- 模板只负责骨架，不负责捏造价格

---

## 6. 生成顺序

建议实现顺序：

1. 先判模板层级
2. 再选主场景和备选场景
3. 再填 entry/take_profit/stop_loss
4. 最后做文本收敛和兜底

---

## 7. 测试重点

- bullish actionable 主场景
- bearish actionable 主场景
- neutral 双向保守场景
- `watch` 与 `avoid` 模板分支
- 无锚点时的兜底文本
