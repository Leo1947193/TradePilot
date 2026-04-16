# 预期变化分析器

## 1. 模块职责与边界

### 1.1 模块职责

预期变化分析器服务于 **7 到 45 天** 的中短期交易窗口，目标是回答以下问题：

1. 卖方分析师公开动作整体是在抬升还是压低短期市场预期
2. 目标价修正是否体现出一致方向的预期门槛变化
3. 公开信息中与预期变化直接相关的新闻标签是在改善、恶化，还是分歧明显

模块输出必须满足以下要求：

- 仅输出 **结构化、确定性、可追溯** 的结果
- 同一份输入在同一规则版本下必须产生同一输出
- 不输出买卖指令，只输出可供上层聚合的 `expectation_shift` 信号

### 1.2 范围内

- 最近 30 / 60 天公开可见的分析师升级、降级、维持、首次覆盖动作
- 最近 30 天目标价上调 / 下调方向与中位数修正幅度
- 最近 14 天与预期变化直接相关的新闻代理标签
- 预期变化方向、覆盖度与置信度的结构化输出

### 1.3 范围外

- EPS / 营收一致预期数值建模与卖方模型修正统计
- 财报结果兑现、管理层量化指引、盈利 surprise 分析
- 价格走势、波动率、成交量、突破 / 破位信号
- 事件时间表、催化剂强度、事件胜率判断

说明：

- 一致预期数值修正归属 **基本面模块**
- 新闻基调归属 **情绪模块中的新闻基调分析器**
- 叙事拥挤度归属 **叙事与拥挤度分析器**
- 本模块只处理“市场短期预期是否在公开信息层面上修 / 下修”

---

## 2. 输入规格

### 2.1 基础上下文

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ticker` | `string` | 是 | 股票代码 |
| `analysis_timestamp` | `ISO 8601` | 是 | 本次分析执行时间 |
| `target_horizon_days` | `number[2]` | 是 | 固定为 `[7, 45]` |
| `sector` | `string` | 否 | 板块信息，用于解释首次覆盖动作 |
| `industry` | `string` | 否 | 行业信息 |

### 2.2 分析师动作输入 `analyst_actions[]`

仅使用最近 60 天记录，其中核心计算窗口为最近 30 天。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `action_id` | `string` | 否 | 来源侧唯一标识；若缺失，需由系统生成稳定去重键 |
| `published_at` | `ISO 8601` | 是 | 动作发布时间 |
| `analyst_firm` | `string` | 否 | 机构名称 |
| `analyst_name` | `string` | 否 | 分析师姓名 |
| `rating_action` | `upgrade | downgrade | reiterate | initiate` | 是 | 原始动作类型 |
| `rating_before` | `string | null` | 否 | 动作前评级 |
| `rating_after` | `string | null` | 否 | 动作后评级 |
| `target_price_old` | `number | null` | 否 | 调整前目标价 |
| `target_price_new` | `number | null` | 否 | 调整后目标价 |
| `currency` | `string | null` | 否 | 目标价币种 |
| `source_name` | `string` | 是 | 数据源名称 |
| `url` | `string` | 是 | 原始链接 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

### 2.3 预期代理标签输入 `expectation_proxy_events[]`

仅使用最近 14 天与市场预期变化直接相关的新闻或摘要标签。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | `string` | 否 | 来源侧唯一标识 |
| `published_at` | `ISO 8601` | 是 | 发布时间 |
| `headline` | `string` | 是 | 标题原文 |
| `summary` | `string | null` | 否 | 摘要或首段摘要 |
| `tag` | `guidance_raise | guidance_cut | demand_improving | demand_softening | margin_pressure | execution_improving` | 是 | 结构化代理标签 |
| `relevance_score` | `number` | 是 | `0-1`，低于阈值不参与计算 |
| `source_name` | `string` | 是 | 数据源名称 |
| `url` | `string` | 是 | 原始链接 |
| `classifier_version` | `string` | 是 | 标签抽取规则或模型版本 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

### 2.4 数据来源要求

- 每个输入数据集必须记录：`source`、`fetched_at`、`staleness_days`、`missing_fields`
- 每条分析师动作和代理标签记录都必须保留 `url` 或稳定唯一来源标识
- 若 `rating_action` 或 `tag` 由 LLM 归一化生成，必须记录 `classifier_version`
- 若关键字段缺失，不允许用自然语言推断预期方向，只能按第 7 节降级

---

## 3. 数据标准化与预处理

### 3.1 分析师动作去重

去重键优先级固定如下：

1. `action_id`
2. `ticker + analyst_firm + analyst_name + published_at(date) + rating_action`
3. `url`

若同一事件存在多条记录，保留顺序固定如下：

1. `rating_after` 与目标价字段更完整者优先
2. `published_at` 更精确者优先
3. `fetched_at` 更新者优先
4. 主数据源优先于备用源

### 3.2 评级方向标准化

内部仅保留以下动作归类：

- `positive_action`
  - `upgrade`
  - `initiate` 且 `rating_after` 属于 `Buy | Overweight | Outperform | Positive | Add`
- `negative_action`
  - `downgrade`
  - `initiate` 且 `rating_after` 属于 `Sell | Underweight | Underperform | Negative | Reduce`
- `neutral_action`
  - `reiterate`
  - `initiate` 且 `rating_after` 无法可靠映射为正向或负向

说明：

- `neutral_action` 计入 `total_actions`，但不贡献方向分子
- `reiterate` 不因目标价上调自动转为正向动作，评级方向与目标价修正分开计分
- 若 `rating_after` 缺失且 `rating_action = initiate`，该记录只计入 `total_actions`

### 3.3 目标价修正口径

仅对满足以下条件的记录计算目标价修正：

- `target_price_old` 与 `target_price_new` 同时存在
- `target_price_old > 0`
- `currency` 一致或可确认是同一币种
- `published_at` 位于最近 30 天窗口内

定义：

```text
target_revision_pct =
  ((target_price_new - target_price_old)
   / max(abs(target_price_old), 0.01)) * 100
