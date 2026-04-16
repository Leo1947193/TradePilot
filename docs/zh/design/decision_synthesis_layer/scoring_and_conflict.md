# 决策综合层评分与冲突处理设计

## 1. 文档目标与边界

本文档只定义决策综合层的以下内容：

- 系统级配置权重与可用性权重口径
- `bias_score` 的归一化计算
- `aligned / mixed / conflicted` 的判定规则
- `overall_bias_preliminary` 与最终 `overall_bias` 的生成顺序
- 系统级硬约束如何作用于方向与可执行性
- `data_completeness_pct` 与 `confidence_score` 的固定公式

本文档明确不覆盖：

- 各上游模块输入字段的逐项契约
- 风险列表的去重与输出 Schema 细节
- 下游交易计划生成器接口

说明：

- 本文档是 [overview.md](/Users/leo/Dev/TradePilot/docs/zh/design/decision_synthesis_layer/overview.md) 的评分子文档
- 若与 `overview.md` 存在冲突，应以 `overview.md` 当前已确认的系统约束为准

---

## 2. 固定配置权重与可用性口径

### 2.1 系统级配置权重

决策综合层固定使用以下系统级配置权重：

- `technical`：`0.50`
- `sentiment`：`0.20`
- `event`：`0.20`
- `fundamental`：`0.10`

说明：

- 当前系统基线默认启用四个核心模块
- 若某模块在兼容部署中被显式关闭，则不进入 `enabled_weight_sum`

### 2.2 `enabled_weight_sum`

`enabled_weight_sum` 表示部署层已启用模块的配置权重总和：

```text
enabled_weight_sum =
  sum(configured_weight for module in enabled_modules)
```

约束：

- `not_enabled` 模块不进入 `enabled_weight_sum`
- `excluded` 模块虽然不可用于打分，但如果部署层已启用，仍进入 `enabled_weight_sum`

### 2.3 `available_weight_sum`

`available_weight_sum` 表示当前真正可用于系统级打分的模块配置权重总和：

```text
available_weight_sum =
  sum(configured_weight for module in usable_or_degraded_modules)
```

约束：

- 只有 `usable` 或 `degraded` 模块进入 `available_weight_sum`
- `excluded` 与 `not_enabled` 模块都不进入 `available_weight_sum`

### 2.4 `available_weight_ratio`

```text
available_weight_ratio =
  available_weight_sum / enabled_weight_sum
```

用途：

- 衡量“已启用模块里，当前有多少证据仍然可用”
- 它是系统是否允许输出非中性方向的前置门槛

边界处理：

- 若 `enabled_weight_sum = 0`，则 `available_weight_ratio` 记为 `0`
- 若 `available_weight_sum = 0`，系统不得输出非中性方向

---

## 3. `bias_score` 计算与归一化

### 3.1 归一化原则

系统级方向分数只使用当前可用模块计算。为避免某个已启用模块缺失时整体分值被机械拉低，综合层必须对可用模块重新归一化：

```text
applied_weight(module) =
  configured_weight(module) / available_weight_sum
```

说明：

- 这是**在可用模块集合内部**做归一化
- 归一化后，所有可用模块的 `applied_weight` 之和固定为 `1.0`
- 只要有启用模块未进入可用集合，就属于 `renormalized = true`

### 3.2 方向值与分数公式

每个模块先提供系统级方向值：

- `bullish = 1`
- `neutral = 0`
- `bearish = -1`
- `disqualified = -1`

其中：

- `disqualified` 只允许由基本面模块输出
- 它在数值上按 `-1` 参与打分，但语义上额外触发硬约束

系统级方向分数固定为：

```text
bias_score =
  sum(direction_value(module) × applied_weight(module))
```

### 3.3 边界值与无可用模块处理

约束如下：

- `bias_score` 理论范围固定为 `[-1.0, 1.0]`
- 若 `available_weight_sum = 0`，则 `bias_score = 0`
- `neutral` 模块的贡献始终为 `0`

```text
contribution(module) =
  direction_value(module) × applied_weight(module)
```

输出建议：

- `bias_score` 保留 `2` 位小数

### 3.4 `overall_bias_preliminary` 阈值

在任何方向压制前，必须先生成未加约束结果：

| 条件 | `overall_bias_preliminary` |
|---|---|
| `bias_score > 0.30` | `bullish` |
| `bias_score < -0.30` | `bearish` |
| 其他情况 | `neutral` |

边界值处理：

- `bias_score = 0.30` 时，必须判为 `neutral`
- `bias_score = -0.30` 时，必须判为 `neutral`

---

## 4. 冲突状态定义与判定

