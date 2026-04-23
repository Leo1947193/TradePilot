# ② 财务健康检查器 — 子模块设计文档

> 本文档是基本面分析模块 [overview.md](./overview.md) 中“② 财务健康检查器”子 Agent 的详细设计。目标是将财务脆弱点筛查固化为**可直接实现**的规则，明确哪些情况只是高风险，哪些情况才构成**近端硬风险否决**。

---

## 1. 模块目标与边界

### 1.1 模块目标

本模块属于服务 **1 周到 3 个月** 持仓周期的基本面模块，但其近端硬风险判断主要聚焦 **2 周到 2 个月** 的中期交易窗口，只回答一个问题：

> 该公司是否存在会在近期显著放大回撤风险的财务脆弱点？

模块必须输出：

1. 固定口径的财务健康检查结果
2. 可追溯的 `checks` 明细
3. 确定性的 `overall_rating`
4. 仅在满足近端硬风险条件时才触发的 `disqualify`

### 1.2 范围内

- 现金流质量
- 流动性压力
- 盈利质量
- 杠杆压力
- 近端硬风险识别
- 面向上游聚合层的结构化风险输出

### 1.3 范围外

- 长期价值投资判断
- 行业竞争格局或行业深度研究
- 催化剂、新闻情绪、分析师动作
- 管理层叙事可信度的主观判断

### 1.4 为什么硬风险只允许覆盖近端风险

本系统的目标持有期是 **14-60 天**。因此：

- 可以触发 `disqualify` 的，只能是**未来 1-2 个季度内可能兑现**的融资、偿债或现金流断裂风险
- 长期低质量、慢性高杠杆、估值过高、盈利波动大等问题，最多提升为 `overall_rating = High`
- **`High` 风险不等于自动取消资格**
- 只有命中本文件定义的 `hard_risk_reasons`，才允许 `disqualify = true`

---

## 2. 输入字段与数据窗口

### 2.1 必需输入字段

| 字段 | 类型 | 窗口 | 用途 |
|---|---|---|---|
| `cash_and_equivalents` | `number` | 最近 1 个季度 | 现金覆盖与净债务计算 |
| `short_term_debt` | `number` | 最近 1 个季度 | `cash_to_short_term_debt` |
| `current_assets` | `number` | 最近 1 个季度 | `current_ratio` |
| `current_liabilities` | `number` | 最近 1 个季度 | `current_ratio` |
| `accounts_receivable` | `number` | 最近 5 个季度 | 应收增速缺口 |
| `inventory` | `number` | 最近 5 个季度 | 库存增速缺口 |
| `total_debt` | `number` | 最近 1 个季度 | 杠杆压力 |
| `operating_cash_flow` | `number` | 最近 4 个季度 | `CFO / Net Income`、现金流压力 |
| `capital_expenditure` | `number` | 最近 4 个季度 | `FCF` 计算 |
| `net_income` | `number` | 最近 4 个季度 | 利润兑现质量 |
| `revenue` | `number` | 最近 5 个季度 | 应收/库存相对增速 |
| `operating_income` | `number` | 最近 4 个季度 | `interest_coverage` |
| `interest_expense` | `number` | 最近 4 个季度 | `interest_coverage` |
| `depreciation_and_amortization` | `number` | 最近 4 个季度 | `net_debt_to_ebitda` |
| `report_period_end` | `date` | 最近 1 个季度 | `data_staleness_days` |
| `source` | `string` | 每个数据集 | 可追溯性 |
| `fetched_at` | `datetime` | 每个数据集 | 数据源追踪 |
| `missing_fields` | `[string]` | 当前批次 | 缺失处理 |

### 2.2 数据窗口定义

| 窗口 | 定义 | 用途 |
|---|---|---|
| `latest_quarter` | 最近一个已披露季度 | 现金、短债、流动比率、总债务 |
| `ttm` | 最近 4 个季度求和 | `FCF / Net Income`、`CFO / Net Income`、`interest_coverage`、`net_debt_to_ebitda` |
| `latest_2q` | 最近 2 个季度序列 | 连续现金流为负检测 |
| `latest_q_vs_4q_ago` | 最近季度与 4 个季度前对比 | 应收/库存相对营收增速 |

