# 情绪分析模块聚合与信号综合

## 1. 聚合器目标与边界

本设计文档定义**情绪分析模块内部**的聚合器行为，用于把以下三个子模块的结构化结果汇总为单一、可追溯、可复现的情绪结论：

- 新闻基调分析器
- 预期变化分析器
- 叙事与拥挤度分析器

聚合器只负责：

- 读取三个子模块的结构化输出，不重新解释原始新闻文本
- 将子模块结果映射为方向性子信号，生成统一的规范分数
- 在固定权重下计算 `normalized_composite_score`
- 处理缺失数据、陈旧数据与低置信度约束
- 生成 `sentiment_bias`
- 生成 `market_expectation`
- 提取 `key_risks`
- 输出 `data_completeness_pct`、`weight_scheme_used` 与 `low_confidence_modules`

聚合器明确**不负责**：

- 重新执行标题级情绪分类
- 重新计算分析师动作、目标价修正或叙事主题聚类
- 解释价格行为、量价结构与技术信号
- 识别财报日、宏观事件日程或催化剂时点
- 生成交易指令

说明：

- 本文中的 `normalized_composite_score` 是聚合器内部唯一规范分数
- 若外层兼容字段仍使用 `composite_score`，其值必须与 `normalized_composite_score` 完全相等
- `sentiment_bias` 只表示情绪与预期方向，不代表可执行买卖建议

---

## 2. 输入依赖

### 2.1 上游输入

聚合器只读取三个子模块的结构化输出，不直接读取原始标题、摘要、社媒正文或数据库表。

### 2.2 最小输入契约

#### 新闻基调模块

| 字段 | 用途 | 是否为计分必需 |
|---|---|---|
| `metrics.news_score` | 参与聚合评分 | 是 |
| `metrics.news_tone` | 方向映射、风险提取 | 是 |
| `metrics.recency_weighted_tone` | 方向校验、风险提取 | 是 |
| `metrics.positive_headline_ratio_7d` | 风险提取、完整度计算 | 否 |
| `metrics.negative_headline_ratio_7d` | 风险提取、完整度计算 | 否 |
| `metrics.source_diversity_7d` | 低置信度判定 | 是 |
| `metrics.headline_relevance_coverage` | 低置信度判定 | 是 |
| `missing_fields` | 缺失字段记录 | 是 |
| `staleness_days` | 新鲜度检查 | 是 |

#### 预期变化模块

| 字段 | 用途 | 是否为计分必需 |
|---|---|---|
| `metrics.expectation_score` | 参与聚合评分 | 是 |
| `metrics.expectation_shift` | 方向映射、`market_expectation` 生成 | 是 |
| `metrics.analyst_action_balance_30d` | 风险提取、完整度计算 | 是 |
| `metrics.target_revision_median_pct_30d` | 风险提取、完整度计算 | 是 |
| `metrics.expectation_headline_balance_14d` | 风险提取、完整度计算 | 是 |
| `metrics.valid_action_count_30d` + `metrics.positive_proxy_count_14d` + `metrics.negative_proxy_count_14d` | 样本量检查 | 否 |
| `metrics.estimate_attention_level` | `market_expectation` 修饰、低置信度判定 | 否 |
| `missing_fields` | 缺失字段记录 | 是 |
| `staleness_days` | 新鲜度检查 | 是 |

#### 叙事与拥挤度模块

| 字段 | 用途 | 是否为计分必需 |
|---|---|---|
| `narrative_score` | 参与聚合评分 | 是 |
| `narrative_state` | 方向映射、`market_expectation` 生成 | 是 |
| `dominant_bullish_theme_share` | 风险提取、完整度计算 | 是 |
| `dominant_bearish_theme_share` | 风险提取、完整度计算 | 是 |
| `contradiction_ratio` | 风险提取、低置信度判定 | 是 |
| `attention_zscore_7d` | 风险提取 | 是 |
| `crowding_flag` | 风险提取、`market_expectation` 修饰 | 是 |
| `source_diversity_7d` | 样本覆盖检查 | 否 |
| `dominant_bullish_narratives` | 可追溯性 | 否 |
| `dominant_bearish_narratives` | 可追溯性 | 否 |
| `missing_fields` | 缺失字段记录 | 是 |
| `staleness_days` | 新鲜度检查 | 是 |