### 4.1 方向权重口径

冲突判定只统计具有方向性的可用模块，`neutral` 不参与多空强弱比较。

```text
bullish_weight =
  sum(applied_weight for direction = bullish)

bearish_weight =
  sum(applied_weight for direction = bearish or disqualified)
```

### 4.2 三种冲突状态

- `aligned`：所有方向性模块同向，或仅存在单侧方向
- `mixed`：同时存在 `bullish` 与 `bearish`，但强侧与弱侧的已应用权重差值 `>= 0.30`
- `conflicted`：同时存在 `bullish` 与 `bearish`，且强侧与弱侧的已应用权重差值 `< 0.30`

其中：

```text
direction_gap = abs(bullish_weight - bearish_weight)
```

### 4.3 判定顺序

推荐按以下固定顺序实现：

```text
if bullish_weight = 0 and bearish_weight = 0:
    conflict_state = "aligned"
elif bullish_weight = 0 or bearish_weight = 0:
    conflict_state = "aligned"
elif direction_gap >= 0.30:
    conflict_state = "mixed"
else:
    conflict_state = "conflicted"
```

解释：

- `aligned` 不要求所有模块都是 `bullish`
- 只要另一侧不存在方向性证据，单侧方向即可视为未冲突
- `mixed` 代表有反向证据，但主导方向仍然明显
- `conflicted` 代表多空证据已经接近势均力敌

---

## 5. 最终方向生成顺序

### 5.1 固定执行顺序

评分与方向判定必须按以下顺序执行：

1. 确认各模块 `enabled`、`status`、`direction_value`
2. 计算 `enabled_weight_sum`
3. 计算 `available_weight_sum`
4. 计算 `available_weight_ratio`
5. 对可用模块计算 `applied_weight`
6. 计算 `bias_score`
7. 计算 `conflict_state`
8. 计算 `data_completeness_pct`
9. 生成 `overall_bias_preliminary`
10. 应用方向压制与系统级硬约束
11. 生成最终 `overall_bias`
12. 计算 `confidence_score`

说明：

- `data_completeness_pct` 必须在最终方向压制前完成计算
- 这样可以避免把“完整度不足”错误地当成事后注释，而不是正式压制条件

### 5.2 最终 `overall_bias` 判定

初始值：

```text
overall_bias = overall_bias_preliminary
```

之后按固定顺序应用压制：

1. 若 `available_weight_ratio < 0.70`，则 `overall_bias = neutral`
2. 若 `conflict_state = conflicted`，则 `overall_bias = neutral`
3. 若 `data_completeness_pct < 60`，则 `overall_bias = neutral`
4. 若命中 `fundamental_long_disqualified` 且 `overall_bias_preliminary = bullish`，则 `overall_bias = neutral`

若以上条件均未触发，则：

```text
overall_bias = overall_bias_preliminary
```

### 5.3 压制规则的含义

- `available_weight_ratio < 0.70`：证据覆盖不足，不允许输出单边方向
- `conflicted`：多空主证据过于接近，不允许输出伪确定性方向
- `data_completeness_pct < 60`：整体输入质量不足，不允许输出单边方向
- `fundamental_long_disqualified`：禁止最终净看多，但不自动等价于做空

---

## 6. 硬约束如何作用于综合层

### 6.1 基本面 `Disqualified`

当基本面模块输出 `Disqualified` 时：

- 必须写入 `blocking_flags = ["fundamental_long_disqualified"]`
- 其 `direction_value = -1`
- 它参与 `bias_score` 与冲突判定
- 它禁止最终结果输出净看多

精确规则：

```text
if "fundamental_long_disqualified" in blocking_flags
   and overall_bias_preliminary = "bullish":
    overall_bias = "neutral"
```

说明：

- 若 `overall_bias_preliminary` 已为 `neutral` 或 `bearish`，则不额外改写方向
- 该规则是“取消净看多资格”，不是“强制转为空头”

### 6.2 技术 `setup_state = avoid`

当技术模块返回 `setup_state = avoid` 时：

- 不直接改写 `overall_bias`
- 但 `actionability_state` 必须为 `avoid`
- `confidence_score` 中的 `execution_component` 必须按 `0.40` 计入

说明：

- 技术 `avoid` 回答的是“当前是否具备执行条件”
- 它不应被错误解释为“系统方向必须转空”

### 6.3 事件近端风险

当事件模块命中以下任一近端风险标记时：

- `binary_event_imminent`
- `earnings_within_3d`
- `regulatory_decision_imminent`
- `macro_event_high_sensitivity`

综合层必须执行：