### 2.3 最低数据要求

- 若最近 4 个季度利润表 / 现金流量表数据不足 4 期，则所有 TTM 指标标记为 `unavailable`
- 若最近 5 个季度收入、应收或库存不足 5 期，则盈利质量中的同比缺口指标标记为 `unavailable`
- `unavailable` 不得被模型主观补全

---

## 3. 核心指标计算口径

### 3.1 自由现金流 `FCF`

```text
FCF_ttm = CFO_ttm - Capex_ttm
```

其中：

- `CFO_ttm` = 最近 4 个季度 `operating_cash_flow` 求和
- `Capex_ttm` = 最近 4 个季度 `capital_expenditure` 的现金流出绝对值求和
- 若源数据已将资本开支记为负数，先取绝对值再参与计算

### 3.2 净利润 `Net Income`

```text
NetIncome_ttm = 最近 4 个季度 net_income 求和
```

- 使用归属于普通股股东的净利润
- 不使用经调整后的 non-GAAP 口径

### 3.3 `FCF / Net Income`

```text
fcf_to_net_income = FCF_ttm / NetIncome_ttm
```

仅在 `NetIncome_ttm > 0` 时计算。

若 `NetIncome_ttm <= 0`：

- `value = null`
- `status = unavailable`
- `reason = "net_income_ttm_non_positive"`
- 该指标不直接作为红旗
- 现金流质量改由 `FCF_ttm`、`CFO_ttm` 的正负号与连续性规则承接

### 3.4 `CFO / Net Income`

```text
cfo_to_net_income = CFO_ttm / NetIncome_ttm
```

仅在 `NetIncome_ttm > 0` 时计算。

若 `NetIncome_ttm <= 0`，处理规则与 `FCF / Net Income` 相同。

### 3.5 `cash_to_short_term_debt`

```text
cash_to_short_term_debt = CashAndEquivalents_latest / ShortTermDebt_latest
```

其中：

- `CashAndEquivalents_latest` = 最近季度现金及等价物
- `ShortTermDebt_latest` = 最近季度短期借款 + 一年内到期长期债务

若 `ShortTermDebt_latest = 0`：

- `value = null`
- `status = pass`
- `reason = "no_short_term_debt"`

### 3.6 `interest_coverage`

```text
interest_coverage = OperatingIncome_ttm / InterestExpense_ttm
```

其中：

- `OperatingIncome_ttm` = 最近 4 个季度 `operating_income` 求和
- `InterestExpense_ttm` = 最近 4 个季度 `interest_expense` 的绝对值求和

若 `latest_total_debt = 0`：

- `value = null`
- `status = pass`
- `reason = "debt_free_balance_sheet"`

若 `latest_total_debt > 0` 且 `InterestExpense_ttm <= 0`：

- `value = null`
- `status = unavailable`
- `reason = "interest_expense_missing_or_non_positive"`

### 3.7 `current_ratio`

```text
current_ratio = CurrentAssets_latest / CurrentLiabilities_latest
```

仅在 `CurrentLiabilities_latest > 0` 时计算。否则标记为 `unavailable`。

### 3.8 `net_debt_to_ebitda`

```text
NetDebt_latest = max(TotalDebt_latest - CashAndEquivalents_latest, 0)
EBITDA_ttm = OperatingIncome_ttm + DandA_ttm
net_debt_to_ebitda = NetDebt_latest / EBITDA_ttm
```

若：

- `NetDebt_latest = 0`：`status = pass`，`reason = "net_cash_or_zero_net_debt"`
- `NetDebt_latest > 0` 且 `EBITDA_ttm <= 0`：`status = fail`，`reason = "positive_net_debt_with_non_positive_ebitda"`

### 3.9 应收与库存相对营收增速缺口

