# 估值锚点分析器

## 1. 模块目标与边界

本分析器属于服务 **1 周到 3 个月** 持仓周期的基本面模块，但其核心估值锚点判断主要聚焦 **2 周到 2 个月** 的中期交易场景，目标不是估算公司的长期内在价值，而是回答以下两个问题：

1. 当前估值在历史区间中处于什么位置
2. 当前估值相对同类公司是偏便宜、合理还是偏贵

模块输出必须为 **结构化、可追溯、可复现** 的估值锚点信号，供上层决策层与技术、情绪模块联合使用。

### 1.1 范围内

- 主估值指标选择与回退
- 历史估值分位判断
- 同行业 / 同板块相对估值比较
- PEG 使用、失效识别与回退
- `space_rating` 与 `valuation_score` 生成

### 1.2 范围外

- DCF、分部估值、ROIC 长周期分析
- 催化剂、新闻情绪、分析师动作解读
- 长期行业格局判断
- 自动生成交易指令

说明：
- 本模块只回答“当前估值背景是否构成顺风 / 逆风”。
- 事件、情绪、催化剂必须由其他模块负责，禁止重新并入本模块。

---

## 2. 输入与数据来源要求

### 2.1 基础输入

- `ticker`
- `as_of_date`
- `sector`
- `industry`
- `market_cap`

### 2.2 当前估值输入

至少提供以下当前倍数中的可用项：

- `forward_pe`
- `ev_ebitda`
- `price_to_sales`
- `price_to_fcf`

### 2.3 历史估值输入

每个候选估值指标都应提供 **点位历史序列**，用于计算 `historical_percentile`：

- 优先使用最近 `60` 个月月末样本
- 最少需要最近 `24` 个月中的有效样本
- 历史序列必须与当前口径一致，例如当前使用 `Forward P/E`，历史也必须使用同口径 `Forward P/E`

### 2.4 同行估值输入

用于计算 `peer_relative_ratio` 的可比池至少包含：

- `peer_ticker`
- `sector`
- `industry`
- `market_cap`
- 对应估值倍数

### 2.5 PEG 相关输入

PEG 只在 `primary_metric_used = ForwardPE` 时计算，所需字段：

- `forward_pe`
- `forward_eps_growth_pct_next_12m`

### 2.6 数据来源要求

每组输入必须记录：

- `source`
- `fetched_at`
- `staleness_days`
- `missing_fields`

约束如下：

- 当前倍数、历史序列、同行倍数必须尽量来自同一数据提供方
- 若发生备用源回退，必须记录 `override_reason`
- 若关键字段缺失，只允许降级、回退或输出低置信度，不允许用自然语言猜测补全

---

## 3. 主指标选择顺序

### 3.1 选择原则

`primary_metric_used` 必须只选择一个主指标，不允许多指标平均，也不允许由模型主观挑选。

选择顺序按以下固定规则执行：

1. 先判断是否属于 `EV/EBITDA` 优先行业
2. 再判断是否为未盈利公司
3. 再判断是否为成熟现金流公司
4. 其余盈利公司使用 `Forward P/E`
5. 若选中指标无效，则按预设回退链回退

### 3.2 公司类型定义

#### 盈利公司

同时满足：

- `forward_eps > 0`
- `ttm_net_income > 0`

#### 未盈利公司

满足任一条件即成立：

- `forward_eps <= 0`
- `ttm_net_income <= 0`

#### 资本密集行业

若 `industry` 属于以下集合，则优先考虑 `EV/EBITDA`：

- 航空
- 汽车与汽车零部件
- 化工
- 金属与采矿
- 钢铁
- 纸业与包装
- 能源勘探与生产
- 油服
- 炼化
- 中游能源
- 机械
- 工程建设
- 航运
- 铁路与货运
- 电信运营商
- 有线网络基础设施
- 公用事业

资本密集行业判定一旦成立，只要 `ev_ebitda > 0`，`EV/EBITDA` 就优先于 `Forward P/E`。

#### 成熟现金流公司

同时满足以下全部条件：

- 最近 `4` 个季度自由现金流均为正
- 最近 `4` 个季度经营现金流均为正
- `capex_to_cfo_4q <= 0.35`
- `latest_revenue_growth_yoy <= 15`
- 不属于 `EV/EBITDA` 优先行业

### 3.3 主指标选择决策表