```

预处理规则：

1. 百分比结果保留 2 位小数
2. 单条 `target_revision_pct` 裁剪到 `[-80.00, 200.00]`
3. 最近 30 天同一机构同一天多次修正时，仅保留最后一次
4. `target_revision_median_pct_30d` 使用所有有效记录的中位数
5. 若有效记录数 `< 2`，允许输出中位数，但必须降低置信度

### 3.4 预期代理标签规则

正向标签：

- `guidance_raise`
- `demand_improving`
- `execution_improving`

负向标签：

- `guidance_cut`
- `demand_softening`
- `margin_pressure`

有效记录要求：

- `relevance_score >= 0.60`
- `published_at` 位于最近 14 天窗口内
- `headline` 与 `url` 同时存在

若同一 `url` 被重复抓取，仅保留 `classifier_version` 最新且字段最完整的记录。

### 3.5 内部辅助指标

```text
analyst_action_balance_30d =
  (positive_action_count_30d - negative_action_count_30d)
  / max(valid_action_count_30d, 1)

expectation_headline_balance_14d =
  (positive_proxy_count_14d - negative_proxy_count_14d)
  / max(valid_proxy_count_14d, 1)
```

其中：

- `valid_action_count_30d = positive_action_count_30d + negative_action_count_30d + neutral_action_count_30d`
- `valid_proxy_count_14d = positive_proxy_count_14d + negative_proxy_count_14d`
- 两个 balance 指标范围固定为 `[-1.00, 1.00]`

---

## 4. 核心指标定义

### 4.1 `analyst_action_balance_30d`

定义见第 3.5 节，用于表达最近 30 天分析师公开动作的净方向。

解释规则：

- `1.00` 表示全部为正向动作
- `-1.00` 表示全部为负向动作
- `0.00` 表示方向平衡，或只有中性动作

### 4.2 `target_revision_median_pct_30d`

定义：最近 30 天所有有效 `target_revision_pct` 的中位数。

解释规则：

- `> 0` 表示目标价修正整体偏上调
- `< 0` 表示目标价修正整体偏下调
- `= 0` 表示整体未形成方向

说明：

- 该指标只表达公开 sell-side 姿态变化，不代表目标价本身是否合理
- 极端值由第 3.3 节裁剪规则处理，避免单一异常值污染中位数

### 4.3 `expectation_headline_balance_14d`

定义见第 3.5 节，用于表达最近 14 天预期代理标签的净方向。

解释规则：

- `>= 0.25` 代表正向预期代理信号明显占优
- `<= -0.25` 代表负向预期代理信号明显占优
- `(-0.25, 0.25)` 代表公开预期变化尚不清晰

### 4.4 `estimate_attention_level`

输出枚举：`High | Normal | Low`

按最近 14 天有效代理标签数量判定：

| 条件 | 输出 |
|---|---|
| `valid_proxy_count_14d >= 6` | `High` |
| `3 <= valid_proxy_count_14d < 6` | `Normal` |
| `valid_proxy_count_14d < 3` | `Low` |

### 4.5 `expectation_shift`

输出枚举：`Improving | Stable | Deteriorating`

判定顺序固定如下：

1. 先判定 `Deteriorating`
   - `analyst_action_balance_30d <= -0.20`
   - 或 `target_revision_median_pct_30d < 0`
   - 或 `expectation_headline_balance_14d <= -0.20`
2. 若不满足 1，再判定 `Improving`
   - `analyst_action_balance_30d >= 0.20`
   - 且 `target_revision_median_pct_30d > 0`
   - 且 `expectation_headline_balance_14d >= 0`
3. 其余情况输出 `Stable`

约束：

- 若 3 个核心信号中有效信号数 `< 2`，强制输出 `Stable`
- 若分析师动作与代理标签方向冲突，负向规则优先于正向规则
- 仅当目标价修正为正，且不存在负向核心信号时，才允许输出 `Improving`

---

## 5. 标签生成规则

### 5.1 `estimate_attention_level` 标签表

| 条件 | 输出标签 |
|---|---|
| `valid_proxy_count_14d >= 6` | `High` |
| `3 <= valid_proxy_count_14d < 6` | `Normal` |
| `valid_proxy_count_14d < 3` | `Low` |

### 5.2 `expectation_shift` 标签表

| 优先级 | 条件 | 输出标签 |
|---|---|---|
| 1 | `analyst_action_balance_30d <= -0.20` | `Deteriorating` |
| 2 | `target_revision_median_pct_30d < 0` | `Deteriorating` |
| 3 | `expectation_headline_balance_14d <= -0.20` | `Deteriorating` |
| 4 | `analyst_action_balance_30d >= 0.20` 且 `target_revision_median_pct_30d > 0` 且 `expectation_headline_balance_14d >= 0` | `Improving` |
| 5 | 以上都不满足，或有效核心信号数 `< 2` | `Stable` |

说明：

- 标签判定是 **顺序执行**
- `Deteriorating` 优先级高于 `Improving`
- `Stable` 不是偏多标签，而是“当前公开信息不足以证明预期正在上修 / 下修”

---

## 6. 评分拆解

### 6.1 `expectation_score`

`expectation_score` 为 `0-100` 的整数分数，由 4 个子分项组成：

```text
expectation_score =
  analyst_action_score      (0-40) +
  target_revision_score     (0-30) +
  expectation_proxy_score   (0-20) +
  coverage_score            (0-10)