```text
receivables_growth_yoy =
  (AR_latest_q - AR_4q_ago) / AR_4q_ago

inventory_growth_yoy =
  (Inventory_latest_q - Inventory_4q_ago) / Inventory_4q_ago

revenue_growth_yoy =
  (Revenue_latest_q - Revenue_4q_ago) / Revenue_4q_ago

receivables_growth_gap_pp =
  (receivables_growth_yoy - revenue_growth_yoy) * 100

inventory_growth_gap_pp =
  (inventory_growth_yoy - revenue_growth_yoy) * 100
```

若分母 `4q_ago` 值小于等于 0，则对应指标标记为 `unavailable`。

### 3.10 `data_staleness_days`

```text
data_staleness_days = analysis_date - latest_report_period_end
```

说明：

- 使用最近一份**已披露季度报表的期末日期**，而不是 `fetched_at`
- 该字段衡量财务状态对当前分析时点的经济新鲜度
- `fetched_at` 仅用于数据源追踪，不参与时效性判断

---

## 4. 检查项定义

本模块固定四类检查：

1. `cashflow_quality`
2. `liquidity_pressure`
3. `earnings_quality`
4. `leverage_pressure`

每类检查由若干原子规则组成。原子规则进入 `checks` 数组；类别级结论用于计算 `overall_rating` 和 `health_score`。

### 4.1 现金流质量 `cashflow_quality`

### 原子规则

| `name` | 阈值 | `pass` | `warning` | `fail` |
|---|---|---|---|---|
| `fcf_to_net_income` | `FCF_ttm / NetIncome_ttm` | `>= 0.80` | `0.50 - 0.79` | `< 0.50` |
| `cfo_to_net_income` | `CFO_ttm / NetIncome_ttm` | `>= 0.90` | `0.60 - 0.89` | `< 0.60` |
| `fcf_negative_streak_2q` | 最近 2 季 FCF 为负的连续季度数 | `0` | `1` | `2` |

### 类别评级规则

- `Low`
  - 无 `fail`
  - 且 `warning` 数量 `<= 1`
- `Medium`
  - 恰好 1 个 `fail`
  - 或 `warning` 数量 `>= 2`
  - 或 `NetIncome_ttm <= 0` 且 `CFO_ttm > 0` 且 `FCF_ttm <= 0`
- `High`
  - `fcf_negative_streak_2q = fail`
  - 或 `NetIncome_ttm <= 0` 且 `CFO_ttm <= 0` 且 `FCF_ttm <= 0`
  - 或原子规则中 `fail` 数量 `>= 2`

### 4.2 流动性压力 `liquidity_pressure`

### 原子规则

| `name` | 阈值 | `pass` | `warning` | `fail` |
|---|---|---|---|---|
| `cash_to_short_term_debt` | 现金 / 短债 | `>= 1.50` | `1.00 - 1.49` | `< 1.00` |
| `current_ratio` | 流动资产 / 流动负债 | `>= 1.20` | `1.00 - 1.19` | `< 1.00` |
| `cfo_negative_streak_2q` | 最近 2 季 CFO 为负的连续季度数 | `0` | `1` | `2` |

### 类别评级规则

- `Low`
  - 无 `fail`
  - 且 `warning` 数量 `<= 1`
- `Medium`
  - 恰好 1 个 `fail`
  - 或 `warning` 数量 `>= 2`
- `High`
  - `cash_to_short_term_debt = fail` 且 `current_ratio = fail`
  - 或 `cash_to_short_term_debt = fail` 且 `cfo_negative_streak_2q = fail`
  - 或原子规则中 `fail` 数量 `>= 2`

### 4.3 盈利质量 `earnings_quality`

### 原子规则

| `name` | 阈值 | `pass` | `warning` | `fail` |
|---|---|---|---|---|
| `receivables_growth_gap_pp` | 应收增速减营收增速 | `<= 10` | `> 10 且 <= 25` | `> 25` |
| `inventory_growth_gap_pp` | 库存增速减营收增速 | `<= 15` | `> 15 且 <= 30` | `> 30` |

### 类别评级规则

- `Low`
  - 两项均为 `pass`
  - 或 1 项 `warning` + 1 项 `pass`
- `Medium`
  - 恰好 1 个 `fail`
  - 或两项均为 `warning`
- `High`
  - 两项均为 `fail`
  - 或 1 项 `fail` + 1 项 `warning`