### 2.3 模块可用性定义

聚合器对每个子模块只判定三种状态：

- `usable`：计分必需字段完整，且新鲜度在可接受范围内
- `degraded`：计分必需字段完整，但存在非计分关键字段缺失、关键覆盖率不足或数据偏旧
- `excluded`：计分必需字段缺失、分数字段非法，或数据过旧，不参与分数计算

---

## 3. 子模块到方向子信号的映射

聚合器不会直接拿 `news_score`、`expectation_score`、`narrative_score` 的高低当作方向，而是先把每个子模块映射为方向性子信号，再用分数完成强弱排序。

### 3.1 新闻子信号

`news_direction_signal` 只能取：

- `bullish`
- `neutral`
- `bearish`

映射规则如下：

| 条件 | `news_direction_signal` |
|---|---|
| `news_tone = positive` 且 `recency_weighted_tone >= 0.20` | `bullish` |
| `news_tone = negative` 且 `recency_weighted_tone <= -0.20` | `bearish` |
| 其他情况 | `neutral` |

补充规则：

- 若 `source_diversity_7d < 3`，方向映射不改写，但必须把新闻模块记入 `low_confidence_modules`
- 若 `headline_relevance_coverage < 0.50`，新闻模块最多只能作为 `degraded`

### 3.2 预期子信号

`expectation_direction_signal` 只能取：

- `bullish`
- `neutral`
- `bearish`

映射规则如下：

| 条件 | `expectation_direction_signal` |
|---|---|
| `expectation_shift = Improving` | `bullish` |
| `expectation_shift = Deteriorating` | `bearish` |
| `expectation_shift = Stable` | `neutral` |

补充规则：

- 若 `target_revision_median_pct_30d < 0`，即使 `expectation_score >= 60`，也不得输出 `bullish`
- 若 `analyst_action_balance_30d <= -0.20` 或 `expectation_headline_balance_14d <= -0.20`，方向必须至少为 `bearish` 或 `neutral`，不得输出 `bullish`

### 3.3 叙事子信号

`narrative_direction_signal` 只能取：

- `bullish`
- `neutral`
- `bearish`

映射规则如下：

| 条件 | `narrative_direction_signal` |
|---|---|
| `narrative_state = Supportive` | `bullish` |
| `narrative_state = Fragile` | `bearish` |
| `narrative_state = Mixed` | `neutral` |

补充规则：

- `crowding_flag = true` 不会单独把方向改成 `bearish`，但会降低最终结论的可执行置信度，并进入 `key_risks`
- 若 `contradiction_ratio >= 0.45`，即使 `dominant_bullish_theme_share` 较高，叙事方向也不得高于 `neutral`

### 3.4 方向子信号值映射

为了统一聚合器内部表达，三个方向子信号均按以下数值映射：

- `bullish = +1`
- `neutral = 0`
- `bearish = -1`

该数值只用于方向一致性检查和摘要解释，不直接替代 `normalized_composite_score`。

---

## 4. 固定权重与归一化

### 4.1 配置权重

为与 `sentimental_analysis_agent/overview.md` 保持一致，聚合器固定使用以下配置权重：

- `news`：`0.40`
- `expectation`：`0.35`
- `narrative`：`0.25`

### 4.2 设计原则

- `news` 权重最高，因为短周期情绪最先体现在标题基调与信息流方向
- `expectation` 次高，因为分析师动作与预期修正比新闻基调更贴近未来 1-4 周门槛变化
- `narrative` 权重最低，因为叙事更适合作为确认与风险修饰，不应单独主导方向

### 4.3 `weight_scheme_used`

聚合器必须输出实际使用的权重方案，字段固定如下：

