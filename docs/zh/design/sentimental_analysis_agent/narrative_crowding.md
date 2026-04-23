# ③ 叙事与拥挤度分析器 — 子模块设计文档

## 1. 模块职责与边界

### 1.1 模块职责

本模块负责把标题级新闻和提及量时间序列转换为**可计算的市场叙事结构**，回答两个问题：

1. 最近 14 天市场是否形成了清晰、可重复验证的主导叙事
2. 该叙事是否已经进入注意力异常放大、容易反身性回撤的拥挤状态

模块必须输出固定字段，供情绪模块聚合器直接消费：

- `dominant_bullish_narratives`
- `dominant_bearish_narratives`
- `dominant_bullish_theme_share`
- `dominant_bearish_theme_share`
- `contradiction_ratio`
- `attention_zscore_7d`
- `crowding_flag`
- `narrative_state`
- `narrative_score`

### 1.2 范围边界

| 范围内 | 范围外 |
|---|---|
| 标题 / 摘要中的主题提取、方向归类、主题占比统计 | 事件日历识别（财报、FOMC、FDA 等） |
| 最近 14 天主导叙事和分歧程度判定 | EPS、营收一致预期数值建模 |
| 最近 7 天注意力异常检测与拥挤风险标记 | 价格趋势、突破 / 破位、成交量结构分析 |
| 结构化 `risk_flags` 供聚合层映射为 `key_risks` | 自动生成交易指令 |

### 1.3 与其他模块的关系

- 本模块只判断**市场在说什么、关注什么、是否过热**，不判断价格是否确认
- 若出现高关注度但没有清晰叙事，本模块只输出 `attention_spike_unconfirmed`，不替代事件模块做催化剂判断
- 若出现一致看空叙事，本模块只输出 `Fragile`，不替代技术模块做止损或回撤判断

---

## 2. 输入规格

### 2.1 标题级文本输入

每条记录必须至少包含以下字段：

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `headline` | `string` | 是 | 新闻标题 |
| `summary` | `string \| null` | 否 | 新闻摘要；缺失时仅使用标题 |
| `published_at` | `ISO 8601` | 是 | 发布时间 |
| `source_name` | `string` | 是 | 来源名称 |
| `source_type` | `news \| wire \| analyst \| social` | 是 | 来源类型 |
| `url` | `string` | 是 | 唯一来源标识；用于去重和追溯 |
| `language` | `string` | 是 | 语言代码 |
| `relevance_score` | `number` | 是 | 与标的相关性，范围 `[0, 1]` |

### 2.2 提及量时间序列

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `date` | `date` | 是 | 按 `primary_market` 所属时区归档的自然日 |
| `mention_count` | `int` | 是 | 当日去重后提及量 |
| `unique_source_count` | `int` | 是 | 当日独立来源数 |

- 当前窗口使用最近 **7 个自然日**
- 基线窗口使用当前窗口之前的 **90 个自然日**
- `mention_count` 必须和标题级去重口径一致

### 2.3 可选社媒输入

若存在社媒数据，可作为 `mention_count` 的组成部分，但必须满足：

- `source_type = social`
- 与新闻源分开记录原始来源
- 不得因社媒缺失而阻塞模块运行

### 2.4 最低可用性要求

| 条件 | 阈值 | 不满足时处理 |
|---|---|---|
| 最近 14 天方向性标题数 | `>= 6` | 标记 `insufficient_directional_evidence`，`narrative_state` 强制降为 `Mixed` |
| 最近 14 天独立来源数 | `>= 3` | 标记 `insufficient_directional_evidence`，`narrative_state` 强制降为 `Mixed` |
| 最近 90 天基线日数 | `>= 30` | `attention_zscore_7d = 0.0`，标记 `attention_baseline_unavailable` |

---

## 3. 主题提取与归类原则

### 3.1 预处理与去重

主题提取前必须先做去重，避免同一新闻在不同入口重复计数。

**去重优先级：**

1. `url` 完全相同，视为同一条记录，只保留一条
2. 若 `url` 缺失，则对 `headline_normalized + source_name + published_date` 做精确匹配去重
3. 同一来源在 24 小时内重复发布的标题，若标准化标题完全一致，只保留发布时间最早的一条

**标准化规则：**

- 去除大小写差异
- 去除首尾空白和重复空格
- 去除纯格式差异的标点变化
- 不做语义改写，不做跨标题合并

### 3.2 提取单元