### 4.4 杠杆压力 `leverage_pressure`

### 原子规则

| `name` | 阈值 | `pass` | `warning` | `fail` |
|---|---|---|---|---|
| `net_debt_to_ebitda` | 净债务 / EBITDA | `<= 3.0` | `> 3.0 且 <= 4.5` | `> 4.5` |
| `interest_coverage` | 营业利润 / 利息费用 | `>= 3.0` | `1.5 - 2.99` | `< 1.5` |

### 类别评级规则

- `Low`
  - 无 `fail`
  - 且 `warning` 数量 `<= 1`
- `Medium`
  - 恰好 1 个 `fail`
  - 或两项均为 `warning`
- `High`
  - 两项均为 `fail`
  - 或 `net_debt_to_ebitda = fail` 且 `interest_coverage = warning`
  - 或 `interest_coverage = fail` 且 `net_debt_to_ebitda = warning`

---

## 5. 红旗判定规则

### 5.1 红旗定义

当且仅当某一检查类别的评级为 `High` 时，该类别记为一个 `red_flag`。

```text
red_flag_count = count(category_rating == High)
```

### 5.2 各类别红旗触发条件

| 类别 | 触发 `High` 的核心情形 |
|---|---|
| `cashflow_quality` | 连续 2 季 FCF 为负；或利润、CFO、FCF 同时走弱 |
| `liquidity_pressure` | 现金覆盖短债不足，且流动比率或近期经营现金流同时恶化 |
| `earnings_quality` | 应收和库存增速同时明显快于营收 |
| `leverage_pressure` | 杠杆高且利息保障弱，或正净债务对应非正 EBITDA |

### 5.3 红旗与取消资格的关系

- `red_flag` 只表示高风险
- `red_flag` 不自动触发 `disqualify`
- `disqualify` 只由第 7 节定义的 `hard_risk_reasons` 决定
- 输出层必须将类别级红旗显式暴露为 `red_flag_categories`

---

## 6. `overall_rating` 规则

设：

```text
high_count = count(category_rating == High)
medium_count = count(category_rating == Medium)
```

则：

- `overall_rating = High`
  - 当 `disqualify = true`
  - 或 `high_count >= 2`
  - 或 `high_count = 1` 且 `medium_count >= 1`
- `overall_rating = Medium`
  - 当 `high_count = 1` 且 `medium_count = 0`
  - 或 `high_count = 0` 且 `medium_count >= 2`
- `overall_rating = Low`
  - 当 `high_count = 0` 且 `medium_count <= 1`

说明：

- `overall_rating = High` 只代表该标的存在显著财务脆弱性
- `overall_rating = High` 但 `hard_risk_reasons = []` 时，**不得**触发取消资格

---

## 7. `disqualify` 规则

### 7.1 固定枚举 `hard_risk_reasons`

`hard_risk_reasons` 只允许出现以下枚举值：

1. `near_term_debt_coverage_failure`
2. `cash_burn_against_short_term_debt`
3. `working_capital_crunch`

### 7.2 触发条件

### 规则 1：`near_term_debt_coverage_failure`

同时满足：

- `cash_to_short_term_debt < 1.0`
- `interest_coverage < 1.5`
- `data_staleness_days <= 120`

含义：

- 账上现金不足以覆盖近端短债
- 当期盈利对利息支出的保障能力也不足
- 这是典型的近端偿债压力组合

### 规则 2：`cash_burn_against_short_term_debt`

同时满足：

- `cash_to_short_term_debt < 1.0`
- 最近 2 个季度 `FCF < 0`
- `data_staleness_days <= 120`

含义：

- 现金覆盖短债不足
- 公司仍在连续消耗自由现金流
- 即使账面利润尚未完全失真，也足以构成近端融资压力

### 规则 3：`working_capital_crunch`

同时满足：

- `cash_to_short_term_debt < 0.75`
- `current_ratio < 0.90`
- 最近 2 个季度 `CFO < 0`
- `data_staleness_days <= 120`

含义：

- 这是更强的营运资金挤压信号
- 其本质是短债覆盖不足、流动资产缓冲不足、经营现金继续流出