```text
weight_scheme_used = {
  configured_weights: {
    news: 0.40,
    expectation: 0.35,
    narrative: 0.25
  },
  available_weight_sum: number,
  applied_weights: {
    news?: number,
    expectation?: number,
    narrative?: number
  },
  renormalized: boolean
}
```

规则：

- 若三个模块都可用，`available_weight_sum = 1.00`
- 若存在 `excluded` 模块，`available_weight_sum` 等于可用模块配置权重之和
- `applied_weights` 必须是归一化后的最终权重，和为 `1.00`
- 只要有任一模块被排除，`renormalized = true`

### 4.4 `normalized_composite_score`

规范公式如下：

```text
normalized_composite_score =
  sum(available_module_score × normalized_module_weight)
```

其中：

```text
normalized_module_weight =
  configured_module_weight / available_weight_sum
```

只有 `usable` 或 `degraded` 模块可以进入归一化分数；`excluded` 模块权重视为 `0`。

### 4.5 模块排除与降级阈值

以下情况之一成立时，模块必须记为 `excluded`，且不参与 `normalized_composite_score`：

- 计分必需字段缺失
- 分数字段不存在或不在 `0-100` 范围内
- 模块输出整体缺失
- `staleness_days` 超过排除阈值

以下情况之一成立时，模块记为 `degraded`，仍参与打分，但必须写入 `low_confidence_modules`：

- 非计分关键字段缺失
- `missing_fields` 非空
- `staleness_days` 超过降级阈值但未超过排除阈值
- 关键覆盖率低于最低门槛但未低到排除

阈值固定如下：

| 模块 | 降级阈值 | 排除阈值 | 最低覆盖门槛 |
|---|---|---|---|
| `news` | `staleness_days > 3` | `staleness_days > 7` | `metrics.headline_relevance_coverage < 0.50` 记 `degraded`，`< 0.30` 记 `excluded` |
| `expectation` | `staleness_days > 10` | `staleness_days > 21` | `metrics.valid_action_count_30d + metrics.positive_proxy_count_14d + metrics.negative_proxy_count_14d < 3` 记 `degraded` |
| `narrative` | `staleness_days > 5` | `staleness_days > 10` | `source_diversity_7d < 3` 记 `degraded`，`attention_zscore_7d` 缺失记 `excluded` |

### 4.6 为什么 `available_weight_sum < 0.70` 只能输出 `Neutral`

`0.70` 是硬约束，不是建议值。

原因如下：

- 任意单模块都不足以独立代表市场情绪全貌
- 仅 `news + narrative` 的最大权重为 `0.65`，缺少预期变化时不足以支撑方向性结论
- 仅 `expectation + narrative` 的最大权重为 `0.60`
- 因此，`available_weight_sum >= 0.70` 实际上要求至少保留 `news` 或 `expectation` 中的一个核心模块，并且不能只靠单一维度推导方向

结论：

- 当 `available_weight_sum < 0.70` 时，允许输出分数，但 `sentiment_bias` 必须压制为 `Neutral`

---

## 5. 低置信度约束与 `sentiment_bias`

### 5.1 `low_confidence_modules` 写入规则

`low_confidence_modules` 与 `low_confidence_details` 必须同时写出所有 `degraded` 或 `excluded` 模块：

- `low_confidence_modules`：overview 兼容摘要字段，只保留模块名数组
- `low_confidence_details`：详细结构字段，保留状态、原因和是否参与计分

详细结构固定如下：

