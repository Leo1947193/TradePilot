# 决策综合层输出与交易计划生成器契约

## 1. 文档目标与边界

本文档只定义三件事：

- 决策综合层最终输出的固定 Schema
- 系统级 `risks` 的汇总与截断规则
- 面向交易计划生成器的消费接口、字段白名单与强约束

本文档明确**不展开**：

- 上游输入逐项适配
- 模块内部原始字段语义
- 系统级评分公式推导过程

公式、标准化过程与综合顺序以 [overview.md](/Users/leo/Dev/TradePilot/docs/zh/design/decision_synthesis_layer/overview.md) 为准；本文档负责把最终对外输出收敛为可直接实现、可直接联调的契约。

---

## 2. 最终输出 Schema

API 对齐说明：

- 本文中的 `decision_synthesis` 与 `trade_plan` 是对外 HTTP API 的核心组装来源
- 公共响应字段与 API 映射见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

### 2.1 顶层结构

决策综合层必须输出如下对象：

说明：为控制篇幅，下方 `module_contributions` 只展示单个元素结构；最终实现仍必须按本文第 4 节固定输出 `4` 项。

```json
{
  "overall_bias": "bullish | neutral | bearish",
  "bias_score": 0.0,
  "confidence_score": 0.0,
  "actionability_state": "actionable | watch | avoid",
  "conflict_state": "aligned | mixed | conflicted",
  "data_completeness_pct": 0.0,
  "weight_scheme_used": {
    "configured_weights": {
      "technical": 0.5,
      "fundamental": 0.1,
      "sentiment": 0.2,
      "event": 0.2
    },
    "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
    "disabled_modules": [],
    "enabled_weight_sum": 1.0,
    "available_weight_sum": 1.0,
    "available_weight_ratio": 1.0,
    "applied_weights": {
      "technical": 0.5,
      "fundamental": 0.1,
      "sentiment": 0.2,
      "event": 0.2
    },
    "renormalized": false
  },
  "blocking_flags": [],
  "module_contributions": [
    {
      "module": "technical",
      "enabled": true,
      "status": "usable",
      "direction": "bullish",
      "direction_value": 1,
      "configured_weight": 0.5,
      "applied_weight": 0.625,
      "contribution": 0.625,
      "data_completeness_pct": 100.0,
      "low_confidence": false
    }
  ],
  "risks": []
}
```

### 2.2 字段定义与约束

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `overall_bias` | enum | 是 | 仅允许 `bullish`、`neutral`、`bearish` |
| `bias_score` | number | 是 | 范围 `[-1.00, 1.00]`，保留 `2` 位小数 |
| `confidence_score` | number | 是 | 范围 `[0.00, 1.00]`，保留 `2` 位小数 |
| `actionability_state` | enum | 是 | 仅允许 `actionable`、`watch`、`avoid` |
| `conflict_state` | enum | 是 | 仅允许 `aligned`、`mixed`、`conflicted` |
| `data_completeness_pct` | number | 是 | 范围 `[0.0, 100.0]`，保留 `1` 位小数 |
| `weight_scheme_used` | object | 是 | 必须完整输出，见下节 |
| `blocking_flags` | string[] | 是 | 系统级阻断标记数组，去重后输出 |
| `module_contributions` | object[] | 是 | 固定输出 `4` 项，每个模块恰好一项 |
| `risks` | string[] | 是 | 系统级风险摘要，去重并截断后输出 |

### 2.3 顶层字段空值规则

- 顶层字段均**不允许为 `null`**
- 当无法形成方向时：
  - `overall_bias` 必须为 `neutral`
  - `bias_score` 必须为 `0.00` 或按综合逻辑计算后的值
  - `actionability_state` 仍必须输出有效枚举值
- 当所有已启用模块都不可用时：
  - `overall_bias = neutral`
  - `actionability_state = avoid`
  - `blocking_flags` 必须包含 `all_enabled_modules_excluded`

---

## 3. `weight_scheme_used` 契约

### 3.1 结构定义

```json
{
  "configured_weights": {
    "technical": 0.5,
    "fundamental": 0.1,
    "sentiment": 0.2,
    "event": 0.2
  },
  "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
  "disabled_modules": [],
  "enabled_weight_sum": 1.0,
  "available_weight_sum": 1.0,
  "available_weight_ratio": 1.0,
  "applied_weights": {
    "technical": 0.5,
    "fundamental": 0.1,
    "sentiment": 0.2,
    "event": 0.2
  },
  "renormalized": false
}
```

### 3.2 字段规则