```

### 6.2 `analyst_action_score` 映射

| `analyst_action_balance_30d` | 分值 |
|---|---|
| `>= 0.60` | `40` |
| `[0.30, 0.60)` | `32` |
| `[0.10, 0.30)` | `24` |
| `(-0.10, 0.10)` | `18` |
| `[-0.30, -0.10]` | `8` |
| `< -0.30` | `0` |

### 6.3 `target_revision_score` 映射

| `target_revision_median_pct_30d` | 分值 |
|---|---|
| `>= 15.00` | `30` |
| `[8.00, 15.00)` | `24` |
| `[3.00, 8.00)` | `18` |
| `(-3.00, 3.00)` | `12` |
| `[-8.00, -3.00]` | `4` |
| `< -8.00` | `0` |

### 6.4 `expectation_proxy_score` 映射

| `expectation_headline_balance_14d` | 分值 |
|---|---|
| `>= 0.50` | `20` |
| `[0.20, 0.50)` | `16` |
| `[0.05, 0.20)` | `12` |
| `(-0.05, 0.05)` | `8` |
| `[-0.20, -0.05]` | `3` |
| `< -0.20` | `0` |

### 6.5 `coverage_score` 映射

按 3 组核心信号的可用性与样本覆盖度打分：

| 条件 | 分值 |
|---|---|
| 3 组核心信号均有效，且 `valid_action_count_30d >= 4`，且 `valid_proxy_count_14d >= 4` | `10` |
| 3 组核心信号均有效，但任一样本量低于上述阈值 | `8` |
| 2 组核心信号有效 | `5` |
| 仅 1 组核心信号有效 | `2` |
| 0 组核心信号有效 | `0` |

### 6.6 完整数据下的总分计算

当 4 个子分项都可计算时：

```text
expectation_score =
  analyst_action_score +
  target_revision_score +
  expectation_proxy_score +
  coverage_score
