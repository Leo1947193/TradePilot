# 决策综合层输入适配契约

## 1. 文档目标与边界

本文定义**决策综合层**对上游模块输出的输入适配契约，用于把 `technical`、`fundamental`、`sentiment`、`event` 的聚合结果统一转换为同一内部结构。

本文只负责：

- 规定各模块的最小输入契约
- 定义 `normalized_module_signal` 的字段、枚举和值约束
- 规定模块到 `direction`、`direction_value`、`status`、`blocking_flags` 的映射规则
- 规定缺失字段、模块未启用、模块执行失败、字段非法时的降级与排除逻辑
- 给出标准化适配顺序与示例

本文明确**不负责**：

- 计算跨模块评分公式
- 判定模块冲突强弱
- 生成交易计划、入场位、止损位或仓位建议

说明：

- 决策综合层是全系统唯一允许做跨模块组合的层
- 当前系统基线默认启用四个核心模块；`not_enabled` 仅保留为契约兼容状态，而不是推荐部署形态
- 输入适配的目标是“保真映射”，不是重做上游分析

---

## 2. 输入来源与最小输入契约

### 2.1 输入来源

决策综合层只读取各模块的**最终聚合结果**，不直接读取原始 OHLCV、财报、新闻正文或事件日历。

每个模块都必须先经过输入适配，输出统一的 `normalized_module_signal`，之后才允许进入后续综合逻辑。

### 2.2 通用适配约束

- 上游字段名必须与模块设计文档约定一致
- 若上游返回额外字段，决策综合层可以忽略，但不得据此扩展本契约中的强制语义
- 所有字符串枚举匹配均应大小写敏感；若上游尚未完成大小写统一，必须在适配层先做显式映射
- `configured_weight` 来自系统配置或部署清单，不从模块运行结果推断
- `summary` 只承接上游摘要，不允许在适配层引入新的分析结论

### 2.3 `technical` 最小输入契约

| 字段 | 类型 / 枚举 | 是否必需 | 适配用途 |
|---|---|---|---|
| `technical_signal` | `bullish` \| `neutral` \| `bearish` | 是 | 映射 `direction` 与 `direction_value` |
| `setup_state` | `actionable` \| `watch` \| `avoid` | 是 | 生成 `blocking_flags` 与状态修饰 |
| `risk_flags` | `string[]` | 是 | 写入 `blocking_flags`，并识别执行退化 |
| `technical_summary` | `string \| null` | 否 | 映射 `summary` |

补充约束：

- `technical_signal` 缺失或不在允许枚举内时，`technical` 必须记为 `excluded`
- `risk_flags` 缺失时，视为关键字段缺失，不允许默认成空数组
- `setup_state` 若为未知值，不直接推断为 `watch`；应记为字段非法并 `excluded`

### 2.4 `fundamental` 最小输入契约

| 字段 | 类型 / 枚举 | 是否必需 | 适配用途 |
|---|---|---|---|
| `fundamental_bias` | `Bullish` \| `Neutral` \| `Bearish` \| `Disqualified` | 是 | 映射 `direction` 与 `direction_value` |
| `key_risks` | `string[]` | 是 | 映射 `key_risks` |
| `data_completeness_pct` | `number`，范围 `0-100` | 否 | 映射 `data_completeness_pct` |
| `low_confidence_modules` | `string[]` | 否 | 生成 `low_confidence` |
| `composite_score` | `number` | 否 | 仅做可追溯透传校验，不参与本层适配判定 |

补充约束：

- `fundamental_bias` 为 `Disqualified` 时，必须生成 `fundamental_long_disqualified`
- `key_risks` 缺失时，视为关键字段缺失；因为该字段承担系统级风险透传职责
- `data_completeness_pct` 若存在但不在 `0-100` 范围内，应视为字段非法并按降级规则处理

### 2.5 `sentiment` 最小输入契约