- `actionability_state = avoid`

同时保持以下约束：

- 不直接改写 `overall_bias`
- 不直接改写 `bias_score`
- 仅当事件模块自身方向已是 `bearish` 时，事件模块才会通过方向值影响 `bias_score`

解释：

- 事件近端风险是“当前不适合新开仓”的执行否决
- 它不是方向改写器

---

## 7. `data_completeness_pct` 与 `confidence_score`

### 7.1 系统级 `data_completeness_pct`

若模块已提供 `data_completeness_pct`，综合层直接使用其值。

若模块未提供，则按保守代理规则折算：

- `usable`：`100`
- `degraded`：`70`
- `excluded`：`0`
- `not_enabled`：不进入分母

固定公式：

```text
data_completeness_pct =
  100 × (
    sum(module_completeness_score × configured_weight for enabled modules)
    / enabled_weight_sum
  )
```

其中：

```text
module_completeness_score = module.data_completeness_pct / 100
```

用途：

- `data_completeness_pct < 60` 时，最终方向必须压制为 `neutral`

### 7.2 `confidence_score` 的四个分量

```text
coverage_component = available_weight_ratio
completeness_component = data_completeness_pct / 100

agreement_component =
  1.00, if conflict_state = aligned
  0.70, if conflict_state = mixed
  0.40, if conflict_state = conflicted

execution_component =
  1.00, if technical.setup_state = actionable
  0.70, if technical.setup_state = watch
  0.40, if technical.setup_state = avoid
```

分量含义：

- `coverage_component`：已启用模块里，当前有多少权重仍然可用
- `completeness_component`：当前输入信息是否足够完整
- `agreement_component`：模块之间是否形成单边共识
- `execution_component`：技术执行条件是否支持把结论下放给后续执行层

### 7.3 固定公式

```text
confidence_score_prelim =
  0.35 × coverage_component +
  0.30 × completeness_component +
  0.20 × agreement_component +
  0.15 × execution_component
```

最终：

```text
confidence_score = round(confidence_score_prelim, 2)
```

约束：

- `confidence_score` 范围固定为 `[0.00, 1.00]`
- 仅当 `confidence_score >= 0.65` 时，系统才允许进入可执行状态
- `confidence_score` 本身不改写 `overall_bias`

### 7.4 阈值用途

- `available_weight_ratio < 0.70`：方向压制阈值
- `data_completeness_pct < 60`：方向压制阈值
- `confidence_score >= 0.65`：进入 `actionable` 的最低阈值

说明：

- `confidence_score` 主要回答“当前综合结论是否足够稳健并具备执行条件”
- `overall_bias` 主要回答“当前系统净方向是什么”
- 两者必须分开，不能互相替代

---

## 8. 伪代码

```text
configured_weights = {
  technical: 0.50,
  sentiment: 0.20,
  event: 0.20,
  fundamental: 0.10
}

enabled_weight_sum =
  sum(configured_weight for enabled modules)

available_weight_sum =
  sum(configured_weight for modules with status in ["usable", "degraded"])

if enabled_weight_sum == 0:
    available_weight_ratio = 0
else:
    available_weight_ratio = available_weight_sum / enabled_weight_sum

if available_weight_sum == 0:
    bias_score = 0
    applied_weight[module] = null
else:
    applied_weight[module] =
      configured_weight[module] / available_weight_sum
    bias_score =
      sum(direction_value[module] * applied_weight[module] for available modules)

bullish_weight =
  sum(applied_weight for available modules if direction = bullish)

bearish_weight =
  sum(applied_weight for available modules if direction in [bearish, disqualified])

direction_gap = abs(bullish_weight - bearish_weight)

if bullish_weight == 0 or bearish_weight == 0:
    conflict_state = "aligned"
else if direction_gap >= 0.30:
    conflict_state = "mixed"
else:
    conflict_state = "conflicted"

if bias_score > 0.30:
    overall_bias_preliminary = "bullish"
else if bias_score < -0.30:
    overall_bias_preliminary = "bearish"
else:
    overall_bias_preliminary = "neutral"

data_completeness_pct = calc_system_completeness(...)
overall_bias = overall_bias_preliminary

if available_weight_ratio < 0.70:
    overall_bias = "neutral"
if conflict_state == "conflicted":
    overall_bias = "neutral"
if data_completeness_pct < 60:
    overall_bias = "neutral"
if "fundamental_long_disqualified" in blocking_flags
   and overall_bias_preliminary == "bullish":
    overall_bias = "neutral"

coverage_component = available_weight_ratio
completeness_component = data_completeness_pct / 100
agreement_component = map_conflict_to_agreement(conflict_state)
execution_component = map_setup_state_to_execution(technical.setup_state)

confidence_score =
  round(
    0.35 * coverage_component +
    0.30 * completeness_component +
    0.20 * agreement_component +
    0.15 * execution_component,
    2
  )
```

