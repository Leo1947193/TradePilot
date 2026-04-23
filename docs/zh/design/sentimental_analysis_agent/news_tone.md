# 新闻基调分析器

## 1. 模块目标与边界

### 1.1 模块目标

新闻基调分析器服务于 **7 到 30 天** 的短中期情绪窗口，目标是回答以下问题：

1. 最近公开新闻对该标的的整体基调偏多、偏空还是中性
2. 这种基调是由最近几天的新信息驱动，还是由较旧新闻残留造成
3. 当前结论是否建立在足够的相关标题覆盖与独立来源支持之上

模块输出必须满足以下要求：

- 仅输出 **结构化、确定性、可追溯** 的结果
- 同一份输入在同一规则版本下必须产生同一输出
- 不输出买卖指令，只输出可供上层聚合的新闻情绪信号

### 1.2 范围内

- 最近 7 / 30 天公司相关新闻标题与可选摘要的方向性判断
- 标题级去重、相关性过滤、时效加权
- `news_tone`、`recency_weighted_tone` 与 `news_score` 生成
- 为上层聚合器提供可追溯的证据标题列表

### 1.3 范围外

- 财报一致预期修正、分析师升级 / 降级、目标价变化
- 社媒讨论热度、叙事拥挤度、注意力异常
- 价格行为、成交量、突破 / 破位等技术信号
- 宏观日历、事件发生时间表与催化剂强度判断

说明：

- 分析师动作与公开预期变化归属 **预期变化分析器**
- 提及量、主导叙事与拥挤度归属 **叙事与拥挤度分析器**
- 价格行为与量价结构归属 **技术分析模块**

---

## 2. 输入定义