```

输出要求：

- `expectation_score` 四舍五入为整数
- 结果限制在 `[0, 100]`

---

## 7. 低置信度与缺失数据处理

### 7.1 关键字段组定义

| 关键字段组 | 字段 |
|---|---|
| `analyst_action_core` | `published_at`、`rating_action`、`source_name`、`url` |
| `target_revision_core` | `target_price_old`、`target_price_new`、`published_at` |
| `expectation_proxy_core` | `tag`、`headline`、`published_at`、`url`、`classifier_version` |

### 7.2 过期阈值

| 数据类型 | 新鲜 | 警告 | 过期 |
|---|---|---|---|
| `analyst_actions` 数据集快照 | `<= 3` 天 | `4-7` 天 | `> 7` 天 |
| `expectation_proxy_events` 数据集快照 | `<= 2` 天 | `3-5` 天 | `> 5` 天 |

说明：

- 这里的过期定义针对数据集抓取时间，不是事件发布时间
- 事件发布时间自然允许落在 14 / 30 / 60 天窗口内

### 7.3 降级规则

#### 7.3.1 分析师动作缺失

- 最近 30 天无有效分析师动作：
  - `analyst_action_balance_30d = null`
  - `analyst_action_score = unavailable`
- 最近 30 天只有 `1` 条有效动作：
  - 允许计算 `analyst_action_balance_30d`
  - `coverage_score` 不得高于 `8`
  - 置信度降低

#### 7.3.2 目标价修正缺失

- 最近 30 天无有效目标价修正：
  - `target_revision_median_pct_30d = null`
  - `target_revision_score = unavailable`
- 最近 30 天仅 `1` 条有效目标价修正：
  - 允许输出中位数
  - `target_revision_signal_thin = true`
  - 置信度降低

#### 7.3.3 代理标签缺失

- 最近 14 天无有效代理标签：
  - `expectation_headline_balance_14d = null`
  - `expectation_proxy_score = unavailable`
  - `estimate_attention_level = Low`
- 最近 14 天有效代理标签 `< 3`：
  - `proxy_signal_thin = true`
  - `estimate_attention_level = Low`
  - 置信度降低

#### 7.3.4 数据过期

- `analyst_actions` 数据集过期：
  - 所有依赖分析师动作的字段视为 `unavailable`
  - 不得输出 `Improving`
- `expectation_proxy_events` 数据集过期：
  - 所有依赖代理标签的字段视为 `unavailable`
  - `estimate_attention_level = Low`

#### 7.3.5 核心信号不足

- 3 个核心信号中有效信号数 `< 2`：
  - `expectation_shift = Stable`
  - `expectation_score` 使用归一化回退
  - `confidence_level` 最多只能为 `Low`

### 7.4 缺失情况下的分数回退

若存在 `unavailable` 子分项，则使用以下规则：

```text
available_score_sum = sum(可计算子分项实际得分)
available_score_cap = sum(可计算子分项理论满分)
normalized_score = (available_score_sum / available_score_cap) * 100
```

然后应用固定缺失惩罚：

| 条件 | 扣分 |
|---|---|
| `analyst_action_score` unavailable | `15` |
| `target_revision_score` unavailable | `12` |
| `expectation_proxy_score` unavailable | `10` |
| 仅 1 组核心信号有效 | `15` |
| `estimate_attention_level = Low` 且 `valid_proxy_count_14d < 3` | `5` |

最终：

```text
expectation_score =
  clamp(round(normalized_score - missing_penalty), 0, 100)