```text
low_confidence_modules = ["news" | "expectation" | "narrative"]

low_confidence_details = [
  {
    module: "news" | "expectation" | "narrative",
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
- `insufficient_source_diversity`
- `insufficient_relevance_coverage`
- `insufficient_sample_size`

### 5.2 `sentiment_bias` 判定顺序

`sentiment_bias` 只能取以下三个值：

- `Bullish`
- `Neutral`
- `Bearish`

严格判定顺序如下：

1. 若 `available_weight_sum = 0`，输出 `Neutral`
2. 若 `available_weight_sum < 0.70`，输出 `Neutral`
3. 若 `data_completeness_pct < 60`，输出 `Neutral`
4. 若 `normalized_composite_score >= 65`，输出 `Bullish`
5. 若 `normalized_composite_score < 40`，输出 `Bearish`
6. 其余情况输出 `Neutral`

区间定义固定为：

- `Bullish`：`[65, 100]`
- `Neutral`：`[40, 65)`
- `Bearish`：`[0, 40)`

### 5.3 方向与分数组合约束

为避免分数和方向解释冲突，聚合器必须额外执行以下约束：

- 若 `sentiment_bias = Bullish`，则三个方向子信号中至少有一个为 `bullish`，且不得出现两个 `bearish`
- 若 `sentiment_bias = Bearish`，则三个方向子信号中至少有一个为 `bearish`，且不得出现两个 `bullish`
- 若方向子信号呈完全对冲状态（即同时存在 `bullish` 与 `bearish`，且三者中无方向占多数），`sentiment_bias` 必须压制为 `Neutral`

这条规则的目的是确保聚合结论不仅是数值结果，也具备方向解释上的可追溯性。

---

## 6. `market_expectation` 生成规则

### 6.1 生成目标

`market_expectation` 是一段固定模板驱动的解释文本，用于总结未来 1-4 周公开预期的方向状态。它必须：

- 只基于结构化字段生成
- 与 `expectation_shift`、`narrative_state`、`sentiment_bias` 保持一致
- 在同一输入与同一版本规则下产生完全相同的文本

### 6.2 主模板判定顺序

判定顺序固定如下：

1. 若 `expectation_shift = Deteriorating`
   - `market_expectation = "市场预期正在下修，负面信息更容易被放大。"`
2. 否则若 `expectation_shift = Improving` 且 `narrative_state = Supportive`
   - `market_expectation = "市场对未来 1-4 周预期正在改善，正向叙事占优。"`
3. 否则若 `expectation_shift = Improving` 且 `narrative_state = Mixed`
   - `market_expectation = "市场预期边际改善，但叙事尚未形成单边共识。"`
4. 否则若 `expectation_shift = Stable` 且 `narrative_state = Mixed`
   - `market_expectation = "市场预期未形成单边共识，当前更接近分歧整理。"`
5. 否则若 `expectation_shift = Stable` 且 `narrative_state = Supportive`
   - `market_expectation = "市场预期整体稳定，当前叙事对短期表现仍有支撑。"`
6. 否则若 `expectation_shift = Stable` 且 `narrative_state = Fragile`
   - `market_expectation = "市场预期尚未明显下修，但叙事结构偏脆弱。"`
7. 其他情况
   - `market_expectation = "市场预期信号有限，当前缺乏清晰的单边判断。"`

### 6.3 追加修饰句规则

在主模板生成后，按以下顺序追加修饰句：

1. 若 `crowding_flag = true` 且 `sentiment_bias = Bullish`
   - 追加：`"但注意情绪已出现拥挤迹象。"`
2. 若 `crowding_flag = true` 且 `sentiment_bias != Bullish`
   - 追加：`"当前注意力已明显升温，情绪反身性风险上升。"`
3. 若 `estimate_attention_level = Low`
   - 追加：`"相关预期证据覆盖有限。"`

追加规则：

- 最多追加 `2` 句
- 修饰句顺序固定，先拥挤，后覆盖不足
- 追加后总文本不得与基础结论发生方向冲突

---

## 7. `key_risks` 提取规则

### 7.1 提取目标

`key_risks` 与 `key_risk_details` 用于输出最值得下游关注的情绪与预期风险，不是所有负面字段的堆叠列表。

约束如下：

- 最多输出 `5` 条
- 必须使用固定模板生成
- 必须带来源模块与规则编号
- 必须按优先级降序输出
- `key_risks` 只保留风险标签字符串，供 overview 摘要消费
- `key_risk_details` 保留完整结构，供实现与调试消费

### 7.2 风险提取优先级与去重规则表

| 优先级 | 规则编号 | 来源字段 | 触发条件 | 输出模板 | 去重键 |
|---|---|---|---|---|---|
| `100` | `SR1` | `news.metrics.news_tone` + `narrative.attention_zscore_7d` | `news_tone = negative` 且 `attention_zscore_7d >= 2.0` | `负面舆情正在被异常放大` | `sentiment:negative_attention_spike` |
| `95` | `SR2` | `expectation.metrics.expectation_shift` | `expectation_shift = Deteriorating` | `短期市场预期正在下修` | `expectation:deteriorating` |
| `90` | `SR3` | `narrative.crowding_flag` + `sentiment_bias` | `crowding_flag = true` | `情绪出现拥挤，存在反身性回撤风险` | `narrative:crowded` |
| `85` | `SR4` | `narrative.contradiction_ratio` | `contradiction_ratio >= 0.45` | `市场叙事分裂，单边共识不足` | `narrative:contradiction` |
| `80` | `SR5` | `news.metrics.recency_weighted_tone` | `recency_weighted_tone <= -0.35` | `近期新闻基调明显偏空` | `news:deep_negative_tone` |
| `75` | `SR6` | `expectation.metrics.target_revision_median_pct_30d` | `< 0` | `分析师目标价中位数出现下修` | `expectation:target_cut` |
| `70` | `SR7` | `expectation.metrics.analyst_action_balance_30d` | `<= -0.20` | `卖方动作偏空，升级不足以抵消降级` | `expectation:analyst_negative_balance` |
| `65` | `SR8` | `low_confidence_modules[]` | 存在 `excluded` 模块 | `关键情绪证据缺失，当前结论置信度受限` | `quality:excluded_module` |
| `60` | `SR9` | `low_confidence_modules[]` | 仅存在 `degraded` 模块 | `部分情绪证据覆盖不足，结论稳定性下降` | `quality:degraded_module` |

### 7.3 去重规则

去重顺序固定如下：

1. 先按 `去重键` 分组
2. 同组内保留**优先级最高**的一条
3. 若优先级相同，保留**最近时间戳**的一条
4. 若时间戳仍相同，按模块顺序保留：`expectation > narrative > news`

### 7.4 截断规则

去重完成后：

- 按 `优先级降序` 排序
- 只保留前 `5` 条
- 若无风险命中，输出空数组 `[]`

### 7.5 输出结构

```text
key_risks = [string]