| 字段 | 约束 |
|---|---|
| `configured_weights` | 固定输出四个键：`technical`、`fundamental`、`sentiment`、`event`；值保留 `4` 位小数 |
| `enabled_modules` | 长度 `0..4`，元素唯一，取值仅允许四个模块名 |
| `disabled_modules` | 长度 `0..4`，元素唯一，取值仅允许四个模块名；与 `enabled_modules` 互斥，二者并集必须覆盖四个模块 |
| `enabled_weight_sum` | 范围 `[0.0000, 1.0000]`，保留 `4` 位小数 |
| `available_weight_sum` | 范围 `[0.0000, 1.0000]`，保留 `4` 位小数，且不大于 `enabled_weight_sum` |
| `available_weight_ratio` | 范围 `[0.0000, 1.0000]`，保留 `4` 位小数 |
| `applied_weights` | 固定输出四个键；参与打分的模块输出 number，未参与打分的模块输出 `null`；number 保留 `4` 位小数 |
| `renormalized` | 当任一已启用模块未参与打分时为 `true`；仅有 `not_enabled` 模块时不因其置为 `true` |

### 3.3 `applied_weights` 的 `null` 规则

- `status = usable` 或 `degraded`：`applied_weight` 必须为 number
- `status = excluded` 或 `not_enabled`：`applied_weight` 必须为 `null`
- `available_weight_sum = 0` 时：四个 `applied_weights` 都必须为 `null`

---

## 4. `module_contributions` 契约

### 4.1 用途

`module_contributions` 只用于：

- 向上游或联调方解释系统级结论是如何形成的
- 做审计、回放、观测和调试
- 支持排查“模块未启用 / 已启用但未参与打分 / 低置信度参与打分”等状态

`module_contributions` **不用于**交易计划生成器做交易方向分支，不允许下游用它回推模块内部原始字段。

### 4.2 固定结构

数组长度固定为 `4`，顺序固定如下：

1. `technical`
2. `fundamental`
3. `sentiment`
4. `event`

每项结构如下：

```json
{
  "module": "technical | fundamental | sentiment | event",
  "enabled": true,
  "status": "usable | degraded | excluded | not_enabled",
  "direction": "bullish | neutral | bearish | disqualified",
  "direction_value": -1,
  "configured_weight": 0.5,
  "applied_weight": 0.625,
  "contribution": 0.625,
  "data_completeness_pct": 100.0,
  "low_confidence": false
}
```

### 4.3 字段约束

| 字段 | 约束 |
|---|---|
| `module` | 仅允许四个固定模块名 |
| `enabled` | `true/false`；表示部署是否启用，不表示是否成功参与打分 |
| `status` | 仅允许 `usable`、`degraded`、`excluded`、`not_enabled` |
| `direction` | 仅允许 `bullish`、`neutral`、`bearish`、`disqualified` |
| `direction_value` | 仅允许 `-1`、`0`、`1`；必须为整数 |
| `configured_weight` | number，保留 `4` 位小数 |
| `applied_weight` | `number | null`，number 保留 `4` 位小数 |
| `contribution` | `number | null`，范围 `[-1.0000, 1.0000]`，保留 `4` 位小数 |
| `data_completeness_pct` | `number | null`，number 范围 `[0.0, 100.0]`，保留 `1` 位小数 |
| `low_confidence` | boolean |

### 4.4 状态与空值规则

#### `usable`

- `enabled = true`
- `applied_weight` 必须为 number
- `contribution` 必须为 number
- `data_completeness_pct` 必须为 number

#### `degraded`

- `enabled = true`
- `applied_weight` 必须为 number
- `contribution` 必须为 number
- `data_completeness_pct` 必须为 number
- `low_confidence` 可为 `true`

#### `excluded`

- `enabled = true`
- `direction` 必须写为 `neutral`
- `direction_value = 0`
- `applied_weight = null`
- `contribution = null`
- `data_completeness_pct` 必须写为 `0.0`

#### `not_enabled`

- `enabled = false`
- `direction` 必须写为 `neutral`
- `direction_value = 0`
- `applied_weight = null`
- `contribution = null`
- `data_completeness_pct = null`
- `low_confidence = false`

### 4.5 计算口径

`module_contributions` 的计算必须遵循以下口径：

- `contribution = direction_value × applied_weight`
- 只对 `usable` / `degraded` 模块计算 `contribution`
- `bias_score` 应先基于未舍入的内部值计算，再在最终输出时保留 `2` 位小数
- `module_contributions[].contribution` 输出时保留 `4` 位小数
- 所有非 `null` 的 `contribution` 求和后，与未舍入 `bias_score` 的差值应只来自舍入误差

