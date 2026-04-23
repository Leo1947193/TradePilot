# 交易计划输入锚点解析实现契约

## 1. 文档目标

本文档定义交易计划生成器如何解析输入锚点，以及这些锚点允许影响什么、不允许影响什么。

它解决两个实现问题：

- 技术和事件上下文如何以只读方式进入 trade plan
- 多个价格锚点并存时，优先级如何固定

---

## 2. 当前实现事实

当前仓库没有独立锚点解析层。

当前 `trade_plan` 只消费：

- `DecisionSynthesis`

因此目前根本不存在：

- `entry_trigger`
- `key_support`
- `key_resistance`
- `target_price`
- `stop_loss_price`
- `risk_reward_ratio`
- `upcoming_catalysts`
- `risk_events`

这些字段的解析逻辑都还没接到 runtime。

---

## 3. 目标输入面

建议后续引入两个只读上下文：

### 3.1 `technical_context`

允许字段：

- `key_support`
- `key_resistance`
- `entry_trigger`
- `target_price`
- `stop_loss_price`
- `risk_reward_ratio`
- `atr_14`
- `volume_pattern`
- `trend`

### 3.2 `event_context`

允许字段：

- `upcoming_catalysts`
- `risk_events`
- `event_summary`

约束：

- 这两个 context 只能补参数和文案，不允许改写：
  - `overall_bias`
  - `actionability_state`
  - `conflict_state`
  - `blocking_flags`

---

## 4. 优先级规则

### 4.1 多头入场锚点

固定优先级：

1. `technical_context.entry_trigger`
2. 最近支撑位附近企稳
3. 最近阻力位突破确认
4. 无锚点时进入等待模板

### 4.2 空头入场锚点

固定优先级：

1. `technical_context.entry_trigger`
2. 最近阻力位受阻转弱
3. 最近支撑位破位确认
4. 无锚点时进入等待模板

### 4.3 止损锚点

固定优先级：

1. `technical_context.stop_loss_price`
2. 反向关键价位 ± `1 x ATR`
3. 无锚点则输出“未入场前不设止损”模板

### 4.4 止盈锚点

固定优先级：

1. `technical_context.target_price`
2. 下一关键阻力/支撑
3. 至少 `2R` 的 RR 推导
4. 无锚点则输出跟踪模板

---

## 5. 解析顺序

后续实现必须固定：

1. 先读取 `DecisionSynthesis`
2. 确认是否允许进入“可带锚点计划”
3. 再读取 `technical_context`
4. 最后读取 `event_context`

原因：

- 系统级约束必须先决定场景是否允许积极计划
- 不能先生成锚点计划，再被 `avoid` 全盘压掉

---

## 6. 当前阶段与目标阶段

### 6.1 当前阶段

当前代码没有 planning context，因此：

- 只能输出模板化场景
- 不应在文档里暗示“当前已经支持价格锚点”

### 6.2 目标阶段

当 `03_analysis/technical` 和 `03_analysis/event` 的 richer 输出接通后：

- `trade_plan` 才开始消费这些锚点
- 仍然不允许它重算方向

---

## 7. 测试重点

- 多头/空头锚点优先级
- 缺少 ATR 时的回退
- 没有 context 时仍能生成保守模板
- `actionability_state = avoid` 时不应进入积极锚点分支