### 2.1 基础上下文

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ticker` | `string` | 是 | 股票代码 |
| `company_name` | `string` | 是 | 公司标准名称 |
| `company_aliases` | `string[]` | 否 | 常见简称、品牌名、英文别名 |
| `analysis_timestamp` | `ISO 8601` | 是 | 本次分析执行时间 |
| `analysis_window_days` | `number[2]` | 是 | 固定为 `[7, 30]` |
| `primary_market` | `string` | 否 | 上市市场，用于过滤跨市场同名噪声 |
| `sector` | `string` | 否 | 行业上下文，仅用于辅助相关性判断 |

### 2.2 新闻输入 `news_items[]`

仅消费标题级新闻记录；摘要为可选增强字段。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `headline` | `string` | 是 | 新闻标题原文 |
| `summary` | `string | null` | 否 | 新闻摘要或首段摘要 |
| `published_at` | `ISO 8601` | 是 | 标题发布时间 |
| `source_name` | `string` | 是 | 来源名称 |
| `source_type` | `news \| wire \| analyst \| social` | 是 | 来源类型 |
| `url` | `string` | 是 | 原始链接；若无公开 URL，必须提供唯一来源标识 |
| `language` | `string` | 是 | 标题语言 |
| `relevance_score` | `number` | 是 | 上游相关性分数，范围 `[0, 1]` |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |
| `source` | `string` | 是 | 数据集名称或数据供应商 |
| `classifier_version` | `string | null` | 否 | 若使用分类器生成事件标签，必须记录版本 |

### 2.3 时间窗口

- **主窗口：** 最近 `7` 天，用于 `positive_headline_ratio_7d`、`negative_headline_ratio_7d` 与 `source_diversity_7d`
- **确认窗口：** 最近 `30` 天，用于 `recency_weighted_tone` 与 `headline_relevance_coverage`
- `published_at < analysis_timestamp - 30 days` 的标题一律不参与计算
- 若标题发布时间晚于 `analysis_timestamp`，视为无效数据并剔除

### 2.4 数据来源与可追溯要求

- 每条记录必须保留 `headline`、`published_at`、`source_name`、`url`、`relevance_score`
- `summary` 缺失允许存在，但不得由模型补写
- 若使用分类器判断标题事件类型，必须记录 `classifier_version`
- 输出证据标题时，必须能回溯到原始 `url` 与去重后的 `dedupe_cluster_id`

---

## 3. 数据预处理规则

### 3.1 标题标准化

对每条原始标题先生成 `normalized_headline`，规则固定如下：

1. 去除首尾空格，并将连续空格折叠为单个空格
2. 英文统一转小写；中文保留原文，不做同义词替换
3. 去除标题首尾标点，但保留中间数字、百分号、货币符号
4. 将 `ticker`、公司全名、常见别名中的大小写差异统一为标准形式，仅用于匹配，不回写原文
5. 不允许在标准化阶段删除“获批 / 下调 / 调查 / 裁员”等方向性词汇

### 3.2 标题级去重

新闻基调只允许按 **独立事件标题** 计数，不允许同一条通稿或转载在多个站点重复加权。

两条标题归为同一 `dedupe_cluster`，当且仅当同时满足以下条件：

1. `ticker` 或 `company_name / company_aliases` 匹配同一主体
2. `published_at` 时间差 `<= 48` 小时
3. 满足以下任一相似条件：
   - `normalized_headline` 完全相同
   - 标题分词后的 Jaccard 相似度 `>= 0.85`，且数字 token 完全一致

去重后保留 **canonical headline**，优先级固定如下：

1. `relevance_score` 更高者优先
2. `source_type = wire` 优先于 `news`
3. `published_at` 更早者优先
4. `url` 字典序更小者优先

对外要求：

- 同一 `dedupe_cluster` 只计入一次情绪分值
- 需保留 `duplicate_count`、`duplicate_urls[]`
- `source_diversity_7d` 仅基于去重后的 canonical headlines 统计

### 3.3 相关性过滤

只允许保留与公司本身存在直接关系的标题。

#### 3.3.1 硬性保留条件

满足以下任一条件的标题可进入候选集：

- `relevance_score >= 0.70`
- `0.50 <= relevance_score < 0.70`，且标题中出现 `ticker`、`company_name` 或任一 `company_aliases`

#### 3.3.2 硬性剔除条件

满足以下任一条件即剔除：

- `relevance_score < 0.50`
- `source_type = social` 或 `source_type = analyst`
- 标题只描述股价涨跌、盘前盘后波动、板块带动，而未给出公司特定事件
- 标题主体是行业、ETF、指数、宏观数据，目标公司只作为列举样本之一
- `language` 不在 `zh`、`en` 支持范围内

#### 3.3.3 相关性覆盖率

```text
headline_relevance_coverage =
  relevant_unique_headline_count_30d
  / max(raw_headline_count_30d, 1)
```

说明：

- 分母使用 30 天原始标题总数
- 分子使用去重且通过过滤后的有效标题数
- 结果保留 2 位小数

### 3.4 有效标题判定

满足以下条件的标题才可参与情绪判断：

- `headline` 非空
- `published_at`、`source_name`、`url`、`relevance_score` 存在
- 通过第 3.2 节去重与第 3.3 节相关性过滤
- `published_at <= analysis_timestamp`
- `published_at >= analysis_timestamp - 30 days`

### 3.5 内部辅助字段

以下字段用于规则判断，不要求全部进入对外 schema：

```text
headline_age_days(i) =
  max(0, analysis_timestamp - published_at(i)) 以自然日计

sentiment_value(i) =
  1  (positive)
  0  (neutral)
 -1  (negative)

recent_weight_share =
  sum(7 天内标题的 recency_weight)
  / max(sum(30 天内标题的 recency_weight), 0.01)