---

## 5. `blocking_flags` 契约

### 5.1 当前受控枚举

`blocking_flags` 当前只允许输出以下系统级标记：

- `technical_setup_avoid`
- `fundamental_long_disqualified`
- `binary_event_imminent`
- `earnings_within_3d`
- `regulatory_decision_imminent`
- `macro_event_high_sensitivity`
- `all_enabled_modules_excluded`

补充约束：

- 模块执行失败、超时、字段非法等诊断信息不得直接进入最终输出的顶层 `blocking_flags`
- 这类信息应保留在模块级适配诊断、`module_contributions.status` 或系统级 `risks` 中，避免把系统级阻断和实现诊断混为一谈

### 5.2 数组规则

- 长度上限：`16`
- 元素必须唯一
- 顺序必须稳定：
  1. 基本面否决
  2. 事件近端风险
  3. 技术执行否决
  4. 全部已启用模块不可用
- 若未来新增系统级阻断标记，必须先更新本文档再扩展枚举

---

## 6. 系统级 `risks` 汇总规则

### 6.1 输出目标

系统级 `risks` 的目标不是枚举全部风险，而是保留**最值得交易计划生成器和人工审阅者优先处理的风险摘要**。

### 6.2 数组约束

- 类型：`string[]`
- 长度上限：`6`
- 每条风险文本必须为已经标准化后的中文摘要
- 元素必须唯一
- 建议单条文本不超过 `60` 个汉字，避免下游展示截断

### 6.3 提取优先级

风险提取必须按以下优先级执行，优先级数值越大越先保留：

| 优先级 | 来源 | 触发条件 | 标准化输出 |
|---|---|---|---|
| `100` | aggregator | `fundamental_long_disqualified` | `基本面存在近端硬风险，禁止输出净看多结论` |
| `95` | aggregator | 命中任一事件近端风险标记 | `近端二元事件风险过高，当前不适合新开仓` |
| `92` | aggregator | `all_enabled_modules_excluded` | `已启用模块均不可用，当前综合结论不具备可执行性` |
| `90` | aggregator | `conflict_state = conflicted` | `跨模块信号显著冲突，当前缺乏单边共识` |
| `85` | aggregator | `available_weight_ratio < 0.70` | `关键模块证据不足，当前综合结论稳定性受限` |
| `80` | technical | 技术模块核心风险 | 直通标准化后的技术风险 |
| `70` | fundamental | `key_risks[]` | 直通标准化后的基本面风险 |
| `60` | sentiment | `key_risks[]` | 直通标准化后的情绪风险 |
| `55` | event | 事件模块其他风险 | 直通标准化后的事件风险 |

### 6.4 去重规则

去重顺序固定如下：

1. 先把风险文本标准化：去首尾空格、合并连续空白、英文大小写折叠
2. 对受控系统级标记，优先使用表内标准化输出，不保留原始变体
3. 若多个来源标准化后文本相同，仅保留优先级最高的一条
4. 若优先级也相同，保留先进入排序序列的一条

### 6.5 截断规则

完成去重后，必须按以下顺序截断：

1. 先按优先级降序排序
2. 同优先级按来源顺序排序：`aggregator` > `technical` > `fundamental` > `sentiment` > `event`
3. 只保留前 `6` 条
4. 被截断的风险不得以 `"others"` 或类似占位文本补回

---

## 7. 交易计划生成器消费契约

### 7.1 系统级分支白名单

交易计划生成器在做**方向、执行性和风险否决分支**时，只能消费以下字段：

- `overall_bias`
- `confidence_score`
- `actionability_state`
- `conflict_state`
- `data_completeness_pct`
- `blocking_flags`
- `risks`

说明：

- `bias_score` 可用于日志或解释性文案，但**不得**作为重新分支判断的阈值输入
- `weight_scheme_used` 与 `module_contributions` 仅用于审计、观测和联调，**不得**参与交易计划分支
- 交易计划生成器**不得**通过 `module_contributions` 反推模块级规则

### 7.2 允许的辅助 `planning_context`

若交易计划生成器需要填充入场、止损、止盈锚点或事件说明，主调度器可以额外注入只读 `planning_context`。该上下文**不属于决策综合层输出**，且只能用于参数填充与解释文案，不得参与方向、执行性或风险否决分支。

当前允许的 `planning_context` 字段如下：

- `technical.key_support`
- `technical.key_resistance`
- `technical.entry_trigger`
- `technical.target_price`
- `technical.stop_loss_price`
- `technical.risk_reward_ratio`
- `technical.atr_14`
- `technical.volume_pattern`
- `event.upcoming_catalysts`
- `event.risk_events`
- `event.event_summary`