| 字段 | 类型 / 枚举 | 是否必需 | 适配用途 |
|---|---|---|---|
| `sentiment_bias` | `Bullish` \| `Neutral` \| `Bearish` | 是 | 映射 `direction` 与 `direction_value` |
| `key_risks` | `string[]` | 是 | 映射 `key_risks` |
| `data_completeness_pct` | `number`，范围 `0-100` | 否 | 映射 `data_completeness_pct` |
| `low_confidence_modules` | `string[]` | 否 | 生成 `low_confidence` |
| `market_expectation` | 字符串 | 否 | 仅供摘要透传或解释，不进入本结构强制字段 |
| `composite_score` | `number` | 否 | 仅做可追溯透传校验，不参与本层适配判定 |

补充约束：

- `sentiment_bias` 缺失或非法时，`sentiment` 必须记为 `excluded`
- `key_risks` 缺失时，视为关键字段缺失

### 2.6 `event` 最小输入契约

| 字段 | 类型 / 枚举 | 是否必需 | 适配用途 |
|---|---|---|---|
| `event_bias` | `Bullish` \| `Neutral` \| `Bearish` | 是 | 映射 `direction` 与 `direction_value` |
| `event_risk_flags` | `string[]` | 是 | 映射 `blocking_flags` |
| `upcoming_catalysts` | `string[]` | 否 | 仅供摘要或追溯，不进入强制字段 |
| `data_completeness_pct` | `number`，范围 `0-100` | 否 | 映射 `data_completeness_pct` |
| `low_confidence_modules` | `string[]` | 否 | 生成 `low_confidence` |

补充约束：

- `event_bias` 与 `event_risk_flags` 都属于关键字段
- `event` 执行失败、超时、返回空对象或关键字段缺失时，必须记为 `excluded`

---

## 3. 标准化内部结构

### 3.1 规范结构

所有模块进入决策综合逻辑前，必须先转换为以下统一结构：

```text
normalized_module_signal = {
  module: "technical" | "fundamental" | "sentiment" | "event",
  enabled: boolean,
  status: "usable" | "degraded" | "excluded" | "not_enabled",
  direction: "bullish" | "neutral" | "bearish" | "disqualified",
  direction_value: -1 | 0 | 1,
  configured_weight: number,
  data_completeness_pct: number | null,
  low_confidence: boolean,
  blocking_flags: string[],
  diagnostic_flags: string[],
  key_risks: string[],
  summary: string | null
}
```

### 3.2 字段定义与值约束

| 字段 | 类型 | 允许值 / 约束 | 说明 |
|---|---|---|---|
| `module` | `string` | `technical` / `fundamental` / `sentiment` / `event` | 标识来源模块，必须与部署配置一致 |
| `enabled` | `boolean` | `true` / `false` | 表示部署是否启用该模块 |
| `status` | `string` | `usable` / `degraded` / `excluded` / `not_enabled` | 模块可用性状态 |
| `direction` | `string` | `bullish` / `neutral` / `bearish` / `disqualified` | 统一方向标签 |
| `direction_value` | `number` | `-1` / `0` / `1` | 统一方向数值 |
| `configured_weight` | `number` | `> 0` | 由系统配置提供，不允许为负数或空值 |
| `data_completeness_pct` | `number \| null` | `null` 或 `0-100` | 上游完整度；未知时必须为 `null` |
| `low_confidence` | `boolean` | `true` / `false` | 统一低置信度标记 |
| `blocking_flags` | `string[]` | 可空数组，元素不可为空串 | 可进入系统级综合逻辑的受控阻断或约束标记 |
| `diagnostic_flags` | `string[]` | 可空数组，元素不可为空串 | 执行失败、超时、字段非法等适配诊断，不进入最终顶层 `blocking_flags` |
| `key_risks` | `string[]` | 可空数组，元素不可为空串 | 上游风险透传 |
| `summary` | `string \| null` | 允许空值 | 上游摘要透传 |

### 3.3 结构级硬约束