```

---

## 4. 情绪标签口径与核心指标

### 4.1 标题事件类型与情绪映射

标题情绪不允许直接由自由文本生成，必须先映射到固定事件类型，再映射为情绪标签。

| `headline_event_type` | `headline_sentiment_label` | `sentiment_value` | 口径说明 |
|---|---|---|---|
| `beat_or_raise` | `positive` | `1` | 财报超预期、指引上修、订单 / 需求显著改善 |
| `approval_or_contract_win` | `positive` | `1` | 获批、赢得大单、重大合作落地、重大诉讼利空解除 |
| `capital_return_or_balance_sheet_relief` | `positive` | `1` | 回购、分红、再融资风险缓解、债务压力明显下降 |
| `miss_or_cut` | `negative` | `-1` | 财报不及预期、指引下修、需求转弱、利润受压 |
| `legal_or_regulatory_hit` | `negative` | `-1` | 调查、起诉、罚款、禁售、召回、审批受阻 |
| `financing_or_liquidity_stress` | `negative` | `-1` | 流动性压力、再融资被动、违约风险、裁员纾困 |
| `management_or_governance_issue` | `negative` | `-1` | 高管离任、治理争议、审计问题、内部控制缺陷 |
| `factual_update` | `neutral` | `0` | 产品发布、会议安排、经营动态，但缺乏明确方向性 |
| `price_action_or_macro_recap` | `neutral` | `0` | 盘中异动、市场回顾、板块联动、宽泛宏观叙事 |
| `mixed_or_unclear` | `neutral` | `0` | 标题同时包含正负面，或方向不明确 |

附加规则：

1. 若同一标题同时出现明显正负面事件，以 **对 1 到 6 周预期影响更直接的一侧** 为准；若无法确定，归入 `mixed_or_unclear`
2. 不允许使用“模型感觉偏多 / 偏空”作为标签依据
3. 若 `summary` 缺失，只允许基于 `headline` 做分类，并在输出中标记 `used_headline_only_classification = true`

### 4.2 时效加权规则

每条有效标题的时效权重 `recency_weight(i)` 固定如下：

| `headline_age_days` | `recency_weight` |
|---|---|
| `0-1` 天 | `1.00` |
| `2-3` 天 | `0.85` |
| `4-7` 天 | `0.65` |
| `8-14` 天 | `0.40` |
| `15-30` 天 | `0.20` |
| `> 30` 天 | `0.00` |

说明：

- 权重只由发布时间决定，不允许由模型自由调整
- 同一 `dedupe_cluster` 内所有转载只继承 canonical headline 的单个权重

### 4.3 核心指标定义

#### 4.3.1 `positive_headline_ratio_7d`

```text
positive_headline_ratio_7d =
  positive_unique_headline_count_7d
  / max(valid_unique_headline_count_7d, 1)
```

#### 4.3.2 `negative_headline_ratio_7d`

```text
negative_headline_ratio_7d =
  negative_unique_headline_count_7d
  / max(valid_unique_headline_count_7d, 1)
```

#### 4.3.3 `recency_weighted_tone`

```text
recency_weighted_tone =
  sum(sentiment_value(i) * recency_weight(i))
  / max(sum(recency_weight(i)), 0.01)
```

规则：

- 仅使用最近 30 天去重后的有效标题
- 取值范围固定为 `[-1.00, 1.00]`
- 输出保留 2 位小数

#### 4.3.4 `source_diversity_7d`

定义：最近 7 天去重后有效标题中，不同 `source_name` 的数量。

规则：

- 同一 `dedupe_cluster` 的转载不重复计数
- 结果为整数，最小值 `0`

---

## 5. 标签生成规则

### 5.1 `news_tone` 标签表

`news_tone` 输出枚举：`positive | neutral | negative`

| 优先级 | 条件 | 输出标签 |
|---|---|---|
| 1 | `valid_unique_headline_count_7d < 3` | `neutral` |
| 2 | `source_diversity_7d < 2` | `neutral` |
| 3 | `recency_weighted_tone <= -0.20` 且 `negative_headline_ratio_7d >= positive_headline_ratio_7d + 0.15` | `negative` |
| 4 | `recency_weighted_tone >= 0.20` 且 `positive_headline_ratio_7d >= negative_headline_ratio_7d + 0.15` | `positive` |
| 5 | 其余情况 | `neutral` |

说明：

- 标签判定按优先级顺序执行，命中后立即停止
- 样本不足时，强制回退为 `neutral`
- `negative` 优先级高于 `positive`，避免在明显利空与轻微利多并存时误判

---

## 6. 评分规则

`news_score` 只表示 **新闻基调强度与可用性**，不表示方向；偏多和偏空都可能得到高分。

### 6.1 `tone_balance_score` 映射

由两个部分组成：

```text
tone_balance_score =
  weighted_tone_strength   (0-25) +
  headline_dominance_score (0-20)