强约束：

- `planning_context` 不得覆盖 `overall_bias`
- `planning_context` 不得覆盖 `actionability_state`
- `planning_context` 不得覆盖 `blocking_flags`
- 即使存在技术锚点，只要 `actionability_state = avoid`，也不得输出执行参数

### 7.3 消费优先级

交易计划生成器必须按以下优先级消费系统级输出：

1. `actionability_state`
2. `blocking_flags`
3. `overall_bias`
4. `conflict_state`
5. `confidence_score`
6. `data_completeness_pct`
7. `risks`

这意味着：

- `actionability_state` 可以直接否决方向性计划
- `blocking_flags` 可以进一步约束允许输出的计划类型
- `overall_bias` 只在未被前两者否决时，决定主方向
- `confidence_score` 只能调节措辞强弱、观察优先级或计划保守度，不能覆盖前述结论

### 7.4 强约束矩阵

| `actionability_state` | `overall_bias` | 约束 |
|---|---|---|
| `avoid` | 任意 | 只允许输出“不交易 / 等待条件 / 风险说明”；不得输出入场、加仓、止盈止损等执行参数 |
| `watch` | `bullish` | 只允许输出看涨观察方案和触发条件；不得写成已可执行计划 |
| `watch` | `bearish` | 只允许输出看跌或防御性观察方案；不得写成已可执行计划 |
| `watch` | `neutral` | 必须同时给出看涨与看跌两组观察条件；不得暗示单边主方案 |
| `actionable` | `bullish` | 只允许输出净看多主方案；不得输出净看空主方案 |
| `actionable` | `bearish` | 只允许输出净看空或防御性主方案；不得输出净看多主方案 |
| `actionable` | `neutral` | 视为非法组合；交易计划生成器必须拒绝产出执行计划并记录契约错误 |

补充说明：

- 若需要展示价格位或事件说明，只能在满足上述矩阵的前提下，从 `planning_context` 中取值
- `planning_context` 只负责回答“如果允许生成计划，具体锚点是什么”，不负责回答“当前是否允许交易”

### 7.5 `blocking_flags` 的强约束

#### `fundamental_long_disqualified`

- 不得生成净看多主方案
- 若同时 `overall_bias = bearish`，只允许输出净看空或防御性方案
- 若 `overall_bias != bearish`，必须降级为不交易或观察，不得把中性结论包装成看多计划

#### 任一事件近端风险标记

适用标记：

- `binary_event_imminent`
- `earnings_within_3d`
- `regulatory_decision_imminent`
- `macro_event_high_sensitivity`

约束如下：

- 不得生成“当前立即开新仓”的计划
- 只允许输出等待事件落地后的观察条件或风险说明
- 即使 `overall_bias` 明确、`confidence_score` 较高，也不得绕过该约束

#### `technical_setup_avoid`

- 不得生成立即执行的交易计划
- 可以保留方向性观察结论，但必须明确“当前技术执行条件不成立”

#### `all_enabled_modules_excluded`

- 必须直接输出不交易
- 不得尝试用历史缓存、默认方向或经验规则补足计划

---

## 8. 联调要求

为避免上下游实现偏差，联调时必须检查以下不变量：

- `module_contributions` 长度固定为 `4`，且模块顺序固定
- `enabled_modules` 与 `disabled_modules` 并集恰好覆盖四个模块且无重复
- `status in ["excluded", "not_enabled"]` 的模块，其 `applied_weight` 与 `contribution` 必须为 `null`
- `overall_bias = neutral` 时，交易计划生成器不得生成单边可执行计划
- `actionability_state = avoid` 时，交易计划生成器不得输出任何执行参数
- `planning_context` 中的技术或事件字段不得改变交易计划分支结果
- `fundamental_long_disqualified` 出现时，交易计划生成器不得产出净看多主方案

---

## 9. JSON 示例

### 9.1 示例一：可执行的看涨场景

