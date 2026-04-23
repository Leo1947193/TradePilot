# 基本面模块聚合与信号综合

## 1. 聚合器目标与边界

本设计文档定义**基本面模块内部**的聚合器行为，用于把以下三个子模块的结构化结果汇总为单一、可追溯、可复现的基本面结论：

- 盈利动量分析器
- 财务健康检查器
- 估值锚点分析器

聚合器只负责：

- 执行硬风险否决门
- 计算固定权重下的 `composite_score`
- 处理缺失数据与低置信度输出约束
- 生成 `fundamental_bias`
- 提取 `key_risks`
- 计算 `data_completeness_pct`

聚合器明确**不负责**：

- 事件催化剂识别
- 新闻情绪、社媒情绪、期权情绪
- 分析师升级 / 降级事件解读
- 全系统跨模块总决策

说明：

- 本文中的 `composite_score` 是基本面聚合后的对外规范分数
- 其计算方式是对可用模块按固定权重做归一化后的最终结果

---

## 2. 输入依赖

### 2.1 上游输入

聚合器只读取三个子模块的结构化输出，不直接读取原始财务表、新闻或事件数据。

### 2.2 最小输入契约

#### 盈利动量模块

| 字段路径 | 用途 | 是否为计分必需 |
|---|---|---|
| `metrics.earnings_score` | 参与聚合评分 | 是 |
| `metrics.earnings_momentum` | 风险提取、偏向解释 | 是 |
| `metrics.eps_revision_balance_30d` | 风险提取、低置信度判定 | 否 |
| `metrics.avg_eps_surprise_pct_4q` | 风险提取、完整度计算 | 否 |
| `metrics.guidance_trend` | 风险提取、完整度计算 | 否 |
| `missing_fields` | 缺失字段记录 | 是 |
| `staleness_days` | 新鲜度检查 | 是 |

#### 财务健康模块

| 字段路径 | 用途 | 是否为计分必需 |
|---|---|---|
| `health_score` | 参与聚合评分 | 是 |
| `overall_rating` | 风险提取、偏向解释 | 是 |
| `disqualify` | 否决门 | 是 |
| `hard_risk_reasons` | 否决原因、风险提取 | 是 |
| `red_flag_categories` | 风险提取 | 是 |
| `checks` | 风险提取、完整度计算 | 否 |
| `data_staleness_days` | 否决门时效性校验 | 是 |
| `missing_fields` | 缺失字段记录 | 是 |

#### 估值锚点模块

| 字段路径 | 用途 | 是否为计分必需 |
|---|---|---|
| `valuation_score` | 参与聚合评分 | 是 |
| `space_rating` | 风险提取、偏向解释 | 是 |
| `historical_percentile` | 风险提取、完整度计算 | 是 |
| `peer_relative_ratio` | 风险提取、完整度计算 | 是 |
| `primary_metric_used` | 可追溯性 | 否 |
| `peg_flag` | 风险提取 | 否 |
| `missing_fields` | 缺失字段记录 | 是 |
| `staleness_days` | 新鲜度检查 | 是 |

### 2.3 模块可用性定义

聚合器对每个子模块只判定三种状态：

- `usable`：计分必需字段完整，且新鲜度在可接受范围内
- `degraded`：计分必需字段完整，但存在非计分关键字段缺失或数据偏旧
- `excluded`：计分必需字段缺失，或数据过旧，不参与分数计算

---

## 3. 否决门执行顺序

聚合顺序固定为：**先 `disqualify`，再算分**。

执行顺序如下：

1. 读取三个子模块输出
2. 校验模块状态：`usable / degraded / excluded`
3. 优先执行财务健康模块的硬风险否决门
4. 若 `disqualify = true` 且 `data_staleness_days <= 120`，直接输出 `fundamental_bias = Disqualified`
5. 仅在未触发否决门时，计算 `composite_score`
6. 应用低置信度约束
7. 生成 `fundamental_bias`
8. 提取 `key_risks`
9. 计算 `data_completeness_pct`

否决门触发后：

- 不再进行方向性打分
- `composite_score = 0`
- `weight_scheme_used.applied_weights = {}`
- `fundamental_bias = Disqualified`