- `status = not_enabled` 时，必须满足 `enabled = false`
- `status` 为 `usable`、`degraded`、`excluded` 时，必须满足 `enabled = true`
- `direction = disqualified` 只允许 `fundamental` 使用
- `direction = disqualified` 时，`direction_value` 必须为 `-1`
- `technical`、`sentiment`、`event` 不允许输出 `direction = disqualified`
- `blocking_flags`、`diagnostic_flags` 与 `key_risks` 为无数据时必须显式写空数组，不允许写 `null`
- `data_completeness_pct` 若无法确定，必须写 `null`，不得写负数、空字符串或 `NaN`

---

## 4. 状态判定顺序与适配流程

### 4.1 状态判定优先级

每个模块的状态判定顺序固定如下，前一条命中后不得再被后一条覆盖：

1. `not_enabled`
2. `excluded`
3. `degraded`
4. `usable`

这样设计的原因：

- 未启用是部署事实，不是运行异常
- 排除是硬失败，优先级高于低置信度
- 低置信度只能修饰“可用但质量不足”的模块，不能掩盖关键字段错误

### 4.2 四种状态的定义

| 状态 | 定义 | 是否进入后续综合 |
|---|---|---|
| `usable` | 关键字段完整、枚举合法、无排除条件，且无明显低置信度触发 | 是 |
| `degraded` | 关键字段完整且方向可判定，但存在完整度偏低、低置信度或非关键字段异常 | 是 |
| `excluded` | 模块已启用但整体缺失、执行失败、关键字段缺失或关键字段非法 | 否 |
| `not_enabled` | 部署配置未启用该模块 | 否 |

### 4.3 统一适配伪代码

```text
adapt_module(module_name, enabled, configured_weight, payload):
    if enabled == false:
        return build_not_enabled_signal(module_name, configured_weight)

    if payload is null or payload.execution_status in ["failed", "timeout"]:
        return build_excluded_signal(module_name, configured_weight, "module_execution_failed")

    validate_required_fields(payload)
    if required_field_missing or required_field_illegal:
        return build_excluded_signal(module_name, configured_weight, "invalid_or_missing_required_field")

    direction = map_direction(module_name, payload)
    direction_value = map_direction_value(direction)

    blocking_flags = extract_blocking_flags(module_name, payload)
    diagnostic_flags = extract_diagnostic_flags(module_name, payload)
    key_risks = extract_key_risks(module_name, payload)
    data_completeness_pct = normalize_completeness(payload.data_completeness_pct)
    low_confidence = derive_low_confidence(module_name, payload, data_completeness_pct)
    summary = extract_summary(module_name, payload)

    if should_degrade(module_name, payload, data_completeness_pct, low_confidence):
        status = "degraded"
    else:
        status = "usable"

    return normalized_module_signal(...)
```

### 4.4 `usable / degraded / excluded / not_enabled` 判定条件

#### `not_enabled`

以下条件成立时，必须输出 `not_enabled`：

- 部署配置中该模块明确未启用
- 某模块在联调或兼容环境中被显式关闭

固定输出约束：

- `enabled = false`
- `status = not_enabled`
- `direction = neutral`
- `direction_value = 0`
- `blocking_flags = []`
- `diagnostic_flags = []`
- `key_risks = []`
- `summary = null`

#### `excluded`

以下任一条件成立时，必须输出 `excluded`：

- 模块已启用，但整体结果对象缺失
- 模块已启用，但执行失败、超时、被上游中断
- 任一关键字段缺失
- 任一关键枚举字段取值非法
- `data_completeness_pct` 存在但为非法数值，且该字段被当前模块实现声明为关键完整度字段
- 方向无法从上游字段唯一映射

固定输出约束：

- `enabled = true`
- `status = excluded`
- `direction = neutral`，除非 `fundamental_bias = Disqualified` 已被合法解析
- `direction_value = 0`，除非合法 `Disqualified`
- 必须把失败原因写入 `diagnostic_flags`

建议的标准诊断标记：

- `module_execution_failed`
- `module_timeout`
- `module_output_missing`
- `missing_required_field`
- `invalid_enum_value`
- `invalid_numeric_value`