- 每条记录最多提取 **2 个主题**
- 仅 `relevance_score >= 0.60` 的记录进入主题提取
- `headline` 与 `summary` 冲突时，以 `headline` 为主，`summary` 只作补充，不得反转标题方向
- 无法映射到固定主题字典的记录，不进入方向性主题统计，但保留在原始追溯记录中

### 3.3 固定主题字典

为保证确定性，主题必须落到固定 `theme_group` 与固定方向枚举，禁止自由生成新类别进入主统计。

| `theme_group` | 看多方向示例 | 看空方向示例 | 判断依据 |
|---|---|---|---|
| `demand_cycle` | 需求加速、订单上修、库存改善 | 需求放缓、订单削减、去库存压力 | 需求与销量预期变化 |
| `product_execution` | 新产品放量、交付顺利、产能爬坡顺利 | 发布延期、交付失误、供应链受阻 | 产品与执行兑现情况 |
| `margin_cost` | 毛利率改善、成本下行、定价权增强 | 毛利率承压、成本上行、价格竞争 | 利润率与成本结构 |
| `capital_financing` | 现金回流、融资条件改善、回购增强 | 融资压力、稀释风险、现金消耗 | 资产负债与资金面叙事 |
| `regulation_policy` | 政策支持、审批推进、监管边际放松 | 监管调查、政策不利、审批受阻 | 政策与监管方向 |
| `valuation_positioning` | 估值重估、机构增配、稀缺性溢价 | 估值过高、交易拥挤、机构减配 | 仓位和估值偏好 |

### 3.4 活跃主题定义

只有满足以下条件的主题，才计入主导叙事和分歧率计算：

- 最近 14 天 `mention_count_14d >= 2`
- 最近 14 天 `source_count_14d >= 2`

不满足条件的主题：

- 不进入 `dominant_*_narratives`
- 不进入 `contradiction_ratio`
- 仍保留在 `theme_trace` 中，供人工追溯

### 3.5 主导叙事排序规则

分别对 bullish 和 bearish 方向的活跃主题排序：

1. `mention_count_14d` 降序
2. `source_count_14d` 降序
3. `latest_published_at` 降序

输出时：

- `dominant_bullish_narratives` 取前 `1-3` 个看多主题标签
- `dominant_bearish_narratives` 取前 `1-3` 个看空主题标签

---

## 4. 核心指标计算口径

### 4.1 `dominant_bullish_theme_share` 与 `dominant_bearish_theme_share`

定义：

- `top_bullish_mentions_14d`：最近 14 天看多活跃主题中，提及量最高的主题提及数
- `top_bearish_mentions_14d`：最近 14 天看空活跃主题中，提及量最高的主题提及数
- `total_directional_theme_mentions_14d`：最近 14 天所有看多和看空活跃主题提及量之和

计算公式：

```text
dominant_bullish_theme_share =
  top_bullish_mentions_14d / max(total_directional_theme_mentions_14d, 1)

dominant_bearish_theme_share =
  top_bearish_mentions_14d / max(total_directional_theme_mentions_14d, 1)
```

说明：

- 若某一方向不存在活跃主题，则该方向 share 记为 `0.0`
- 分母只统计活跃且有明确方向的主题，不含无法归类主题

### 4.2 `contradiction_ratio`

本指标用于衡量叙事是否分裂，严格按**活跃主题数量**而非标题数量计算。

定义：

- `bullish_active_theme_count`：最近 14 天看多活跃主题数
- `bearish_active_theme_count`：最近 14 天看空活跃主题数
- `active_theme_count`：两者之和
- `contradictory_theme_count`：`min(bullish_active_theme_count, bearish_active_theme_count)`

计算公式：

```text
contradiction_ratio =
  contradictory_theme_count / max(active_theme_count, 1)
```

边界含义：

| 场景 | 结果 |
|---|---|
| 只有单边主题存在 | `0.0` |
| 3 个看多主题 + 1 个看空主题 | `0.25` |
| 2 个看多主题 + 2 个看空主题 | `0.50` |

说明：

- `contradiction_ratio` 的理论范围是 `[0.0, 0.5]`
- 该指标越接近 `0.5`，说明正反叙事越均衡、分歧越大

### 4.3 `attention_zscore_7d`

本指标用于衡量最近 7 天关注度是否显著高于历史常态。

#### 4.3.1 当前值

```text
mentions_7d_current =
  sum(mention_count[d]) , d in 最近 7 个自然日
```

#### 4.3.2 90 天基线