这样做的原因是：`Disqualified` 表示近端硬风险已经足以覆盖方向性分数，继续给出看涨 / 看跌分数会误导下游。

### 3.1 聚合伪代码

```text
configured_weights = {
  earnings: 0.45,
  health: 0.35,
  valuation: 0.20
}

module_state = assess_module_state(inputs)

if health.disqualify == true and health.data_staleness_days <= 120:
    return {
      composite_score: 0,
      fundamental_bias: "Disqualified",
      low_confidence_modules: collect_low_confidence(module_state),
      key_risks: extract_key_risks(inputs, module_state),
      data_completeness_pct: calc_data_completeness(inputs, module_state),
      weight_scheme_used: {
        configured_weights: configured_weights,
        available_weight_sum: 0.0,
        applied_weights: {},
        renormalized: false
      }
    }

available_modules = filter(module_state in ["usable", "degraded"])
available_weight_sum = sum(configured_weights[module] for module in available_modules)

if available_weight_sum > 0:
    normalized_weights[module] = configured_weights[module] / available_weight_sum
    composite_score =
      sum(score[module] * normalized_weights[module] for module in available_modules)
else:
    composite_score = 0

data_completeness_pct = calc_data_completeness(inputs, module_state)
low_confidence_modules = collect_low_confidence(module_state)

if available_weight_sum < 0.70 or data_completeness_pct < 60:
    fundamental_bias = "Neutral"
else if composite_score >= 70:
    fundamental_bias = "Bullish"
else if composite_score < 45:
    fundamental_bias = "Bearish"
else:
    fundamental_bias = "Neutral"
```

---

## 4. 固定权重设计

### 4.1 配置权重

为与 `fundamental_analysis_agent/overview.md` 保持一致，聚合器固定使用以下配置权重：

- `earnings`：`0.45`
- `health`：`0.35`
- `valuation`：`0.20`

### 4.2 设计原则

- `earnings` 权重最高，因为中期交易窗口内，盈利兑现与预期修正最直接影响方向
- `health` 次高，因为财务脆弱性决定下行尾部风险与否决门
- `valuation` 最低，因为估值更适合作为顺风 / 逆风背景，不应单独主导方向

### 4.3 `weight_scheme_used`

聚合器必须输出实际使用的权重方案，字段固定如下：

```text
weight_scheme_used = {
  configured_weights: {
    earnings: 0.45,
    health: 0.35,
    valuation: 0.20
  },
  available_weight_sum: number,
  applied_weights: {
    earnings?: number,
    health?: number,
    valuation?: number
  },
  renormalized: boolean
}
```

规则：

- 若三个模块都可用，`available_weight_sum = 1.00`
- 若存在缺失模块，`available_weight_sum` 等于可用模块的配置权重之和
- `applied_weights` 必须是归一化后的最终权重，和为 `1.00`
- 只要有任一模块被排除，`renormalized = true`

---

## 5. 缺失数据归一化规则

### 5.1 `composite_score`

规范公式如下：

```text
composite_score =
  sum(available_module_score × normalized_module_weight)
```

其中：

```text
normalized_module_weight =
  configured_module_weight / available_weight_sum
```

只有 `usable` 或 `degraded` 模块可以进入归一化分数；`excluded` 模块权重视为 `0`。

### 5.2 模块排除规则

以下情况之一成立时，模块必须记为 `excluded`，且不参与 `composite_score`：

- 计分必需字段缺失
- 分数字段不存在或不在 `0-100` 范围内
- 模块输出整体缺失
- 新鲜度超过排除阈值

排除阈值固定如下：

| 模块 | 降级阈值 | 排除阈值 |
|---|---|---|
| `earnings` | `staleness_days > 45` | `staleness_days > 90` |
| `health` | `data_staleness_days > 120` | `data_staleness_days > 180` |
| `valuation` | `staleness_days > 15` | `staleness_days > 30` |

### 5.3 模块降级规则

以下情况之一成立时，模块记为 `degraded`，仍参与打分，但必须写入 `low_confidence_modules`：