```

`weighted_tone_strength`：

| `abs(recency_weighted_tone)` | 分值 |
|---|---|
| `>= 0.60` | `25` |
| `[0.40, 0.60)` | `20` |
| `[0.25, 0.40)` | `15` |
| `[0.10, 0.25)` | `8` |
| `< 0.10` | `0` |

`headline_dominance_score`：

```text
headline_ratio_gap =
  abs(positive_headline_ratio_7d - negative_headline_ratio_7d)
```

| `headline_ratio_gap` | 分值 |
|---|---|
| `>= 0.50` | `20` |
| `[0.30, 0.50)` | `15` |
| `[0.15, 0.30)` | `10` |
| `[0.05, 0.15)` | `5` |
| `< 0.05` | `0` |

### 6.2 `recency_score` 映射

```text
recent_weight_share =
  sum(7 天内标题的 recency_weight)
  / max(sum(30 天内标题的 recency_weight), 0.01)
```

| `recent_weight_share` | 分值 |
|---|---|
| `>= 0.75` | `25` |
| `[0.60, 0.75)` | `20` |
| `[0.45, 0.60)` | `15` |
| `[0.30, 0.45)` | `8` |
| `< 0.30` | `0` |

### 6.3 `source_diversity_score` 映射

| `source_diversity_7d` | 分值 |
|---|---|
| `>= 8` | `15` |
| `[5, 8)` | `12` |
| `[3, 5)` | `8` |
| `2` | `4` |
| `< 2` | `0` |

### 6.4 `relevance_coverage_score` 映射

| `headline_relevance_coverage` | 分值 |
|---|---|
| `>= 0.75` | `15` |
| `[0.60, 0.75)` | `12` |
| `[0.45, 0.60)` | `8` |
| `[0.30, 0.45)` | `4` |
| `< 0.30` | `0` |

### 6.5 完整数据下的总分计算

当 4 个子分项都可计算时：

```text
news_score =
  tone_balance_score +
  recency_score +
  source_diversity_score +
  relevance_coverage_score
```

输出要求：

- `news_score` 四舍五入为整数
- 结果限制在 `[0, 100]`

---

## 7. 缺失数据与过期数据处理

### 7.1 关键字段定义

以下字段组属于 **关键字段**：

| 关键字段组 | 字段 |
|---|---|
| `news_identity_core` | `headline`、`source_name`、`url` |
| `news_timestamp_core` | `published_at`、`analysis_timestamp` |
| `news_relevance_core` | `relevance_score` |
| `news_classification_core` | `classifier_version` 或可验证的规则版本 |

### 7.2 过期阈值

| 数据类型 | 新鲜 | 警告 | 过期 |
|---|---|---|---|
| 新闻数据集抓取时间 `fetched_at` | `<= 1` 天 | `2-3` 天 | `> 3` 天 |
| 标题发布时间相对分析时点 | `<= 7` 天 | `8-30` 天 | `> 30` 天 |

说明：

- 数据集过期表示抓取快照过旧
- 标题过期表示超出分析窗口，不是数据错误

### 7.3 降级规则

#### 7.3.1 标题样本不足

- `valid_unique_headline_count_30d = 0`：
  - `news_tone = neutral`
  - `news_score = 50`
  - `confidence_level = Low`
- `valid_unique_headline_count_7d < 3`：
  - `news_tone` 不得输出 `positive` 或 `negative`
  - `tone_balance_score` 仍可计算，但需标记 `insufficient_recent_coverage = true`

#### 7.3.2 关键字段缺失

- 缺 `headline`、`published_at`、`source_name`、`url`、`relevance_score` 中任一项：
  - 该标题直接剔除
  - 对应字段组写入 `critical_missing_fields`
- `summary` 缺失：
  - 允许继续计算
  - 仅标记 `used_headline_only_classification = true`

#### 7.3.3 数据集过期

- `fetched_at` 处于警告区间：
  - `confidence_score` 扣减 `0.10`
- `fetched_at` 过期：
  - `news_tone` 不得输出 `positive` 或 `negative`
  - `news_score` 上限强制为 `60`
  - `confidence_score` 额外扣减 `0.20`

#### 7.3.4 可计算分项不足

若存在分项不可计算，则使用以下规则：

```text
available_score_sum = sum(可计算子分项实际得分)
available_score_cap = sum(可计算子分项理论满分)
normalized_score = (available_score_sum / available_score_cap) * 100
```

然后应用固定缺失惩罚：

| 条件 | 扣分 |
|---|---|
| `tone_balance_score` unavailable | `20` |
| `recency_score` unavailable | `10` |
| `source_diversity_score` unavailable | `10` |
| `relevance_coverage_score` unavailable | `10` |

最终：

```text
news_score =
  clamp(round(normalized_score - missing_penalty), 0, 100)