基线窗口为当前 7 日窗口之前的 90 个自然日。为了保证口径一致，基线使用**历史滚动 7 日提及总量**：

```text
rolling_mentions_7d[i] =
  sum(mention_count[d]) , d in [i-6, i]
```

其中 `i` 取自基线窗口内所有可构成完整 7 日滚动值的日期。

#### 4.3.3 标准分

```text
baseline_mean_7d = mean(rolling_mentions_7d)
baseline_std_7d  = population_std(rolling_mentions_7d)

attention_zscore_7d =
  (mentions_7d_current - baseline_mean_7d) / baseline_std_7d
```

**特殊处理：**

- 若 `baseline_std_7d = 0`，则 `attention_zscore_7d = 0.0`
- 若可用基线滚动值少于 `30` 个，则 `attention_zscore_7d = 0.0`
- 两种情况都必须追加 `attention_baseline_unavailable`

### 4.4 `source_diversity_7d`

本指标用于衡量最近 7 天参与叙事形成的独立来源覆盖度，供聚合层做低置信度判断。

定义：

- `recent_unique_sources_7d`：最近 7 天内，完成标题级去重且 `relevance_score >= 0.60` 的记录对应的去重后独立 `source_name`

计算公式：

```text
source_diversity_7d =
  count(distinct source_name in recent_unique_sources_7d)
```

说明：

- 只统计去重后的有效标题，避免同一来源重复转载抬高覆盖度
- `source_diversity_7d < 3` 不直接改变方向，但必须触发低覆盖降级

### 4.5 追溯字段要求

每个进入统计的活跃主题必须保留：

- `theme_group`
- `theme_direction`
- `mention_count_14d`
- `source_count_14d`
- `headline_ids`
- `representative_urls`
- `first_published_at`
- `latest_published_at`

---

## 5. 判定规则

### 5.1 `crowding_flag`

与 overview 保持一致，`crowding_flag = true` 当且仅当同时满足：

- `attention_zscore_7d >= 2.0`
- `max(dominant_bullish_theme_share, dominant_bearish_theme_share) >= 0.50`

否则：

- `crowding_flag = false`

### 5.2 `narrative_state`

判定顺序采用**低可用性优先、负面优先、其余保守**的规则。

#### 5.2.1 低可用性优先

若满足以下任一条件，直接输出：

- `narrative_state = Mixed`
- 并追加 `insufficient_directional_evidence`

触发条件：

- 最近 14 天方向性标题数 `< 6`
- 或最近 14 天独立来源数 `< 3`

#### 5.2.2 正常判定

在满足最低可用性要求后，按以下顺序判定：

| 优先级 | 条件 | `narrative_state` |
|---|---|---|
| 1 | `dominant_bearish_theme_share >= 0.45` | `Fragile` |
| 2 | `contradiction_ratio >= 0.45` | `Fragile` |
| 3 | `crowding_flag = true` 且 `dominant_bearish_theme_share >= dominant_bullish_theme_share` | `Fragile` |
| 4 | `dominant_bullish_theme_share >= 0.45` 且 `contradiction_ratio <= 0.30` 且 `crowding_flag = false` | `Supportive` |
| 5 | 其他情况 | `Mixed` |

### 5.3 边界处理

| 场景 | 处理 |
|---|---|
| `dominant_bullish_theme_share = 0.45` | 满足 `Supportive` 的 share 门槛 |
| `contradiction_ratio = 0.30` | 仍可判为 `Supportive` |
| `contradiction_ratio = 0.45` | 直接判为 `Fragile` |
| `attention_zscore_7d = 2.0` 且主导主题 share = `0.50` | `crowding_flag = true` |

---

## 6. 风险标记

模块必须输出 `risk_flags: string[]`，用于聚合层映射为 `key_risks`。

| `risk_flag` | 触发条件 | 含义 |
|---|---|---|
| `narrative_split` | `contradiction_ratio >= 0.45` | 市场叙事明显分裂 |
| `crowding_long_bias` | `crowding_flag = true` 且 `dominant_bullish_theme_share > dominant_bearish_theme_share` | 正向叙事过热，存在反身性回撤风险 |
| `crowding_short_bias` | `crowding_flag = true` 且 `dominant_bearish_theme_share >= dominant_bullish_theme_share` | 负向叙事过热，存在踩踏式下修风险 |
| `attention_spike_unconfirmed` | `attention_zscore_7d >= 2.0` 且 `max(dominant_bullish_theme_share, dominant_bearish_theme_share) < 0.50` | 注意力放大，但未形成单边叙事 |
| `insufficient_directional_evidence` | 最近 14 天方向性标题 `< 6` 或独立来源 `< 3` | 数据不足，不允许给出强方向结论 |
| `attention_baseline_unavailable` | 基线窗口不足或标准差为 `0` | 无法可靠评估注意力异常 |