- 非计分关键字段缺失
- 数据新鲜度超过降级阈值但未超过排除阈值
- `missing_fields` 非空

### 5.4 为什么 `available_weight_sum < 0.70` 只能输出 `Neutral`

`0.70` 阈值是硬约束，不是建议值。

原因如下：

- 任意单模块都不足以独立输出方向
- `valuation` 权重只有 `0.20`，只能做背景修正，不能主导方向
- 缺少 `earnings` 时，剩余最大权重仅 `0.55`
- 缺少 `health` 时，剩余最大权重仅 `0.65`
- 因此，`available_weight_sum >= 0.70` 实际上要求至少同时拿到两个核心证据中的充分组合，避免单模块极端值直接推导出 `Bullish` 或 `Bearish`

结论：

- 当 `available_weight_sum < 0.70` 时，允许输出分数，但 `fundamental_bias` 必须被压制为 `Neutral`

---

## 6. 低置信度约束

### 6.1 `low_confidence_modules` 写入规则

`low_confidence_modules` 必须写入所有 `degraded` 或 `excluded` 模块，结构固定如下：

```text
low_confidence_modules = [
  {
    module: "earnings" | "health" | "valuation",
    status: "degraded" | "excluded",
    reason_codes: string[],
    excluded_from_score: boolean
  }
]
```

固定 `reason_codes` 只允许以下值：

- `missing_required_fields`
- `missing_non_required_fields`
- `stale_data`
- `missing_module_output`
- `invalid_score_range`

### 6.2 方向压制规则

除 `Disqualified` 外，以下任一条件成立时，`fundamental_bias` 必须压制为 `Neutral`：

- `available_weight_sum < 0.70`
- `data_completeness_pct < 60`
- `available_weight_sum = 0`

说明：

- 低置信度约束只压制方向，不会把 `Neutral` 改成 `Bullish` 或 `Bearish`
- `Disqualified` 不受该压制规则影响，因为其来源是显式硬风险，而不是方向性打分

---

## 7. `fundamental_bias` 判定规则

`fundamental_bias` 只能取以下四个值：

- `Bullish`
- `Neutral`
- `Bearish`
- `Disqualified`

严格判定顺序如下：

1. 若命中否决门，输出 `Disqualified`
2. 否则若 `available_weight_sum < 0.70`，输出 `Neutral`
3. 否则若 `data_completeness_pct < 60`，输出 `Neutral`
4. 否则若 `composite_score >= 70`，输出 `Bullish`
5. 否则若 `composite_score < 45`，输出 `Bearish`
6. 其余情况输出 `Neutral`

为避免边界歧义，区间定义固定为：

- `Bullish`：`[70, 100]`
- `Neutral`：`[45, 70)`
- `Bearish`：`[0, 45)`
- `Disqualified`：独立于分数区间

---

## 8. `key_risks` 提取规则

### 8.1 提取目标

`key_risks` 用于输出**最值得下游关注**的基本面风险，不是所有负面字段的堆叠列表。

约束如下：

- 最多输出 `4` 条
- 必须使用固定模板生成
- 必须带来源模块与规则编号
- 必须按优先级降序输出

### 8.2 风险提取优先级与去重规则表

| 优先级 | 规则编号 | 来源字段 | 触发条件 | 输出模板 | 去重键 |
|---|---|---|---|---|---|
| `100` | `HR1` | `health.hard_risk_reasons[]` | `disqualify = true` | `近端硬风险：{reason}` | `hard_risk:{reason}` |
| `90` | `HR2` | `health.red_flag_categories[]` | 类别级红旗存在 | `财务健康红旗：{category}` | `health_red_flag:{category}` |
| `80` | `ER1` | `earnings.metrics.guidance_trend` | `guidance_trend = Lowered` | `管理层指引下修` | `earnings:guidance_lowered` |
| `75` | `ER2` | `earnings.metrics.eps_revision_balance_30d` | `<= -0.25` | `近 30 天 EPS 预期显著下修` | `earnings:eps_revision_down` |
| `70` | `ER3` | `earnings.metrics.earnings_momentum` | `Decelerating` | `盈利动量走弱` | `earnings:momentum_decelerating` |
| `65` | `ER4` | `earnings.metrics.avg_revenue_surprise_pct_4q` | `< 0` | `营收兑现弱于预期` | `earnings:revenue_miss` |
| `60` | `VR1` | `valuation.space_rating` | `Compressed` | `估值处于压缩风险区间` | `valuation:compressed` |
| `55` | `VR2` | `valuation.space_rating` | `Elevated` | `估值偏高，继续扩张空间有限` | `valuation:elevated` |
| `50` | `VR3` | `valuation.peer_relative_ratio` | `> 1.20` | `相对板块估值溢价过高` | `valuation:peer_premium` |
| `45` | `VR4` | `valuation.peg_flag` | `peg_flag ∈ {GrowthTooLow, NegativeGrowth, NegativeOrZeroMultiple}` | `增长调整后估值不占优` | `valuation:peg_flag` |