#### `degraded`

以下任一条件成立，且未命中 `excluded` 时，必须输出 `degraded`：

- 上游存在低置信度信号，如 `low_confidence_modules` 非空
- `data_completeness_pct` 已知且低于 `60`
- 技术模块 `risk_flags` 包含 `agent_{N}_unavailable`
- 技术模块 `setup_state = avoid`
- 事件模块存在近端重大事件风险标记，但仍成功返回方向
- 非关键字段缺失，导致摘要或风险信息不完整

固定输出约束：

- `enabled = true`
- `status = degraded`
- `direction` 与方向映射结果保持一致，不因降级被自动改写为 `neutral`
- `low_confidence = true`

#### `usable`

以下条件同时成立时，输出 `usable`：

- 模块已启用
- 关键字段完整且合法
- 可唯一确定方向映射
- 未命中任何 `excluded` 或 `degraded` 条件

---

## 5. 各模块映射规则

### 5.1 通用映射规则

统一方向数值映射固定如下：

| `direction` | `direction_value` |
|---|---|
| `bullish` | `1` |
| `neutral` | `0` |
| `bearish` | `-1` |
| `disqualified` | `-1` |

通用补充规则：

- `direction_value` 只表达方向，不表达强弱
- `blocking_flags` 只承载可参与系统级综合逻辑的业务约束
- `diagnostic_flags` 承载执行失败、超时、字段非法等适配诊断
- `low_confidence = true` 不会自动改写方向，只会影响 `status`

### 5.2 `technical` 映射规则

#### 方向映射

| 上游字段 | 标准化结果 |
|---|---|
| `technical_signal = bullish` | `direction = bullish`，`direction_value = 1` |
| `technical_signal = neutral` | `direction = neutral`，`direction_value = 0` |
| `technical_signal = bearish` | `direction = bearish`，`direction_value = -1` |

#### `blocking_flags` 映射

规则顺序如下：

1. 若 `setup_state = avoid`，追加 `technical_setup_avoid`
2. 原始 `risk_flags` 仅用于模块内追溯和 `key_risks` 提取，不直接提升为最终系统级 `blocking_flags`
3. 去重后写入 `blocking_flags`

#### `status` 修饰规则

- `technical_signal` 缺失或非法：`excluded`
- `setup_state` 缺失或非法：`excluded`
- `risk_flags` 缺失或不是数组：`excluded`
- `setup_state = avoid`：至少 `degraded`
- `risk_flags` 含 `agent_{N}_unavailable`：至少 `degraded`

### 5.3 `fundamental` 映射规则

#### 方向映射

| 上游字段 | 标准化结果 |
|---|---|
| `fundamental_bias = Bullish` | `direction = bullish`，`direction_value = 1` |
| `fundamental_bias = Neutral` | `direction = neutral`，`direction_value = 0` |
| `fundamental_bias = Bearish` | `direction = bearish`，`direction_value = -1` |
| `fundamental_bias = Disqualified` | `direction = disqualified`，`direction_value = -1` |

#### `blocking_flags` 映射

规则顺序如下：

1. 初始化为空数组
2. 若 `fundamental_bias = Disqualified`，追加 `fundamental_long_disqualified`
3. 若适配层命中字段错误或执行失败，再追加相应失败标记

#### `status` 修饰规则

- `fundamental_bias` 缺失或非法：`excluded`
- `key_risks` 缺失或不是数组：`excluded`
- `low_confidence_modules` 非空：至少 `degraded`
- `data_completeness_pct` 已知且 `< 60`：至少 `degraded`
- `fundamental_bias = Disqualified` 但字段合法：模块仍可为 `usable` 或 `degraded`，不自动视为 `excluded`

说明：

- `Disqualified` 是合法业务结论，不是运行失败
- 其系统含义是“禁止净看多”，不是自动生成做空建议

### 5.4 `sentiment` 映射规则

#### 方向映射