| 优先级 | 公司类型 / 条件 | 主指标 | 启用条件 | 回退 1 | 回退 2 |
|---|---|---|---|---|---|
| 1 | 资本密集行业 | `EV/EBITDA` | `ev_ebitda > 0` | `ForwardPE` | `PriceToSales` |
| 2 | 未盈利公司 | `PriceToSales` | `price_to_sales > 0` | `EV/EBITDA` | `null` |
| 3 | 成熟现金流公司 | `PriceToFCF` | `price_to_fcf > 0` | `ForwardPE` | `EV/EBITDA` |
| 4 | 其他盈利公司 | `ForwardPE` | `forward_pe > 0` | `EV/EBITDA` | `PriceToFCF` |

补充规则：

- 未盈利公司只有在 `price_to_sales <= 0` 且 `ev_ebitda > 0` 时，才允许退回 `EV/EBITDA`
- 若主指标与所有回退指标都不可用，则 `primary_metric_used = null`
- `null` 状态下不得输出方向性便宜 / 昂贵结论，只能输出低置信度中性结果

### 3.4 `primary_metric_used` 字段规则

取值范围：

- `ForwardPE`
- `EV/EBITDA`
- `PriceToSales`
- `PriceToFCF`
- `null`

同时输出：

- `primary_metric_value`
- `primary_metric_selection_reason`
- `primary_metric_fallback_reason`

`primary_metric_fallback_reason` 只允许使用以下固定值：

- `InvalidOrNegativePrimaryMultiple`
- `MissingPrimaryMultiple`
- `NoComparableHistory`
- `NoComparablePeers`
- `AllMetricsUnavailable`
- `null`

---

## 4. 历史分位计算规则

### 4.1 目标

`historical_percentile` 用于回答：当前主估值倍数在公司自身历史中处于什么位置。

定义约定：

- 分位数越低，代表估值越便宜
- 分位数越高，代表估值越昂贵

### 4.2 样本窗口

固定规则如下：

- 首选最近 `60` 个月月末样本
- 若 `60` 个月不可用，则使用最近可得的 `36-59` 个月样本
- 若仅有 `24-35` 个有效样本，允许计算，但必须降为 `Medium` 置信度
- 若仅有 `12-23` 个有效样本，允许计算，但必须降为 `Low` 置信度
- 若有效样本 `< 12`，则 `historical_percentile = null`

### 4.3 清洗规则

历史样本只保留与当前主指标同口径、且可比较的样本：

- 删除 `<= 0` 的倍数样本
- 删除缺失样本
- 删除明显口径切换导致的异常样本
- 不允许把不同指标的历史序列拼接在一起

### 4.4 计算公式

设：

- `current_multiple` 为当前主估值倍数
- `valid_history_samples` 为清洗后的有效历史样本
- `n` 为有效样本数

则：

```text
historical_percentile =
  100 × count(sample <= current_multiple) / n
```

输出保留 `1` 位小数。

示例：

- 当前 `Forward P/E = 18.4`
- 有效历史样本 `57` 个
- 其中 `16` 个样本 `<= 18.4`

则：

```text
historical_percentile = 100 × 16 / 57 = 28.1
```

### 4.5 当前倍数不可比较时的处理

若出现以下情况，则当前倍数不可用于历史分位：

- `current_multiple <= 0`
- 当前倍数字段缺失
- 当前使用的是回退指标，但历史中不存在同口径序列

处理规则：

- 将 `historical_percentile = null`
- 记录 `primary_metric_fallback_reason = NoComparableHistory` 或更早的无效原因
- 历史分位分项按中性分处理，见第 8 节

---

## 5. 同行业 / 同板块相对估值规则

### 5.1 可比池构建顺序

`peer_relative_ratio` 按以下固定顺序构建：

1. 同行业 `industry`
2. 若有效同行少于 `5` 个，则扩展到同板块 `sector`
3. 扩展到 `sector` 时，必须限制在同一市值档位

### 5.2 市值档位

固定分桶如下：

- `Small`：`0.3B <= market_cap < 2B`
- `Mid`：`2B <= market_cap < 10B`
- `Large`：`10B <= market_cap < 100B`
- `Mega`：`market_cap >= 100B`

### 5.3 同行过滤规则

同行必须满足：

- 排除目标股票自身
- 使用与目标股票相同的 `primary_metric_used`
- 倍数必须 `> 0`
- 若目标股票为未盈利公司，则同行也必须属于未盈利组
- 若目标股票为盈利公司，则同行必须属于盈利组