```

若 `available_score_cap < 55`，则强制回退为：

- `news_tone = neutral`
- `news_score = 50`
- `confidence_level = Low`

### 7.4 置信度计算

初始值固定为 `1.00`，按下表扣减：

| 条件 | 扣减 |
|---|---|
| `valid_unique_headline_count_7d < 5` | `0.10` |
| `valid_unique_headline_count_7d < 3` | `0.15` |
| `source_diversity_7d < 3` | `0.10` |
| `headline_relevance_coverage < 0.45` | `0.10` |
| 数据集抓取时间处于警告区间 | `0.10` |
| 数据集抓取时间过期 | `0.20` |
| 仅能使用标题、无法使用摘要 | `0.05` |

最终：

```text
confidence_score = clamp(1.00 - total_deduction, 0.20, 1.00)
```

`confidence_level` 映射：

- `confidence_score >= 0.85` → `High`
- `0.65 <= confidence_score < 0.85` → `Medium`
- `confidence_score < 0.65` → `Low`

---

## 8. 输出 Schema

API 对齐说明：

- 本节 Schema 仅用于 `news_tone` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

```json
{
  "schema_version": "1.0",
  "ticker": "string",
  "analysis_timestamp": "ISO 8601",
  "module": "NewsToneAnalyzerV1",
  "staleness_days": "number",
  "missing_fields": ["string"],
  "metrics": {
    "valid_unique_headline_count_7d": "number",
    "valid_unique_headline_count_30d": "number",
    "positive_headline_ratio_7d": "number",
    "negative_headline_ratio_7d": "number",
    "recency_weighted_tone": "number",
    "source_diversity_7d": "number",
    "headline_relevance_coverage": "number",
    "news_tone": "positive | neutral | negative",
    "news_score": "number"
  },
  "subscores": {
    "tone_balance_score": "number | null",
    "recency_score": "number | null",
    "source_diversity_score": "number | null",
    "relevance_coverage_score": "number | null"
  },
  "confidence": {
    "confidence_score": "number",
    "confidence_level": "High | Medium | Low",
    "critical_missing_fields": ["string"],
    "stale_fields": ["string"]
  },
  "flags": {
    "insufficient_recent_coverage": "boolean",
    "used_headline_only_classification": "boolean",
    "used_normalized_scoring": "boolean"
  },
  "evidence": [
    {
      "headline": "string",
      "published_at": "ISO 8601",
      "source_name": "string",
      "url": "string",
      "dedupe_cluster_id": "string",
      "headline_event_type": "string",
      "headline_sentiment_label": "positive | neutral | negative",
      "sentiment_value": "number",
      "recency_weight": "number",
      "relevance_score": "number",
      "classifier_version": "string | null"
    }
  ],
  "source_trace": [
    {
      "dataset": "news_items",
      "source": "string",
      "fetched_at": "ISO 8601",
      "staleness_days": "number",
      "missing_fields": ["string"]
    }
  ]
}
```

约束：

- 对外输出中的比例与分数字段统一保留 2 位小数
- `news_score` 输出整数
- `evidence` 至少返回 3 条最高权重的 canonical headlines；若不足 3 条，则按实际返回

---

## 9. 实现约束与 JSON 输出示例

### 9.1 实现约束

1. 所有阈值必须硬编码在规则层，不允许由模型自由决定。
2. 先做去重和相关性过滤，再做标题分类，不允许把无关标题直接送入情绪计算。
3. 标题必须先映射到固定 `headline_event_type`，再映射到 `headline_sentiment_label`。
4. 不允许将转载数量直接当作情绪强度；同一 `dedupe_cluster` 只能计分一次。
5. 不允许使用股价涨跌新闻替代公司事件新闻，否则会与技术分析模块职责重叠。
6. 若数据不足，必须走第 7 节降级逻辑，不允许输出“模型认为偏多 / 偏空”。

### 9.2 JSON 输出示例

```json
{
  "schema_version": "1.0",
  "ticker": "AAPL",
  "analysis_timestamp": "2026-04-16T10:30:00Z",
  "module": "NewsToneAnalyzerV1",
  "staleness_days": 0,
  "missing_fields": [],
  "metrics": {
    "valid_unique_headline_count_7d": 6,
    "valid_unique_headline_count_30d": 14,
    "positive_headline_ratio_7d": 0.50,
    "negative_headline_ratio_7d": 0.17,
    "recency_weighted_tone": 0.28,
    "source_diversity_7d": 5,
    "headline_relevance_coverage": 0.70,
    "news_tone": "positive",
    "news_score": 71
  },
  "subscores": {
    "tone_balance_score": 25,
    "recency_score": 20,
    "source_diversity_score": 12,
    "relevance_coverage_score": 12
  },
  "confidence": {
    "confidence_score": 0.90,
    "confidence_level": "High",
    "critical_missing_fields": [],
    "stale_fields": []
  },
  "flags": {
    "insufficient_recent_coverage": false,
    "used_headline_only_classification": false,
    "used_normalized_scoring": false
  },
  "evidence": [
    {
      "headline": "Apple supplier orders point to stronger iPhone demand in China",
      "published_at": "2026-04-15T08:10:00Z",
      "source_name": "Reuters",
      "url": "https://example.com/apple-demand-china",
      "dedupe_cluster_id": "AAPL-20260415-01",
      "headline_event_type": "beat_or_raise",
      "headline_sentiment_label": "positive",
      "sentiment_value": 1,
      "recency_weight": 1.0,
      "relevance_score": 0.91,
      "classifier_version": "headline-event-v1.2"
    },
    {
      "headline": "Apple wins expanded enterprise device contract with major bank",
      "published_at": "2026-04-13T12:20:00Z",
      "source_name": "Bloomberg",
      "url": "https://example.com/apple-enterprise-contract",
      "dedupe_cluster_id": "AAPL-20260413-02",
      "headline_event_type": "approval_or_contract_win",
      "headline_sentiment_label": "positive",
      "sentiment_value": 1,
      "recency_weight": 0.85,
      "relevance_score": 0.88,
      "classifier_version": "headline-event-v1.2"
    },
    {
      "headline": "Apple faces fresh antitrust inquiry in one European market",
      "published_at": "2026-04-11T06:45:00Z",
      "source_name": "Financial Times",
      "url": "https://example.com/apple-antitrust-inquiry",
      "dedupe_cluster_id": "AAPL-20260411-01",
      "headline_event_type": "legal_or_regulatory_hit",
      "headline_sentiment_label": "negative",
      "sentiment_value": -1,
      "recency_weight": 0.65,
      "relevance_score": 0.84,
      "classifier_version": "headline-event-v1.2"
    }
  ],
  "source_trace": [
    {
      "dataset": "news_items",
      "source": "primary_news_feed",
      "fetched_at": "2026-04-16T10:20:00Z",
      "staleness_days": 0,
      "missing_fields": []
    }
  ]
}
```

该示例表示：

- 最近 7 天有效标题数量与来源分布足以支持方向判断
- 近端正面标题占比明显高于负面标题
- 30 天时效加权后整体基调偏正，但并非极端单边
- 输出结论可回溯到具体 canonical headlines、来源、时间与分类器版本