### 7.3 时效性限制

若 `data_staleness_days > 120`：

- `hard_risk_reasons` 必须返回空数组 `[]`
- `disqualify` 必须为 `false`
- 即使当前类别评级为 `High`，也只能保留为高风险提示，不能一票否决

原因：

- 超过 120 天的季度财务状态，已经不足以支撑近端强否决
- 本模块应避免用过期数据制造错误的取消资格信号

### 7.4 缺失字段限制

若某条硬风险规则所需关键字段缺失或 `unavailable`：

- 该条规则不得触发
- 不允许“按常识推断”补齐

### 7.5 最终判定

```text
disqualify = (len(hard_risk_reasons) > 0)
```

### 7.6 输出层红旗字段

为便于聚合器直接消费，财务健康模块必须额外输出：

```text
category_ratings = {
  cashflow_quality: "Low | Medium | High",
  liquidity_pressure: "Low | Medium | High",
  earnings_quality: "Low | Medium | High",
  leverage_pressure: "Low | Medium | High"
}

red_flag_categories =
  所有 category_ratings 中取值为 High 的类别名称数组
```

规则：

- `red_flag_categories` 只允许包含上述 4 个固定类别
- `red_flag_categories = []` 表示没有类别级红旗
- 聚合器不得再从 `checks.status` 反推红旗，必须直接读取该字段

---

## 8. `health_score` 评分拆解

### 8.1 总公式

```text
health_score =
  cashflow_quality_score  (0-30) +
  liquidity_score         (0-25) +
  earnings_quality_score  (0-20) +
  leverage_score          (0-25)
```

### 8.2 评分表

### 现金流质量：30 分

| 项目 | 满分 | `pass` | `warning` | `fail` | `unavailable` |
|---|---|---|---|---|---|
| `fcf_to_net_income` | 12 | 12 | 6 | 0 | 6 |
| `cfo_to_net_income` | 10 | 10 | 5 | 0 | 5 |
| `fcf_negative_streak_2q` | 8 | 8 | 4 | 0 | 4 |

补充规则：

- 若 `NetIncome_ttm <= 0` 且 `FCF_ttm > 0`，则 `fcf_to_net_income` 记 `unavailable` 但保留 6 分
- 若 `NetIncome_ttm <= 0` 且 `FCF_ttm <= 0`，则 `fcf_to_net_income` 记 0 分
- 若 `NetIncome_ttm <= 0` 且 `CFO_ttm > 0`，则 `cfo_to_net_income` 记 5 分
- 若 `NetIncome_ttm <= 0` 且 `CFO_ttm <= 0`，则 `cfo_to_net_income` 记 0 分

### 流动性压力：25 分

| 项目 | 满分 | `pass` | `warning` | `fail` | `unavailable` |
|---|---|---|---|---|---|
| `cash_to_short_term_debt` | 12 | 12 | 6 | 0 | 6 |
| `current_ratio` | 7 | 7 | 3 | 0 | 3 |
| `cfo_negative_streak_2q` | 6 | 6 | 3 | 0 | 3 |

说明：

- `short_term_debt = 0` 时，`cash_to_short_term_debt` 视为 `pass` 并拿满分

### 盈利质量：20 分

| 项目 | 满分 | `pass` | `warning` | `fail` | `unavailable` |
|---|---|---|---|---|---|
| `receivables_growth_gap_pp` | 10 | 10 | 5 | 0 | 5 |
| `inventory_growth_gap_pp` | 10 | 10 | 5 | 0 | 5 |

### 杠杆压力：25 分

| 项目 | 满分 | `pass` | `warning` | `fail` | `unavailable` |
|---|---|---|---|---|---|
| `net_debt_to_ebitda` | 12 | 12 | 6 | 0 | 6 |
| `interest_coverage` | 13 | 13 | 6 | 0 | 6 |

说明：

- `latest_total_debt = 0` 时，`interest_coverage` 视为 `pass`
- `net_debt = 0` 时，`net_debt_to_ebitda` 视为 `pass`

### 8.3 分数解释