### 5.4 样本数规则

- 同行业有效同行 `>= 5`：`peer_group_scope = Industry`
- 同行业有效同行 `< 5` 且同板块同市值档位有效同行 `>= 8`：`peer_group_scope = Sector`
- 以上都不满足：`peer_group_scope = Unavailable`

### 5.5 计算公式

设：

- `current_multiple` 为当前主倍数
- `peer_median_value` 为有效同行中位数

则：

```text
peer_relative_ratio = current_multiple / peer_median_value
```

输出保留 `2` 位小数。

解释规则：

- `< 1.00`：低于同行中位数
- `= 1.00`：等于同行中位数
- `> 1.00`：高于同行中位数

### 5.6 当前倍数或同行中位数不可比较时的处理

出现以下情况时，`peer_relative_ratio = null`：

- `current_multiple <= 0`
- `peer_median_value <= 0`
- `peer_group_scope = Unavailable`

此时：

- `peer_relative_ratio` 分项按中性分处理
- `confidence` 至少降一级

---

## 6. PEG 使用与回退规则

### 6.1 使用范围

`peg_ratio` 只在以下条件同时满足时计算：

- `primary_metric_used = ForwardPE`
- `forward_pe > 0`
- `forward_eps_growth_pct_next_12m` 有值
- `forward_eps_growth_pct_next_12m >= 3`

说明：

- 增长率按百分比点使用，不转成小数
- 例如 `forward_pe = 18.4`，`forward_eps_growth_pct_next_12m = 20`，则 `peg_ratio = 0.92`

### 6.2 计算公式

```text
peg_ratio = forward_pe / forward_eps_growth_pct_next_12m
```

输出保留 `2` 位小数。

### 6.3 `peg_flag` 固定取值

- `Valid`
- `NotApplicablePrimaryMetric`
- `MissingGrowth`
- `GrowthTooLow`
- `NegativeGrowth`
- `NegativeOrZeroMultiple`

### 6.4 `peg_flag` 判定顺序

按以下顺序执行，命中后停止：

1. 若 `primary_metric_used != ForwardPE`，则 `peg_flag = NotApplicablePrimaryMetric`
2. 若 `forward_pe <= 0`，则 `peg_flag = NegativeOrZeroMultiple`
3. 若增长率缺失，则 `peg_flag = MissingGrowth`
4. 若增长率 `< 0`，则 `peg_flag = NegativeGrowth`
5. 若 `0 <= 增长率 < 3`，则 `peg_flag = GrowthTooLow`
6. 其余情况为 `Valid`

### 6.5 PEG 回退规则

当 `peg_flag != Valid` 时：

- `peg_ratio = null`
- 不允许估算替代 PEG
- 估值判断回退到 `historical_percentile + peer_relative_ratio + 数据完整性`
- `valuation_score` 中 PEG 分项按固定回退分处理

PEG 分项回退分如下：

| `peg_flag` | PEG 分项得分 |
|---|---:|
| `Valid` | 按 `peg_ratio` 映射 |
| `NotApplicablePrimaryMetric` | `10` |
| `MissingGrowth` | `8` |
| `GrowthTooLow` | `4` |
| `NegativeGrowth` | `0` |
| `NegativeOrZeroMultiple` | `0` |

---

## 7. `space_rating` 标签规则

### 7.1 标签定义

- `Undervalued`：估值同时低于自身历史与同行，且没有被无效增长掩盖
- `Fair`：估值大致处于正常区间
- `Elevated`：估值高于历史或同行
- `Compressed`：估值处于极高区间，后续更容易发生倍数压缩

### 7.2 固定阈值

先计算：

- `historical_percentile`
- `peer_relative_ratio`
- `peg_ratio`
- `peg_flag`

再按以下顺序判定：

#### `Compressed`

同时满足：

- `historical_percentile != null`
- `peer_relative_ratio != null`
- `historical_percentile >= 85`
- `peer_relative_ratio >= 1.20`
- 且满足任一条件：
  - `peg_flag = NegativeGrowth`
  - `peg_flag = GrowthTooLow`
  - `peg_flag = NegativeOrZeroMultiple`
  - `peg_ratio != null` 且 `peg_ratio > 1.50`

#### `Undervalued`

同时满足：