```

若 `available_score_cap < 50`，则强制回退为：

- `expectation_score = 50`
- `expectation_shift = Stable`
- `confidence_level = Low`

### 7.5 置信度计算

初始值固定为 `1.00`，按下表扣减：

| 条件 | 扣减 |
|---|---|
| `analyst_actions` 处于警告区间 | `0.08` |
| `analyst_actions` 过期 | `0.18` |
| 最近 30 天仅 `1` 条有效分析师动作 | `0.10` |
| 最近 30 天无有效目标价修正 | `0.12` |
| 最近 30 天仅 `1` 条有效目标价修正 | `0.08` |
| `expectation_proxy_events` 处于警告区间 | `0.05` |
| `expectation_proxy_events` 过期 | `0.12` |
| 最近 14 天有效代理标签 `< 3` | `0.10` |
| 3 个核心信号中有效信号数 `< 2` | `0.20` |

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

- 本节 Schema 仅用于 `expectation_shift` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../api/schemas.md](../api/schemas.md) 和 [../api/openapi.yaml](../api/openapi.yaml)

```json
{
  "schema_version": "1.0",
  "ticker": "string",
  "analysis_timestamp": "ISO 8601",
  "module": "ExpectationShiftAnalyzerV1",
  "staleness_days": "number",
  "missing_fields": ["string"],
  "metrics": {
    "positive_action_count_30d": "number",
    "negative_action_count_30d": "number",
    "neutral_action_count_30d": "number",
    "valid_action_count_30d": "number",
    "analyst_action_balance_30d": "number | null",
    "target_revision_median_pct_30d": "number | null",
    "positive_proxy_count_14d": "number",
    "negative_proxy_count_14d": "number",
    "expectation_headline_balance_14d": "number | null",
    "estimate_attention_level": "High | Normal | Low",
    "expectation_shift": "Improving | Stable | Deteriorating",
    "expectation_score": "number"
  },
  "subscores": {
    "analyst_action_score": "number | null",
    "target_revision_score": "number | null",
    "expectation_proxy_score": "number | null",
    "coverage_score": "number"
  },
  "confidence": {
    "confidence_score": "number",
    "confidence_level": "High | Medium | Low",
    "critical_missing_fields": ["string"],
    "stale_fields": ["string"]
  },
  "flags": {
    "target_revision_signal_thin": "boolean",
    "proxy_signal_thin": "boolean",
    "used_normalized_scoring": "boolean"
  },
  "source_trace": [
    {
      "dataset": "analyst_actions | expectation_proxy_events",
      "source": "string",
      "fetched_at": "ISO 8601",
      "staleness_days": "number",
      "missing_fields": ["string"]
    }
  ]
}
```

约束：

- 所有百分比字段统一保留 2 位小数
- `expectation_score` 输出整数
- `critical_missing_fields` 仅列关键字段组名，不输出自然语言猜测

---

## 9. 实现约束与 JSON 示例

### 9.1 实现约束

1. 所有阈值必须硬编码在规则层，不允许由模型自由决定。
2. 必须先完成动作标准化、目标价口径校验和标签过滤，再进入标签判定。
3. `Deteriorating` 优先级高于 `Improving`。
4. 不允许把目标价修正直接当作估值结论，只能当作卖方预期姿态信号。
5. 不允许用缺失摘要或自然语言总结回填结构化字段。
6. 若输入不足，必须执行第 7 节回退逻辑，不允许输出“模型认为偏多 / 偏空”。
7. 每个对外字段都必须能回溯到原始 `url`、`published_at` 和 `classifier_version`。

### 9.2 JSON 输出示例

```json
{
  "schema_version": "1.0",
  "ticker": "TSM",
  "analysis_timestamp": "2026-04-16T10:30:00Z",
  "module": "ExpectationShiftAnalyzerV1",
  "staleness_days": 1,
  "missing_fields": [],
  "metrics": {
    "positive_action_count_30d": 4,
    "negative_action_count_30d": 1,
    "neutral_action_count_30d": 2,
    "valid_action_count_30d": 7,
    "analyst_action_balance_30d": 0.43,
    "target_revision_median_pct_30d": 6.50,
    "positive_proxy_count_14d": 4,
    "negative_proxy_count_14d": 1,
    "expectation_headline_balance_14d": 0.60,
    "estimate_attention_level": "Normal",
    "expectation_shift": "Improving",
    "expectation_score": 80
  },
  "subscores": {
    "analyst_action_score": 32,
    "target_revision_score": 18,
    "expectation_proxy_score": 20,
    "coverage_score": 10
  },
  "confidence": {
    "confidence_score": 0.90,
    "confidence_level": "High",
    "critical_missing_fields": [],
    "stale_fields": []
  },
  "flags": {
    "target_revision_signal_thin": false,
    "proxy_signal_thin": false,
    "used_normalized_scoring": false
  },
  "source_trace": [
    {
      "dataset": "analyst_actions",
      "source": "primary_sellside_feed",
      "fetched_at": "2026-04-16T10:05:00Z",
      "staleness_days": 1,
      "missing_fields": []
    },
    {
      "dataset": "expectation_proxy_events",
      "source": "news_classifier_pipeline",
      "fetched_at": "2026-04-16T10:08:00Z",
      "staleness_days": 0,
      "missing_fields": []
    }
  ]
}
```

该示例表示：

- 最近 30 天分析师公开动作整体偏正向
- 目标价修正中位数为正，说明 sell-side 预期门槛在上移
- 最近 14 天预期代理标签以正向信号为主，且没有触发任何负向优先级条件
- 3 组核心信号均有效，因此允许输出 `Improving`