| 上游字段 | 标准化结果 |
|---|---|
| `sentiment_bias = Bullish` | `direction = bullish`，`direction_value = 1` |
| `sentiment_bias = Neutral` | `direction = neutral`，`direction_value = 0` |
| `sentiment_bias = Bearish` | `direction = bearish`，`direction_value = -1` |

#### `blocking_flags` 映射

规则顺序如下：

1. 默认空数组
2. 不把 `key_risks` 直接复制到 `blocking_flags`
3. 若适配层检测到运行失败或字段非法，只写适配失败标记

#### `status` 修饰规则

- `sentiment_bias` 缺失或非法：`excluded`
- `key_risks` 缺失或不是数组：`excluded`
- `low_confidence_modules` 非空：至少 `degraded`
- `data_completeness_pct` 已知且 `< 60`：至少 `degraded`

### 5.5 `event` 映射规则

#### 方向映射

| 上游字段 | 标准化结果 |
|---|---|
| `event_bias = Bullish` | `direction = bullish`，`direction_value = 1` |
| `event_bias = Neutral` | `direction = neutral`，`direction_value = 0` |
| `event_bias = Bearish` | `direction = bearish`，`direction_value = -1` |

#### `blocking_flags` 映射

规则顺序如下：

1. 若 `event_risk_flags` 合法存在，先整体透传
2. 若命中近端二元事件风险、财报窗口风险或监管结果未决风险，必须保留对应原始标记
3. 若执行失败或关键字段缺失，再追加适配失败标记

#### `status` 修饰规则

- 模块未启用：`not_enabled`
- 已启用但返回空对象：`excluded`
- 已启用但执行失败或超时：`excluded`
- `event_bias` 或 `event_risk_flags` 缺失 / 非法：`excluded`
- `low_confidence_modules` 非空：至少 `degraded`
- `data_completeness_pct` 已知且 `< 60`：至少 `degraded`
- 存在重大事件风险标记但方向可解析：至少 `degraded`

---

## 6. 缺失字段、非法字段与降级适配规则

### 6.1 缺失字段处理

处理顺序固定如下：

1. 先区分字段是否属于关键字段
2. 关键字段缺失：直接 `excluded`
3. 非关键字段缺失：保留方向映射，标记 `degraded`
4. 若缺失字段只影响摘要透传，`summary = null`
5. 若缺失字段只影响完整度计算，`data_completeness_pct = null`，并根据其他信号决定是否降级

### 6.2 模块未启用处理

- 只允许通过部署配置声明 `enabled = false`
- 未启用不是失败，不得写入 `module_execution_failed`
- 四个核心模块在当前系统基线中默认全部启用
- 若某模块在联调或兼容环境中被显式关闭，仍按同一规则进入 `not_enabled`

### 6.3 模块执行失败处理

若上游提供执行元数据，推荐按下列方式映射：

| 上游执行结果 | 适配结果 |
|---|---|
| `failed` | `status = excluded`，追加 `module_execution_failed` 到 `diagnostic_flags` |
| `timeout` | `status = excluded`，追加 `module_timeout` 到 `diagnostic_flags` |
| `interrupted` | `status = excluded`，追加 `module_execution_failed` 到 `diagnostic_flags` |
| 空对象 / 无返回 | `status = excluded`，追加 `module_output_missing` 到 `diagnostic_flags` |

说明：

- 执行失败时，除合法的 `Disqualified` 外，不再保留原方向
- 执行失败优先级高于低置信度

### 6.4 字段非法处理

字段非法包括但不限于：

- 枚举值不在允许集合内
- 数值字段为负数、超过定义范围、`NaN` 或空字符串
- 期望数组的字段返回为对象或标量

处理规则：

- 关键字段非法：`excluded`
- 非关键字段非法：`degraded`
- 非法原因必须进入 `diagnostic_flags`

### 6.5 `low_confidence` 统一生成规则

`low_confidence` 按以下顺序判定：