| `health_score` | 解读 |
|---|---|
| `80 - 100` | 财务健康，近端脆弱点少 |
| `60 - 79` | 有可见风险，但尚未形成广泛脆弱性 |
| `< 60` | 财务脆弱性明显，应结合 `overall_rating` 和 `hard_risk_reasons` 谨慎处理 |

注意：

- `health_score < 60` 不自动等于 `disqualify`
- `health_score >= 60` 也不覆盖 `disqualify = true`
- **否决优先级高于分数**

---

## 9. `checks` 数据结构定义

### 9.1 `HealthCheckItem` Schema

```json
{
  "category": "cashflow_quality | liquidity_pressure | earnings_quality | leverage_pressure",
  "name": "string",
  "status": "pass | warning | fail | unavailable",
  "value": "number | boolean | null",
  "unit": "ratio | quarters | pct_points | usd | boolean | null",
  "threshold": {
    "pass_gte": "number | null",
    "warning_gte": "number | null",
    "warning_lte": "number | null",
    "fail_lt": "number | null",
    "fail_gt": "number | null"
  },
  "window": "latest_quarter | ttm | latest_2q | latest_q_vs_4q_ago",
  "hard_risk_candidate": "boolean",
  "reason": "string",
  "source": "string",
  "as_of_date": "YYYY-MM-DD"
}
```

### 9.2 字段要求

每个 `checks` item 至少必须包含：

- `name`
- `status`
- `value`
- `threshold`
- `reason`

本模块 v1 要求实际落地时额外固定包含：

- `category`
- `unit`
- `window`
- `hard_risk_candidate`
- `source`
- `as_of_date`

### 9.3 `checks` 数组示例

```json
[
  {
    "category": "cashflow_quality",
    "name": "fcf_to_net_income",
    "status": "warning",
    "value": 0.67,
    "unit": "ratio",
    "threshold": {
      "pass_gte": 0.8,
      "warning_gte": 0.5,
      "warning_lte": 0.79,
      "fail_lt": 0.5,
      "fail_gt": null
    },
    "window": "ttm",
    "hard_risk_candidate": false,
    "reason": "自由现金流对净利润覆盖不足，但尚未跌破 fail 阈值。",
    "source": "company_filings",
    "as_of_date": "2026-03-31"
  },
  {
    "category": "liquidity_pressure",
    "name": "cash_to_short_term_debt",
    "status": "fail",
    "value": 0.82,
    "unit": "ratio",
    "threshold": {
      "pass_gte": 1.5,
      "warning_gte": 1.0,
      "warning_lte": 1.49,
      "fail_lt": 1.0,
      "fail_gt": null
    },
    "window": "latest_quarter",
    "hard_risk_candidate": true,
    "reason": "现金不足以覆盖近端短债。",
    "source": "company_filings",
    "as_of_date": "2026-03-31"
  },
  {
    "category": "earnings_quality",
    "name": "receivables_growth_gap_pp",
    "status": "warning",
    "value": 18.4,
    "unit": "pct_points",
    "threshold": {
      "pass_gte": null,
      "warning_gte": 10.01,
      "warning_lte": 25.0,
      "fail_lt": null,
      "fail_gt": 25.0
    },
    "window": "latest_q_vs_4q_ago",
    "hard_risk_candidate": false,
    "reason": "应收增速明显快于营收，需关注回款质量。",
    "source": "company_filings",
    "as_of_date": "2026-03-31"
  },
  {
    "category": "leverage_pressure",
    "name": "interest_coverage",
    "status": "warning",
    "value": 2.1,
    "unit": "ratio",
    "threshold": {
      "pass_gte": 3.0,
      "warning_gte": 1.5,
      "warning_lte": 2.99,
      "fail_lt": 1.5,
      "fail_gt": null
    },
    "window": "ttm",
    "hard_risk_candidate": true,
    "reason": "利息保障倍数偏低，但尚未跌破硬风险阈值。",
    "source": "company_filings",
    "as_of_date": "2026-03-31"
  }
]
```

---

## 10. 缺失数据、异常值、时效性处理

### 10.1 缺失数据处理