key_risk_details = [
  {
    risk_key: string,
    risk_label: string,
    source_module: "news" | "expectation" | "narrative" | "aggregator",
    rule_id: string,
    priority: number
  }
]
```

---

## 8. `data_completeness_pct` 计算规则

### 8.1 计算口径

`data_completeness_pct` 采用：**关键字段覆盖率 × 模块配置权重** 的加权计算。

即：

- 先计算每个模块的关键字段覆盖率
- 再按模块固定权重加总
- 最终输出 `0-100` 的百分比

### 8.2 模块内关键字段权重

#### `news`

| 字段 | 模块内权重 |
|---|---|
| `news_score` | `0.30` |
| `news_tone` | `0.15` |
| `recency_weighted_tone` | `0.20` |
| `source_diversity_7d` | `0.15` |
| `headline_relevance_coverage` | `0.20` |

#### `expectation`

| 字段 | 模块内权重 |
|---|---|
| `expectation_score` | `0.30` |
| `expectation_shift` | `0.15` |
| `analyst_action_balance_30d` | `0.20` |
| `target_revision_median_pct_30d` | `0.20` |
| `expectation_headline_balance_14d` | `0.15` |

#### `narrative`

| 字段 | 模块内权重 |
|---|---|
| `narrative_score` | `0.30` |
| `narrative_state` | `0.15` |
| `dominant_bullish_theme_share` | `0.15` |
| `dominant_bearish_theme_share` | `0.15` |
| `contradiction_ratio` | `0.10` |
| `attention_zscore_7d` | `0.10` |
| `crowding_flag` | `0.05` |

### 8.3 字段计分规则

每个关键字段只能按以下规则计分：

- 字段存在，且模块未超过降级阈值：记满分
- 字段存在，但模块超过降级阈值且未超过排除阈值：记 `50%`
- 字段缺失、为空、或模块已被排除：记 `0`

### 8.4 计算公式

```text
module_completeness_score =
  sum(field_present_score × field_weight)