### 8.3 去重规则

去重顺序固定如下：

1. 先按 `去重键` 分组
2. 同组内保留**优先级最高**的一条
3. 若优先级相同，保留**最近时间戳**的一条
4. 若时间戳仍相同，按模块顺序保留：`health > earnings > valuation`

### 8.4 截断规则

去重完成后：

- 按 `优先级降序` 排序
- 只保留前 `4` 条
- 若无风险命中，输出空数组 `[]`

### 8.5 输出结构

```text
key_risks = [
  {
    risk_key: string,
    risk_label: string,
    source_module: "earnings" | "health" | "valuation",
    rule_id: string,
    priority: number
  }
]
```

---

## 9. `data_completeness_pct` 计算规则

### 9.1 计算口径

`data_completeness_pct` **不是按原始字段简单计数**，也不是按模块平均。

本设计采用：**关键字段覆盖率 × 模块配置权重** 的加权计算。

即：

- 先计算每个模块的关键字段覆盖率
- 再按模块固定权重加总
- 最终输出 `0-100` 的百分比

### 9.2 模块内关键字段权重

#### `earnings`

| 字段 | 模块内权重 |
|---|---|
| `earnings_score` | `0.35` |
| `earnings_momentum` | `0.20` |
| `eps_revision_balance_30d` | `0.20` |
| `avg_eps_surprise_pct_4q` | `0.15` |
| `guidance_trend` | `0.10` |

#### `health`

| 字段 | 模块内权重 |
|---|---|
| `health_score` | `0.30` |
| `overall_rating` | `0.15` |
| `disqualify` | `0.20` |
| `hard_risk_reasons` | `0.10` |
| `checks` | `0.15` |
| `data_staleness_days` | `0.10` |

#### `valuation`

| 字段 | 模块内权重 |
|---|---|
| `valuation_score` | `0.35` |
| `space_rating` | `0.20` |
| `historical_percentile` | `0.20` |
| `peer_relative_ratio` | `0.15` |
| `primary_metric_used` | `0.10` |

### 9.3 字段计分规则

每个关键字段只能按以下规则计分：

- 字段存在，且未超过降级阈值：记满分
- 字段存在，但所在模块超过降级阈值且未超过排除阈值：记 `50%`
- 字段缺失、为空、或模块已被排除：记 `0`

### 9.4 计算公式

```text
module_completeness_score =
  sum(field_present_score × field_weight)

data_completeness_pct =
  100 × (
    earnings_module_completeness_score × 0.45 +
    health_module_completeness_score   × 0.35 +
    valuation_module_completeness_score × 0.20
  )
```

### 9.5 使用规则

- `data_completeness_pct >= 85`：可视为高完整度
- `60 <= data_completeness_pct < 85`：允许方向判断
- `data_completeness_pct < 60`：只允许输出 `Neutral` 或 `Disqualified`

---

## 10. 输出 Schema

API 对齐说明：

- 本节 Schema 定义的是基本面聚合器内部输出
- 它是公共 `fundamental_analysis` 对象的上游来源，但不等同于最终 HTTP 响应
- 最终对外契约见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