- 原始字段缺失时，对应 `checks` 项输出 `status = unavailable`
- `reason` 必须写明缺失原因，例如：
  - `missing_latest_quarter_balance_sheet_field`
  - `insufficient_quarters_for_ttm`
  - `invalid_denominator_non_positive`
- `unavailable` 可参与 `health_score` 的中性计分
- `unavailable` 不得触发 `hard_risk_reasons`

### 10.2 异常值处理

以下情况视为异常输入，不做推断修复：

- `current_assets < 0`
- `current_liabilities < 0`
- `cash_and_equivalents < 0`
- `short_term_debt < 0`
- `interest_expense < 0` 且同时 `total_debt > 0`
- 最近 4 个季度序列顺序不连续

处理方式：

- 对受影响指标标记 `unavailable`
- 在 `reason` 中写入 `invalid_input_value`

### 10.3 时效性分层

| `data_staleness_days` | 处理规则 |
|---|---|
| `<= 90` | 正常使用 |
| `91 - 120` | 允许触发 `disqualify`，但需在 `reason` 中标记为临近过期 |
| `> 120` | 禁止触发 `disqualify` |

### 10.4 时效性与风险判定的关系

- 过期数据仍可输出 `overall_rating = High`
- 过期数据仍可输出较低 `health_score`
- 但**不得**输出 `disqualify = true`

---

## 11. 输出 Schema 与示例

API 对齐说明：

- 本节 Schema 仅用于 `financial_health` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

### 11.1 输出 Schema

```json
{
  "overall_rating": "Low | Medium | High",
  "disqualify": "boolean",
  "hard_risk_reasons": [
    "near_term_debt_coverage_failure | cash_burn_against_short_term_debt | working_capital_crunch"
  ],
  "category_ratings": {
    "cashflow_quality": "Low | Medium | High",
    "liquidity_pressure": "Low | Medium | High",
    "earnings_quality": "Low | Medium | High",
    "leverage_pressure": "Low | Medium | High"
  },
  "red_flag_categories": ["cashflow_quality | liquidity_pressure | earnings_quality | leverage_pressure"],
  "checks": ["HealthCheckItem"],
  "health_score": "number",
  "data_staleness_days": "number",
  "missing_fields": ["string"]
}
```

### 11.2 完整 JSON 输出示例