- `historical_percentile != null`
- `peer_relative_ratio != null`
- `historical_percentile <= 30`
- `peer_relative_ratio <= 0.90`
- 且满足任一条件：
  - `peg_flag = Valid` 且 `peg_ratio <= 1.00`
  - `peg_flag = NotApplicablePrimaryMetric`
  - `peg_flag = MissingGrowth`

#### `Elevated`

满足任一条件：

- `historical_percentile >= 70`
- `peer_relative_ratio >= 1.10`
- `peg_flag = Valid` 且 `peg_ratio > 1.50`

#### `Fair`

除以上三类以外，全部归为 `Fair`。

### 7.3 缺失场景处理

若 `historical_percentile = null` 且 `peer_relative_ratio = null`，则强制：

- `space_rating = Fair`
- `confidence = Low`

---

## 8. `valuation_score` 评分规则

### 8.1 评分结构

`valuation_score` 为 `0-100` 分，由四个分项组成：

```text
valuation_score =
  history_score      (0-35) +
  peer_score         (0-35) +
  peg_score          (0-20) +
  data_quality_score (0-10)
```

### 8.2 `history_score`

若 `historical_percentile = null`，固定取中性分 `18`。

否则按下表映射：

| `historical_percentile` | `history_score` |
|---|---:|
| `<= 10` | `35` |
| `<= 20` | `31` |
| `<= 30` | `27` |
| `<= 40` | `23` |
| `<= 60` | `18` |
| `<= 70` | `14` |
| `<= 80` | `9` |
| `<= 90` | `4` |
| `> 90` | `0` |

### 8.3 `peer_score`

若 `peer_relative_ratio = null`，固定取中性分 `18`。

否则按下表映射：

| `peer_relative_ratio` | `peer_score` |
|---|---:|
| `<= 0.70` | `35` |
| `<= 0.85` | `30` |
| `<= 0.95` | `24` |
| `<= 1.05` | `18` |
| `<= 1.15` | `12` |
| `<= 1.30` | `6` |
| `> 1.30` | `0` |

### 8.4 `peg_score`

若 `peg_flag = Valid`，按下表映射：

| `peg_ratio` | `peg_score` |
|---|---:|
| `<= 0.80` | `20` |
| `<= 1.00` | `16` |
| `<= 1.50` | `10` |
| `<= 2.00` | `4` |
| `> 2.00` | `0` |

若 `peg_flag != Valid`，按第 6.5 节固定回退分执行。

### 8.5 `data_quality_score`

按以下规则计分：

- `10`：主指标、历史分位、同行比较三项全部有效，且 `staleness_days <= 7`
- `7`：三项中有一项缺失，且 `staleness_days <= 14`
- `4`：三项中有两项缺失，或 `15 <= staleness_days <= 30`
- `0`：主指标不可用，或 `staleness_days > 30`

### 8.6 分数解读

- `75-100`：估值顺风明显
- `60-74`：估值略有顺风
- `40-59`：估值中性
- `< 40`：估值逆风明显

---

## 9. 缺失数据与异常场景处理

### 9.1 主指标缺失

若首选主指标缺失或 `<= 0`：

- 按第 3 节决策表回退
- 记录 `primary_metric_fallback_reason`
- 回退后重新计算历史分位与同行比较

### 9.2 全部指标不可用

若所有候选指标都不可用：

- `primary_metric_used = null`
- `primary_metric_value = null`
- `historical_percentile = null`
- `peer_relative_ratio = null`
- `peg_ratio = null`
- `space_rating = Fair`
- `valuation_score = 36`
- `confidence = Low`

### 9.3 历史样本窗口不足

- `24-35` 个有效样本：允许输出，但 `confidence` 最多为 `Medium`
- `12-23` 个有效样本：允许输出，但 `confidence = Low`
- `< 12` 个有效样本：`historical_percentile = null`

### 9.4 当前倍数为负值或不可比较

若当前主倍数 `<= 0`：

- 该指标立即判定为无效
- 不允许参与历史或同行比较
- 必须按回退链切换到下一个指标

### 9.5 同行样本不足

若 `Industry` 样本不足：

- 扩展到 `Sector + 同市值档位`

若仍不足：

- `peer_group_scope = Unavailable`
- `peer_relative_ratio = null`

### 9.6 PEG 异常

- 增长率缺失：`peg_flag = MissingGrowth`
- `0 <= 增长率 < 3`：`peg_flag = GrowthTooLow`
- 增长率 `< 0`：`peg_flag = NegativeGrowth`
- `forward_pe <= 0`：`peg_flag = NegativeOrZeroMultiple`