说明：

- `risk_flags` 只追加，不互斥
- 同一条件在同一次运行中只记录一次

---

## 7. 模块评分

与 overview 保持一致：

```text
narrative_score =
  narrative_alignment_score   (0-40) +
  contradiction_score         (0-25) +
  attention_score             (0-20) +
  crowding_penalty_adjustment (0-15)
```

### 7.1 `narrative_alignment_score`（0-40）

先计算：

```text
net_theme_share =
  dominant_bullish_theme_share - dominant_bearish_theme_share
```

再按下表取值：

| 条件 | 分值 |
|---|---|
| `net_theme_share >= 0.25` | `40` |
| `0.10 <= net_theme_share < 0.25` | `30` |
| `-0.10 < net_theme_share < 0.10` | `20` |
| `-0.25 < net_theme_share <= -0.10` | `10` |
| `net_theme_share <= -0.25` | `0` |

### 7.2 `contradiction_score`（0-25）

| 条件 | 分值 |
|---|---|
| `contradiction_ratio <= 0.20` | `25` |
| `0.20 < contradiction_ratio <= 0.30` | `18` |
| `0.30 < contradiction_ratio < 0.45` | `8` |
| `contradiction_ratio >= 0.45` | `0` |

### 7.3 `attention_score`（0-20）

| 条件 | 分值 |
|---|---|
| `1.0 <= attention_zscore_7d < 2.0` 且 `net_theme_share > 0.10` | `20` |
| `0.0 <= attention_zscore_7d < 1.0` 且 `net_theme_share > 0.10` | `14` |
| `attention_zscore_7d >= 2.0` 且 `net_theme_share > 0.10` | `10` |
| `-0.10 <= net_theme_share <= 0.10` | `10` |
| `1.0 <= attention_zscore_7d < 2.0` 且 `net_theme_share < -0.10` | `4` |
| `attention_zscore_7d >= 2.0` 且 `net_theme_share < -0.10` | `0` |
| 其他情况 | `8` |

### 7.4 `crowding_penalty_adjustment`（0-15）

| 条件 | 分值 |
|---|---|
| `crowding_flag = false` 且不包含 `attention_spike_unconfirmed` | `15` |
| `crowding_flag = false` 且包含 `attention_spike_unconfirmed` | `8` |
| `crowding_flag = true` | `0` |

### 7.5 低可用性封顶规则

若 `risk_flags` 包含以下任一项：

- `insufficient_directional_evidence`
- `attention_baseline_unavailable`

则：

- `narrative_score` 仍按上述规则计算
- 但最终结果必须执行 `min(narrative_score, 55)`

---

## 8. 缺失数据处理

### 8.1 标题缺失摘要

- 允许
- 仅使用 `headline`
- 不追加风险标记

### 8.2 无法提取方向性主题

若最近 14 天所有记录都无法映射到固定主题字典，则输出：

- `dominant_bullish_narratives = []`
- `dominant_bearish_narratives = []`
- `dominant_bullish_theme_share = 0.0`
- `dominant_bearish_theme_share = 0.0`
- `contradiction_ratio = 0.0`
- `crowding_flag = false`
- `narrative_state = Mixed`
- `risk_flags` 追加 `insufficient_directional_evidence`

### 8.3 缺失 90 天提及基线

若缺失或不足以形成有效基线：

- `attention_zscore_7d = 0.0`
- `crowding_flag = false`
- `risk_flags` 追加 `attention_baseline_unavailable`

### 8.4 单一来源放大

若最近 7 天 `unique_source_count < 3` 且 `attention_zscore_7d >= 2.0`：

- 不修改 `attention_zscore_7d`
- 但必须追加 `insufficient_directional_evidence`
- `narrative_state` 维持 `Mixed`

---

## 9. 输出 Schema

API 对齐说明：

- 本节 Schema 仅用于 `narrative_crowding` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