```json
{
  "overall_bias": "bullish",
  "bias_score": 0.70,
  "confidence_score": 0.83,
  "actionability_state": "actionable",
  "conflict_state": "aligned",
  "data_completeness_pct": 91.3,
  "weight_scheme_used": {
    "configured_weights": {
      "technical": 0.5000,
      "fundamental": 0.1000,
      "sentiment": 0.2000,
      "event": 0.2000
    },
    "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
    "disabled_modules": [],
    "enabled_weight_sum": 1.0000,
    "available_weight_sum": 1.0000,
    "available_weight_ratio": 1.0000,
    "applied_weights": {
      "technical": 0.5000,
      "fundamental": 0.1000,
      "sentiment": 0.2000,
      "event": 0.2000
    },
    "renormalized": false
  },
  "blocking_flags": [],
  "module_contributions": [
    {
      "module": "technical",
      "enabled": true,
      "status": "usable",
      "direction": "bullish",
      "direction_value": 1,
      "configured_weight": 0.5000,
      "applied_weight": 0.5000,
      "contribution": 0.5000,
      "data_completeness_pct": 100.0,
      "low_confidence": false
    },
    {
      "module": "fundamental",
      "enabled": true,
      "status": "usable",
      "direction": "neutral",
      "direction_value": 0,
      "configured_weight": 0.1000,
      "applied_weight": 0.1000,
      "contribution": 0.0000,
      "data_completeness_pct": 96.0,
      "low_confidence": false
    },
    {
      "module": "sentiment",
      "enabled": true,
      "status": "degraded",
      "direction": "bullish",
      "direction_value": 1,
      "configured_weight": 0.2000,
      "applied_weight": 0.2000,
      "contribution": 0.2000,
      "data_completeness_pct": 75.0,
      "low_confidence": true
    },
    {
      "module": "event",
      "enabled": true,
      "status": "usable",
      "direction": "neutral",
      "direction_value": 0,
      "configured_weight": 0.2000,
      "applied_weight": 0.2000,
      "contribution": 0.0000,
      "data_completeness_pct": 88.0,
      "low_confidence": false
    }
  ],
  "risks": [
    "情绪侧覆盖度偏低，短期叙事延续性仍需继续确认",
    "基本面暂无硬性否决，但盈利兑现节奏仍需继续跟踪"
  ]
}
```

该输出可被交易计划生成器解释为：

- 允许进入看涨主方案分支
- 允许生成执行参数
- 但需要把情绪侧低置信度保留在风险说明中

### 9.2 示例二：`avoid` / 不交易场景

```json
{
  "overall_bias": "neutral",
  "bias_score": 0.40,
  "confidence_score": 0.90,
  "actionability_state": "avoid",
  "conflict_state": "mixed",
  "data_completeness_pct": 89.4,
  "weight_scheme_used": {
    "configured_weights": {
      "technical": 0.5000,
      "fundamental": 0.1000,
      "sentiment": 0.2000,
      "event": 0.2000
    },
    "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
    "disabled_modules": [],
    "enabled_weight_sum": 1.0000,
    "available_weight_sum": 1.0000,
    "available_weight_ratio": 1.0000,
    "applied_weights": {
      "technical": 0.5000,
      "fundamental": 0.1000,
      "sentiment": 0.2000,
      "event": 0.2000
    },
    "renormalized": false
  },
  "blocking_flags": [
    "fundamental_long_disqualified",
    "earnings_within_3d"
  ],
  "module_contributions": [
    {
      "module": "technical",
      "enabled": true,
      "status": "usable",
      "direction": "bullish",
      "direction_value": 1,
      "configured_weight": 0.5000,
      "applied_weight": 0.5000,
      "contribution": 0.5000,
      "data_completeness_pct": 98.0,
      "low_confidence": false
    },
    {
      "module": "fundamental",
      "enabled": true,
      "status": "usable",
      "direction": "disqualified",
      "direction_value": -1,
      "configured_weight": 0.1000,
      "applied_weight": 0.1000,
      "contribution": -0.1000,
      "data_completeness_pct": 94.0,
      "low_confidence": false
    },
    {
      "module": "sentiment",
      "enabled": true,
      "status": "usable",
      "direction": "bullish",
      "direction_value": 1,
      "configured_weight": 0.2000,
      "applied_weight": 0.2000,
      "contribution": 0.2000,
      "data_completeness_pct": 86.0,
      "low_confidence": false
    },
    {
      "module": "event",
      "enabled": true,
      "status": "usable",
      "direction": "bearish",
      "direction_value": -1,
      "configured_weight": 0.2000,
      "applied_weight": 0.2000,
      "contribution": -0.2000,
      "data_completeness_pct": 82.0,
      "low_confidence": false
    }
  ],
  "risks": [
    "基本面存在近端硬风险，禁止输出净看多结论",
    "近端二元事件风险过高，当前不适合新开仓",
    "盈利披露窗口临近，事件后定价跳空风险较高"
  ]
}
```

该输出可被交易计划生成器解释为：

- 不得产出任何立即执行的交易计划
- 不得把较高 `confidence_score` 误解为“可以忽略阻断标记”
- 只能输出不交易结论，或等待财报落地后的再评估条件