1. 若模块进入 `degraded` 且原因包含低覆盖、低样本或上游显式低置信度，则为 `true`
2. 若上游存在 `low_confidence_modules` 且非空，则为 `true`
3. 若 `data_completeness_pct` 已知且 `< 60`，则为 `true`
4. 其他情况为 `false`

说明：

- `excluded` 不要求 `low_confidence = true`，因为其含义是“不可用”而不是“低质量可用”
- `not_enabled` 必须为 `false`

---

## 7. 输入适配示例

### 7.1 示例一：四模块部署，全部启用

#### 原始输入

```text
deployment_config = {
  technical: { enabled: true, configured_weight: 0.50 },
  fundamental: { enabled: true, configured_weight: 0.10 },
  sentiment: { enabled: true, configured_weight: 0.20 },
  event: { enabled: true, configured_weight: 0.20 }
}

technical_payload = {
  technical_signal: "bullish",
  setup_state: "actionable",
  risk_flags: [],
  technical_summary: "趋势与动量一致。"
}

fundamental_payload = {
  fundamental_bias: "Neutral",
  key_risks: ["margin_pressure"],
  data_completeness_pct: 82,
  low_confidence_modules: []
}

sentiment_payload = {
  sentiment_bias: "Bearish",
  key_risks: ["crowded_long"],
  data_completeness_pct: 58,
  low_confidence_modules: ["narrative"]
}

event_payload = {
  event_bias: "Neutral",
  event_risk_flags: [],
  upcoming_catalysts: ["下次财报窗口在 28 天后"],
  data_completeness_pct: 84,
  low_confidence_modules: []
}
```

#### 适配结果

```text
[
  {
    module: "technical",
    enabled: true,
    status: "usable",
    direction: "bullish",
    direction_value: 1,
    configured_weight: 0.50,
    data_completeness_pct: null,
    low_confidence: false,
    blocking_flags: [],
    diagnostic_flags: [],
    key_risks: [],
    summary: "趋势与动量一致。"
  },
  {
    module: "fundamental",
    enabled: true,
    status: "usable",
    direction: "neutral",
    direction_value: 0,
    configured_weight: 0.10,
    data_completeness_pct: 82,
    low_confidence: false,
    blocking_flags: [],
    diagnostic_flags: [],
    key_risks: ["margin_pressure"],
    summary: null
  },
  {
    module: "sentiment",
    enabled: true,
    status: "degraded",
    direction: "bearish",
    direction_value: -1,
    configured_weight: 0.20,
    data_completeness_pct: 58,
    low_confidence: true,
    blocking_flags: [],
    diagnostic_flags: [],
    key_risks: ["crowded_long"],
    summary: null
  },
  {
    module: "event",
    enabled: true,
    status: "usable",
    direction: "neutral",
    direction_value: 0,
    configured_weight: 0.20,
    data_completeness_pct: 84,
    low_confidence: false,
    blocking_flags: [],
    diagnostic_flags: [],
    key_risks: [],
    summary: null
  }
]
```

说明：

- `sentiment` 因 `data_completeness_pct < 60` 且 `low_confidence_modules` 非空，被标记为 `degraded`
- `event` 正常参与适配，但未贡献系统级阻断标记

### 7.2 示例二：`event` 已启用但执行失败

#### 原始输入

```text
deployment_config = {
  event: { enabled: true, configured_weight: 0.20 }
}

event_payload = {
  execution_status: "failed"
}
```

#### 适配结果

```text
{
  module: "event",
  enabled: true,
  status: "excluded",
  direction: "neutral",
  direction_value: 0,
  configured_weight: 0.20,
  data_completeness_pct: null,
  low_confidence: false,
  blocking_flags: [],
  diagnostic_flags: ["module_execution_failed"],
  key_risks: [],
  summary: null
}
```

说明：

- `event` 已启用，因此不能降级为 `not_enabled`
- 因执行失败且无合法 `event_bias`，必须直接 `excluded`
- 失败原因需显式进入 `diagnostic_flags`，供后续系统级可追溯性使用