data_completeness_pct =
  100 × (
    news_module_completeness_score        × 0.40 +
    expectation_module_completeness_score × 0.35 +
    narrative_module_completeness_score   × 0.25
  )
```

### 8.5 使用规则

- `data_completeness_pct >= 85`：高完整度
- `60 <= data_completeness_pct < 85`：允许方向判断，但可伴随低置信度提示
- `data_completeness_pct < 60`：`sentiment_bias` 只能输出 `Neutral`

---

## 9. 异常与降级策略

### 9.1 异常类型

| 异常类型 | 检测方式 | 处理 |
|---|---|---|
| 模块超时 | 子模块未在规定时间内返回结果 | 记为 `excluded`，`reason_codes` 写入 `missing_module_output` |
| 字段缺失 | 计分必需字段缺失或为 `null` | 记为 `excluded`，不参与分数 |
| 字段越界 | 分数字段不在 `0-100`、比例不在 `[0, 1]`、`attention_zscore_7d` 非数值 | 该字段视为缺失；若为计分必需字段则模块 `excluded` |
| 数据陈旧 | 超过模块排除阈值 | 记为 `excluded` |
| 覆盖不足 | 来源数、相关性覆盖或样本量低于最低门槛 | 记为 `degraded` 或 `excluded` |

### 9.2 最低可用模块数量

聚合器至少需要**两个模块**的有效输出，且 `available_weight_sum >= 0.70`，才能产生非中性的方向结论。

降级行为矩阵如下：

| 可用状态 | 行为 |
|---|---|
| `3 usable/degraded` | 正常执行全部逻辑 |
| `2 usable/degraded` 且 `available_weight_sum >= 0.70` | 允许生成方向结论，但必须输出 `renormalized = true` |
| `2 usable/degraded` 且 `available_weight_sum < 0.70` | 允许生成分数，但 `sentiment_bias` 强制为 `Neutral` |
| `1` 个或更少可用模块 | `normalized_composite_score = null`，`sentiment_bias = Neutral`，`market_expectation = "市场预期信号有限，当前缺乏清晰的单边判断。"` |

### 9.3 伪代码

```text
configured_weights = {
  news: 0.40,
  expectation: 0.35,
  narrative: 0.25
}

module_state = assess_module_state(inputs)
available_modules = filter(module_state in ["usable", "degraded"])
available_weight_sum = sum(configured_weights[module] for module in available_modules)

if count(available_modules) <= 1:
    normalized_composite_score = null
else if available_weight_sum > 0:
    normalized_weights[module] = configured_weights[module] / available_weight_sum
    normalized_composite_score =
      sum(score[module] * normalized_weights[module] for module in available_modules)
else:
    normalized_composite_score = null

data_completeness_pct = calc_data_completeness(inputs, module_state)
low_confidence_modules = collect_low_confidence(module_state)

if normalized_composite_score is null:
    sentiment_bias = "Neutral"
else if available_weight_sum < 0.70 or data_completeness_pct < 60:
    sentiment_bias = "Neutral"
else if normalized_composite_score >= 65:
    sentiment_bias = "Bullish"
else if normalized_composite_score < 40:
    sentiment_bias = "Bearish"
else:
    sentiment_bias = "Neutral"