---

## 9. 数值示例

### 9.1 示例 A：方向一致，最终看多

假设：

- `technical = bullish`，`setup_state = actionable`
- `sentiment = bullish`
- `event = neutral`
- `fundamental = neutral`
- 四个模块都为 `usable`
- 四个模块 `data_completeness_pct = 100`

则：

```text
enabled_weight_sum = 1.00
available_weight_sum = 1.00
available_weight_ratio = 1.00 / 1.00 = 1.00

applied_weights:
technical   = 0.50
sentiment   = 0.20
event       = 0.20
fundamental = 0.10

bias_score =
  1 × 0.50 +
  1 × 0.20 +
  0 × 0.20 +
  0 × 0.10
  = 0.70
```

判定：

- `overall_bias_preliminary = bullish`
- `bullish_weight = 0.70`
- `bearish_weight = 0`
- `conflict_state = aligned`
- `data_completeness_pct = 100`

置信度：

```text
coverage_component = 1.00
completeness_component = 1.00
agreement_component = 1.00
execution_component = 1.00

confidence_score =
  0.35 × 1.00 +
  0.30 × 1.00 +
  0.20 × 1.00 +
  0.15 × 1.00
  = 1.00
```

结果：

- `overall_bias = bullish`
- `confidence_score = 1.00`

### 9.2 示例 B：强冲突，最终压制为中性

假设：

- 四个模块都已启用且 `usable`
- `technical = bullish`
- `sentiment = bearish`
- `event = bearish`
- `fundamental = bullish`
- `technical.setup_state = actionable`
- 四个模块 `data_completeness_pct = 100`

则：

```text
enabled_weight_sum = 1.00
available_weight_sum = 1.00
available_weight_ratio = 1.00

applied_weights:
technical   = 0.50
sentiment   = 0.20
event       = 0.20
fundamental = 0.10

bias_score =
  1 × 0.50 +
  (-1) × 0.20 +
  (-1) × 0.20 +
  1 × 0.10
  = 0.20

bullish_weight = 0.60
bearish_weight = 0.40
direction_gap = 0.20
```

判定：

- `overall_bias_preliminary = neutral`
- `conflict_state = conflicted`

结果：

- 即使覆盖和完整度都足够，系统仍应显式标记 `conflicted`
- `overall_bias = neutral`

说明：

- 这个例子展示的是“多空证据势均力敌”
- 即使未来把 `bias_score` 阈值调得更敏感，`conflicted` 仍然应当单独保留并压制方向

### 9.3 示例 C：基本面 `Disqualified`，禁止净看多

假设：

- `technical = bullish`
- `sentiment = bullish`
- `event = neutral`
- `fundamental = disqualified`
- `technical.setup_state = actionable`
- 四个模块都为 `usable`
- 四个模块 `data_completeness_pct = 100`

则：

```text
enabled_weight_sum = 1.00
available_weight_sum = 1.00
available_weight_ratio = 1.00

applied_weights:
technical   = 0.50
sentiment   = 0.20
event       = 0.20
fundamental = 0.10

bias_score =
  1 × 0.50 +
  1 × 0.20 +
  0 × 0.20 +
  (-1) × 0.10
  = 0.60
```

判定：

- `overall_bias_preliminary = bullish`
- `conflict_state = mixed`
- `blocking_flags` 必须包含 `fundamental_long_disqualified`

结果：

- 因命中基本面硬约束，`overall_bias` 必须压制为 `neutral`
- 该规则只取消净看多资格，不把结果强制改写为 `bearish`

### 9.4 示例 D：事件近端风险不改方向，只否决执行

假设：

- 四个模块都已启用
- `technical = bullish`，`setup_state = actionable`
- `sentiment = bullish`
- `event = bullish`
- `fundamental = neutral`
- 事件模块同时返回 `earnings_within_3d`
- 四个模块都为 `usable`
- 四个模块 `data_completeness_pct = 100`

则：

```text
bias_score =
  1 × 0.50 +
  1 × 0.20 +
  1 × 0.20 +
  0 × 0.10
  = 0.90
```

结果：

- `overall_bias_preliminary = bullish`
- `overall_bias = bullish`
- 但由于命中事件近端风险，`actionability_state` 必须为 `avoid`

这个例子说明：

- 事件近端风险是执行否决，不是方向翻转器