```json
{
  "overall_rating": "Medium",
  "disqualify": false,
  "hard_risk_reasons": [],
  "category_ratings": {
    "cashflow_quality": "Medium",
    "liquidity_pressure": "Low",
    "earnings_quality": "Medium",
    "leverage_pressure": "Medium"
  },
  "red_flag_categories": [],
  "checks": [
    {
      "category": "cashflow_quality",
      "name": "fcf_to_net_income",
      "status": "warning",
      "value": 0.67,
      "unit": "ratio",
      "threshold": {
        "pass_gte": 0.8,
        "warning_gte": 0.5,
        "warning_lte": 0.79,
        "fail_lt": 0.5,
        "fail_gt": null
      },
      "window": "ttm",
      "hard_risk_candidate": false,
      "reason": "自由现金流对净利润覆盖不足，但尚未跌破 fail 阈值。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "cashflow_quality",
      "name": "cfo_to_net_income",
      "status": "pass",
      "value": 0.94,
      "unit": "ratio",
      "threshold": {
        "pass_gte": 0.9,
        "warning_gte": 0.6,
        "warning_lte": 0.89,
        "fail_lt": 0.6,
        "fail_gt": null
      },
      "window": "ttm",
      "hard_risk_candidate": false,
      "reason": "经营现金流对净利润覆盖正常。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "liquidity_pressure",
      "name": "cash_to_short_term_debt",
      "status": "warning",
      "value": 1.18,
      "unit": "ratio",
      "threshold": {
        "pass_gte": 1.5,
        "warning_gte": 1.0,
        "warning_lte": 1.49,
        "fail_lt": 1.0,
        "fail_gt": null
      },
      "window": "latest_quarter",
      "hard_risk_candidate": true,
      "reason": "现金覆盖短债仅略高于 1 倍，缓冲偏薄。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "liquidity_pressure",
      "name": "current_ratio",
      "status": "pass",
      "value": 1.26,
      "unit": "ratio",
      "threshold": {
        "pass_gte": 1.2,
        "warning_gte": 1.0,
        "warning_lte": 1.19,
        "fail_lt": 1.0,
        "fail_gt": null
      },
      "window": "latest_quarter",
      "hard_risk_candidate": false,
      "reason": "流动比率仍在安全区间。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "earnings_quality",
      "name": "receivables_growth_gap_pp",
      "status": "warning",
      "value": 18.4,
      "unit": "pct_points",
      "threshold": {
        "pass_gte": null,
        "warning_gte": 10.01,
        "warning_lte": 25.0,
        "fail_lt": null,
        "fail_gt": 25.0
      },
      "window": "latest_q_vs_4q_ago",
      "hard_risk_candidate": false,
      "reason": "应收增速快于营收，表明回款质量承压。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "earnings_quality",
      "name": "inventory_growth_gap_pp",
      "status": "pass",
      "value": 8.2,
      "unit": "pct_points",
      "threshold": {
        "pass_gte": null,
        "warning_gte": 15.01,
        "warning_lte": 30.0,
        "fail_lt": null,
        "fail_gt": 30.0
      },
      "window": "latest_q_vs_4q_ago",
      "hard_risk_candidate": false,
      "reason": "库存增速未明显偏离营收增速。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "leverage_pressure",
      "name": "net_debt_to_ebitda",
      "status": "warning",
      "value": 3.4,
      "unit": "ratio",
      "threshold": {
        "pass_gte": null,
        "warning_gte": 3.01,
        "warning_lte": 4.5,
        "fail_lt": null,
        "fail_gt": 4.5
      },
      "window": "ttm",
      "hard_risk_candidate": false,
      "reason": "杠杆高于舒适区，但尚未进入 fail 区间。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    },
    {
      "category": "leverage_pressure",
      "name": "interest_coverage",
      "status": "warning",
      "value": 2.1,
      "unit": "ratio",
      "threshold": {
        "pass_gte": 3.0,
        "warning_gte": 1.5,
        "warning_lte": 2.99,
        "fail_lt": 1.5,
        "fail_gt": null
      },
      "window": "ttm",
      "hard_risk_candidate": true,
      "reason": "利息保障倍数偏低，但未触发硬风险。",
      "source": "company_filings",
      "as_of_date": "2026-03-31"
    }
  ],
  "health_score": 68,
  "data_staleness_days": 16,
  "missing_fields": []
}
```

### 11.3 “高风险但未取消资格”示例

```json
{
  "overall_rating": "High",
  "disqualify": false,
  "hard_risk_reasons": [],
  "category_ratings": {
    "cashflow_quality": "High",
    "liquidity_pressure": "Medium",
    "earnings_quality": "Low",
    "leverage_pressure": "High"
  },
  "red_flag_categories": [
    "cashflow_quality",
    "leverage_pressure"
  ],
  "why": "cashflow_quality = High，leverage_pressure = High，但 cash_to_short_term_debt = 1.12，未跌破 1.0，因此不满足任何硬风险条件。"
}
```

该例说明：

- 允许输出非常差的财务质量结论
- 但只要近端短债覆盖没有破线，就不能自动一票否决

### 11.4 “命中取消资格”示例

```json
{
  "overall_rating": "High",
  "disqualify": true,
  "hard_risk_reasons": [
    "near_term_debt_coverage_failure",
    "cash_burn_against_short_term_debt"
  ],
  "category_ratings": {
    "cashflow_quality": "High",
    "liquidity_pressure": "High",
    "earnings_quality": "Medium",
    "leverage_pressure": "High"
  },
  "red_flag_categories": [
    "cashflow_quality",
    "liquidity_pressure",
    "leverage_pressure"
  ],
  "why": "cash_to_short_term_debt = 0.64，interest_coverage = 1.2，最近 2 季 FCF 连续为负，且 data_staleness_days = 34。"
}
```

该例说明：

- 不是因为“高风险”而取消资格
- 而是因为已经满足了明确的近端偿债与现金消耗组合条件