```

### 9.4 可追溯性要求

聚合器输出必须能够回溯到：

- 子模块名称
- 子模块版本或规则版本
- 关键来源的时间戳
- 触发的规则编号
- 被排除或降级的原因码

实现要求如下：

- 每条 `key_risks` 必须带 `rule_id`
- 每条 `low_confidence_modules` 必须带 `reason_codes`
- `market_expectation` 只能使用固定模板，不得引入未在结构化字段中出现的新事实

---

## 10. 输出 Schema

API 对齐说明：

- 本节 Schema 定义的是情绪聚合器内部输出
- 它是公共 `sentiment_expectations` 对象的上游来源，但不等同于最终 HTTP 响应
- 最终对外契约见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

```json
{
  "composite_score": "number | null",
  "normalized_composite_score": "number | null",
  "sentiment_bias": "Bullish | Neutral | Bearish",
  "news_tone": "positive | neutral | negative",
  "market_expectation": "string",
  "weight_scheme_used": {
    "configured_weights": {
      "news": "number",
      "expectation": "number",
      "narrative": "number"
    },
    "available_weight_sum": "number",
    "applied_weights": {
      "news": "number",
      "expectation": "number",
      "narrative": "number"
    },
    "renormalized": "boolean"
  },
  "low_confidence_modules": ["string"],
  "low_confidence_details": [
    {
      "module": "news | expectation | narrative",
      "status": "degraded | excluded",
      "reason_codes": ["string"],
      "excluded_from_score": "boolean"
    }
  ],
  "data_completeness_pct": "number",
  "direction_signals": {
    "news_direction_signal": "bullish | neutral | bearish",
    "expectation_direction_signal": "bullish | neutral | bearish",
    "narrative_direction_signal": "bullish | neutral | bearish"
  },
  "key_risks": ["string"],
  "key_risk_details": [
    {
      "risk_key": "string",
      "risk_label": "string",
      "source_module": "news | expectation | narrative | aggregator",
      "rule_id": "string",
      "priority": "number"
    }
  ]
}
```

字段约束：

- `composite_score` 与 `normalized_composite_score` 必须完全相等；保留两个字段是为了兼容 overview 与内部聚合口径
- `normalized_composite_score` 取值范围为 `0-100`；当可用模块不足时允许为 `null`
- `weight_scheme_used.applied_weights` 只包含参与计分的模块
- `low_confidence_modules` 为 overview 兼容摘要字段，仅保留模块名；详细原因写入 `low_confidence_details`
- `key_risks` 为 overview 兼容摘要字段，仅保留风险标签；详细结构写入 `key_risk_details`
- `direction_signals` 用于解释方向来源，不能替代子模块原始输出

---

## 11. 输出示例

```json
{
  "composite_score": 68.25,
  "normalized_composite_score": 68.25,
  "sentiment_bias": "Bullish",
  "news_tone": "positive",
  "market_expectation": "市场对未来 1-4 周预期正在改善，正向叙事占优。但注意情绪已出现拥挤迹象。",
  "weight_scheme_used": {
    "configured_weights": {
      "news": 0.4,
      "expectation": 0.35,
      "narrative": 0.25
    },
    "available_weight_sum": 1.0,
    "applied_weights": {
      "news": 0.4,
      "expectation": 0.35,
      "narrative": 0.25
    },
    "renormalized": false
  },
  "low_confidence_modules": [],
  "low_confidence_details": [],
  "data_completeness_pct": 92.5,
  "direction_signals": {
    "news_direction_signal": "bullish",
    "expectation_direction_signal": "bullish",
    "narrative_direction_signal": "neutral"
  },
  "key_risks": [
    "情绪出现拥挤，存在反身性回撤风险"
  ],
  "key_risk_details": [
    {
      "risk_key": "narrative:crowded",
      "risk_label": "情绪出现拥挤，存在反身性回撤风险",
      "source_module": "narrative",
      "rule_id": "SR3",
      "priority": 90
    }
  ]
}
```

示例说明：

- 新闻与预期模块共同把分数推高到 `65` 以上，因此 `sentiment_bias = Bullish`
- 叙事模块并未转为 `bearish`，但 `crowding_flag = true` 仍进入 `key_risks`
- 若此例中 `expectation` 模块被排除，则 `available_weight_sum = 0.65`，最终 `sentiment_bias` 必须压制为 `Neutral`