### 9.1 主输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | `string` | 固定为 `"1.0"` |
| `ticker` | `string` | 股票代码 |
| `analysis_timestamp` | `ISO 8601` | 本次分析执行时间 |
| `module` | `string` | 固定为 `"NarrativeCrowdingAnalyzerV1"` |
| `staleness_days` | `number` | 最近一次有效数据相对分析时间的天数 |
| `missing_fields` | `string[]` | 输出时缺失的关键字段名 |
| `analysis_window_days` | `number` | 固定为 `14` |
| `dominant_bullish_narratives` | `string[]` | 最近 14 天前 1-3 个看多主导叙事 |
| `dominant_bearish_narratives` | `string[]` | 最近 14 天前 1-3 个看空主导叙事 |
| `dominant_bullish_theme_share` | `number` | 范围 `[0, 1]` |
| `dominant_bearish_theme_share` | `number` | 范围 `[0, 1]` |
| `contradiction_ratio` | `number` | 范围 `[0, 0.5]` |
| `attention_zscore_7d` | `number` | 最近 7 天提及量标准分 |
| `source_diversity_7d` | `number` | 最近 7 天独立来源数 |
| `crowding_flag` | `boolean` | 是否触发拥挤标记 |
| `narrative_state` | `Supportive \| Mixed \| Fragile` | 模块方向状态 |
| `narrative_score` | `number` | 范围 `[0, 100]` |
| `risk_flags` | `string[]` | 模块风险标记 |
| `theme_trace` | `ThemeTraceItem[]` | 活跃主题追溯信息 |

### 9.2 `ThemeTraceItem`

```json
{
  "theme_group": "string",
  "theme_direction": "bullish | bearish",
  "theme_label": "string",
  "mention_count_14d": "number",
  "source_count_14d": "number",
  "headline_ids": ["string"],
  "representative_urls": ["string"],
  "first_published_at": "ISO 8601",
  "latest_published_at": "ISO 8601"
}
```

### 9.3 JSON 示例

```json
{
  "schema_version": "1.0",
  "ticker": "NVDA",
  "analysis_timestamp": "2026-04-16T10:00:00Z",
  "module": "NarrativeCrowdingAnalyzerV1",
  "staleness_days": 1,
  "missing_fields": [],
  "analysis_window_days": 14,
  "dominant_bullish_narratives": [
    "需求加速",
    "新产品放量"
  ],
  "dominant_bearish_narratives": [
    "估值过高"
  ],
  "dominant_bullish_theme_share": 0.54,
  "dominant_bearish_theme_share": 0.15,
  "contradiction_ratio": 0.25,
  "attention_zscore_7d": 2.34,
  "source_diversity_7d": 6,
  "crowding_flag": true,
  "narrative_state": "Mixed",
  "narrative_score": 58,
  "risk_flags": [
    "crowding_long_bias"
  ],
  "theme_trace": [
    {
      "theme_group": "demand_cycle",
      "theme_direction": "bullish",
      "theme_label": "需求加速",
      "mention_count_14d": 7,
      "source_count_14d": 5,
      "headline_ids": ["h_102", "h_118", "h_130"],
      "representative_urls": [
        "https://example.com/news/102",
        "https://example.com/news/118"
      ],
      "first_published_at": "2026-04-02T08:00:00Z",
      "latest_published_at": "2026-04-14T13:30:00Z"
    },
    {
      "theme_group": "valuation_positioning",
      "theme_direction": "bearish",
      "theme_label": "估值过高",
      "mention_count_14d": 2,
      "source_count_14d": 2,
      "headline_ids": ["h_109", "h_121"],
      "representative_urls": [
        "https://example.com/news/109"
      ],
      "first_published_at": "2026-04-05T15:00:00Z",
      "latest_published_at": "2026-04-12T10:10:00Z"
    }
  ]
}
```

---

## 10. 实现约束

### 10.1 确定性优先

- 同一输入、同一 `classifier_version`、同一规则版本，必须产生同一输出
- LLM 允许参与主题抽取，但最终必须落回固定 `theme_group` 和固定方向标签
- 不允许把自然语言解释直接写回结构化主字段

### 10.2 可追溯性优先

- `dominant_*_narratives` 中的每个主题必须能追溯到 `headline_ids` 和 `representative_urls`
- `crowding_flag` 必须能回溯到 `attention_zscore_7d` 的基线明细
- `risk_flags` 必须能映射到明确阈值，不允许主观描述

### 10.3 保守降级优先

- 数据不足时宁可输出 `Mixed`，也不输出高置信度单边结论
- 基线缺失时宁可禁用拥挤判定，也不推测注意力异常