### 9.7 置信度规则

`confidence` 取值：

- `High`
- `Medium`
- `Low`

固定规则：

- `High`：历史有效样本 `>= 36` 且同行有效样本满足最优分组要求
- `Medium`：历史有效样本 `24-35`，或同行仅能扩展到 `Sector`
- `Low`：历史有效样本 `< 24`，或同行不可用，或主指标发生两级以上回退

---

## 10. 输出 schema 与示例

API 对齐说明：

- 本节 Schema 仅用于 `valuation_anchor` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

### 10.1 输出 schema

| 字段 | 类型 | 说明 |
|---|---|---|
| `module` | `string` | 固定为 `valuation_anchor` |
| `as_of_date` | `string` | 估值快照日期 |
| `primary_metric_used` | `string \| null` | 主指标 |
| `primary_metric_value` | `number \| null` | 主指标当前倍数 |
| `primary_metric_selection_reason` | `string \| null` | 选择主指标的固定原因码 |
| `primary_metric_fallback_reason` | `string \| null` | 回退原因 |
| `historical_window_months_used` | `number` | 实际历史窗口月数 |
| `historical_valid_sample_count` | `number` | 有效历史样本数 |
| `historical_percentile` | `number \| null` | 历史分位，越低越便宜 |
| `peer_group_scope` | `string` | `Industry \| Sector \| Unavailable` |
| `peer_count_used` | `number` | 有效同行样本数 |
| `peer_median_value` | `number \| null` | 同行中位数 |
| `peer_relative_ratio` | `number \| null` | 当前倍数 / 同行中位数 |
| `peg_ratio` | `number \| null` | PEG |
| `peg_flag` | `string` | PEG 状态 |
| `space_rating` | `string` | `Undervalued \| Fair \| Elevated \| Compressed` |
| `valuation_score` | `number` | `0-100` |
| `confidence` | `string` | `High \| Medium \| Low` |
| `staleness_days` | `number` | 估值数据新鲜度，供聚合器直接消费 |
| `missing_fields` | `string[]` | 当前模块缺失字段，供聚合器直接消费 |
| `metrics` | `object` | 原始与派生估值字段 |
| `data_issues` | `string[]` | 缺失、异常、回退说明 |
| `source_summary` | `object` | 来源与时效性摘要 |

### 10.2 `metrics` 字段示例

```json
{
  "forward_pe": 18.4,
  "ev_ebitda": 14.1,
  "price_to_sales": 5.2,
  "price_to_fcf": 19.8,
  "forward_eps_growth_pct_next_12m": 20.0,
  "history_forward_pe_p10_5y": 13.4,
  "history_forward_pe_p50_5y": 22.9,
  "history_forward_pe_p90_5y": 31.4,
  "peer_forward_pe_median": 21.7
}
```

### 10.3 完整 JSON 输出示例

```json
{
  "module": "valuation_anchor",
  "as_of_date": "2026-04-16",
  "primary_metric_used": "ForwardPE",
  "primary_metric_value": 18.4,
  "primary_metric_selection_reason": "ProfitableNonCapitalIntensive",
  "primary_metric_fallback_reason": null,
  "historical_window_months_used": 60,
  "historical_valid_sample_count": 57,
  "historical_percentile": 28.1,
  "peer_group_scope": "Industry",
  "peer_count_used": 11,
  "peer_median_value": 21.7,
  "peer_relative_ratio": 0.85,
  "peg_ratio": 0.92,
  "peg_flag": "Valid",
  "space_rating": "Undervalued",
  "valuation_score": 78,
  "confidence": "High",
  "staleness_days": 0,
  "missing_fields": [],
  "metrics": {
    "forward_pe": 18.4,
    "ev_ebitda": 14.1,
    "price_to_sales": 5.2,
    "price_to_fcf": 19.8,
    "forward_eps_growth_pct_next_12m": 20.0,
    "history_forward_pe_p10_5y": 13.4,
    "history_forward_pe_p50_5y": 22.9,
    "history_forward_pe_p90_5y": 31.4,
    "peer_forward_pe_median": 21.7
  },
  "data_issues": [],
  "source_summary": {
    "valuation_source": "primary_financial_provider",
    "history_source": "primary_financial_provider",
    "peer_source": "primary_financial_provider",
    "fetched_at": "2026-04-16T09:30:00Z",
    "staleness_days": 0,
    "missing_fields": []
  }
}
```