```json
{
  "composite_score": "number",
  "fundamental_bias": "Bullish | Neutral | Bearish | Disqualified",
  "low_confidence_modules": [
    {
      "module": "earnings | health | valuation",
      "status": "degraded | excluded",
      "reason_codes": ["string"],
      "excluded_from_score": "boolean"
    }
  ],
  "data_completeness_pct": "number",
  "weight_scheme_used": {
    "configured_weights": {
      "earnings": "number",
      "health": "number",
      "valuation": "number"
    },
    "available_weight_sum": "number",
    "applied_weights": {
      "earnings": "number",
      "health": "number",
      "valuation": "number"
    },
    "renormalized": "boolean"
  },
  "key_risks": [
    {
      "risk_key": "string",
      "risk_label": "string",
      "source_module": "earnings | health | valuation",
      "rule_id": "string",
      "priority": "number"
    }
  ]
}
```

字段约束：

- `composite_score` 保留 1 位小数
- `data_completeness_pct` 保留 1 位小数
- `key_risks` 长度上限为 `4`
- `low_confidence_modules` 只记录非高置信度模块，不记录 `usable` 模块

---

## 11. 完整示例

### 11.1 正常输出示例

假设：

- `earnings_score = 84`
- `health_score = 72`
- `valuation_score = 55`
- 三个模块全部可用

计算结果：

```text
composite_score =
  84 × 0.45 + 72 × 0.35 + 55 × 0.20
  = 74.0
```

输出示例：

```json
{
  "composite_score": 74.0,
  "fundamental_bias": "Bullish",
  "low_confidence_modules": [],
  "data_completeness_pct": 94.0,
  "weight_scheme_used": {
    "configured_weights": {
      "earnings": 0.45,
      "health": 0.35,
      "valuation": 0.20
    },
    "available_weight_sum": 1.0,
    "applied_weights": {
      "earnings": 0.45,
      "health": 0.35,
      "valuation": 0.20
    },
    "renormalized": false
  },
  "key_risks": [
    {
      "risk_key": "health_red_flag:leverage_pressure",
      "risk_label": "财务健康红旗：leverage_pressure",
      "source_module": "health",
      "rule_id": "HR2",
      "priority": 90
    },
    {
      "risk_key": "valuation:elevated",
      "risk_label": "估值偏高，继续扩张空间有限",
      "source_module": "valuation",
      "rule_id": "VR2",
      "priority": 55
    }
  ]
}
```

### 11.2 低置信度输出示例

假设：

- `earnings` 模块缺失，无法参与打分
- `health_score = 62`
- `valuation_score = 84`
- `available_weight_sum = 0.55`

计算结果：

```text
composite_score =
  (62 × 0.35 + 84 × 0.20) / 0.55
  = 70.0
```

虽然归一化分数达到 `70.0`，但由于 `available_weight_sum < 0.70`，最终只能输出 `Neutral`。

输出示例：

```json
{
  "composite_score": 70.0,
  "fundamental_bias": "Neutral",
  "low_confidence_modules": [
    {
      "module": "earnings",
      "status": "excluded",
      "reason_codes": ["missing_module_output"],
      "excluded_from_score": true
    }
  ],
  "data_completeness_pct": 55.0,
  "weight_scheme_used": {
    "configured_weights": {
      "earnings": 0.45,
      "health": 0.35,
      "valuation": 0.20
    },
    "available_weight_sum": 0.55,
    "applied_weights": {
      "health": 0.6364,
      "valuation": 0.3636
    },
    "renormalized": true
  },
  "key_risks": [
    {
      "risk_key": "health_red_flag:cashflow_quality",
      "risk_label": "财务健康红旗：cashflow_quality",
      "source_module": "health",
      "rule_id": "HR2",
      "priority": 90
    }
  ]
}
```

---

## 12. 可复现性约束

为保证聚合行为可复现，聚合器必须满足以下要求：

- 固定执行顺序，不允许先算分再补否决门
- 固定权重，不允许按自然语言解释动态调权
- 固定阈值，不允许使用“由模型判断是否偏高 / 偏低”
- 固定 `reason_codes`、`rule_id` 和风险模板
- 固定缺失数据归一化公式与 `Neutral` 压制条件

只要输入字段相同，聚合输出必须相同。
