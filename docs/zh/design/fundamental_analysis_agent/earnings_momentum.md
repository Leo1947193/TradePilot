# 盈利动量分析器

## 1. 模块目标与边界

### 1.1 模块目标

盈利动量分析器服务于 **14 到 60 天** 的中期交易窗口，目标是回答以下问题：

1. 公司最近几个季度的盈利兑现是否稳定
2. 市场对当前季度的预期是在上修、持平还是下修
3. 管理层指引是否在强化或削弱近端盈利趋势

模块输出必须满足以下要求：

- 仅输出 **结构化、确定性、可追溯** 的结果
- 同一份输入在同一规则版本下必须产生同一输出
- 不输出买卖指令，只输出可供上层聚合的盈利动量信号

### 1.2 范围内

- 最近 4 到 8 个季度的 EPS 与营收兑现情况
- 最近 30 / 60 天卖方一致预期修正方向
- 最近 2 次管理层量化指引变化
- 当前季度预期门槛的高低判断

### 1.3 范围外

- 催化剂识别、事件强度判断、财报日博弈
- 新闻情绪、社媒情绪、期权情绪
- 分析师升级 / 降级事件解读
- 长周期盈利预测、行业景气度研究、估值判断

说明：

- 催化剂与事件归属 **事件分析模块**
- 新闻与预期情绪归属 **情绪分析模块**
- 财务健康与估值归属 **基本面模块其他子分析器**

---

## 2. 输入定义

### 2.1 基础上下文

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ticker` | `string` | 是 | 股票代码 |
| `analysis_timestamp` | `ISO 8601` | 是 | 本次分析执行时间 |
| `target_horizon_days` | `number[2]` | 是 | 固定为 `[14, 60]` |

### 2.2 季度结果输入 `quarterly_results[]`

至少提供最近 8 个季度，按 `fiscal_period_end` 可排序。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `fiscal_year` | `number` | 是 | 财年 |
| `fiscal_quarter` | `1-4` | 是 | 财季 |
| `fiscal_period_end` | `date` | 是 | 季度结束日 |
| `report_date` | `date` | 是 | 实际财报发布日期 |
| `eps_actual` | `number` | 是 | 实际 EPS，需与一致预期口径一致 |
| `eps_consensus_pre_report` | `number` | 是 | 财报发布前最近可用的一致 EPS 预期 |
| `revenue_actual` | `number` | 是 | 实际营收 |
| `revenue_consensus_pre_report` | `number` | 是 | 财报发布前最近可用的一致营收预期 |
| `currency` | `string` | 是 | 货币单位，营收必须同币种 |
| `source` | `string` | 是 | 数据源名称 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

### 2.3 一致预期修正输入 `revision_summary`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `eps_up_30d` | `number` | 是 | 过去 30 天 EPS 上调人数 |
| `eps_down_30d` | `number` | 是 | 过去 30 天 EPS 下调人数 |
| `eps_up_60d` | `number` | 是 | 过去 60 天 EPS 上调人数 |
| `eps_down_60d` | `number` | 是 | 过去 60 天 EPS 下调人数 |
| `revenue_up_30d` | `number` | 是 | 过去 30 天营收上调人数 |
| `revenue_down_30d` | `number` | 是 | 过去 30 天营收下调人数 |
| `as_of_date` | `date` | 是 | 修正统计对应日期 |
| `source` | `string` | 是 | 数据源名称 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

说明：

- 若数据源明确返回 `0` 上调、`0` 下调，视为 **有效中性数据**
- 若字段本身缺失、无法获取或来源不可验证，视为 **缺失数据**

### 2.4 当前季度一致预期快照 `current_quarter_consensus`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `eps_consensus_now` | `number` | 是 | 当前季度最新 EPS 一致预期 |
| `eps_consensus_30d_ago` | `number` | 是 | 30 天前 EPS 一致预期 |
| `source` | `string` | 是 | 数据源名称 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

说明：

- `current_quarter_bar` 只强制依赖 EPS 一致预期变化，不新增额外对外输出字段
- 若后续实现中可稳定取得营收一致预期时间序列，可作为内部校验字段，但不纳入 v1 输出

### 2.5 管理层指引输入 `guidance_history[]`

仅使用最近 2 次、且 **同一预测口径** 的量化指引。

优先级固定如下：

1. 当前财季指引
2. 下一财季指引
3. 当前财年指引

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `guidance_horizon` | `CurrentQuarter | NextQuarter | FiscalYear` | 是 | 指引覆盖周期 |
| `metric_type` | `EPS | Revenue` | 是 | 指引指标类型 |
| `low` | `number | null` | 否 | 指引下限 |
| `high` | `number | null` | 否 | 指引上限 |
| `issued_at` | `date` | 是 | 指引发布时间 |
| `explicit_no_guidance` | `boolean` | 是 | 管理层是否明确表示不给量化指引 |
| `source` | `string` | 是 | 数据源名称 |
| `fetched_at` | `ISO 8601` | 是 | 抓取时间 |

---

## 3. 数据预处理规则

### 3.1 季度数据标准化

1. 按 `fiscal_period_end` 降序排序，保留最近 8 个季度。
2. 以 `fiscal_year + fiscal_quarter` 为唯一键去重。
3. 若同一季度存在多条记录，优先级固定为：
   - `report_date` 更完整者优先
   - `fetched_at` 更新者优先
   - 主数据源优先于备用源
4. EPS 实际值与一致预期必须使用同一拆股调整口径；若无法确认口径一致，该季度 EPS 不参与 surprise 计算。
5. 营收币种必须一致；若币种不一致且无可信汇率映射，该季度营收不参与 surprise 计算。

### 3.2 财报前一致预期快照规则

- `eps_consensus_pre_report` 与 `revenue_consensus_pre_report` 必须来自 `report_date` 之前最近的可用快照。
- 若最近快照距离 `report_date` 超过 5 个自然日，则该季度对应字段记为无效，不参与 surprise 计算。
- 不允许使用财报发布后的修正值回填财报前预期。

### 3.3 有效季度判定

满足以下条件的季度才可用于 surprise 计算：

- `report_date`、`actual`、`consensus_pre_report` 均存在
- 数值口径一致
- 来源可追溯

有效 EPS 季度和有效营收季度分别独立判定，不相互替代。

### 3.4 内部辅助字段

以下字段用于标签判断，不要求进入对外 schema：

```text
eps_surprise_pct(q) =
  ((eps_actual(q) - eps_consensus_pre_report(q))
   / max(abs(eps_consensus_pre_report(q)), 0.01)) * 100

revenue_surprise_pct(q) =
  ((revenue_actual(q) - revenue_consensus_pre_report(q))
   / max(abs(revenue_consensus_pre_report(q)), 1)) * 100

eps_consensus_change_pct_30d =
  ((eps_consensus_now - eps_consensus_30d_ago)
   / max(abs(eps_consensus_30d_ago), 0.01)) * 100
```

预处理要求：

- 所有百分比字段保留 2 位小数
- `eps_surprise_pct(q)` 与 `revenue_surprise_pct(q)` 计算后裁剪到 `[-100.00, 100.00]`
- `eps_consensus_change_pct_30d` 不裁剪

### 3.5 指引配对规则

1. 仅允许比较同一 `guidance_horizon`、同一 `metric_type` 的相邻两次量化指引。
2. 指引区间中点定义为：

```text
guidance_midpoint = (low + high) / 2
```

3. 若只有单边值，则以该值视为中点。
4. 若最近一次记录 `explicit_no_guidance = true`，则直接判定为 `NoGuidance`，不再与上一次配对比较。
5. 若最近两次记录都不是量化指引，且均为 `explicit_no_guidance = true`，则判定为 `NoGuidance`。

---

## 4. 核心指标定义

### 4.1 `eps_beat_streak_quarters`

定义：从最近一个已披露季度开始，连续满足 `eps_surprise_pct(q) > 0` 的季度数。

规则：

- `eps_surprise_pct(q) = 0` 不算 beat，会中断 streak
- 某季度 EPS surprise 无法计算时，连续计数在该季度终止
- 仅向后连续统计，不做跳跃式补洞

示例：

- 最近 4 季 EPS surprise 为 `4.1% / 2.3% / -1.2% / 6.0%`
- `eps_beat_streak_quarters = 2`

### 4.2 `avg_eps_surprise_pct_4q`

定义：最近 4 个 **有效 EPS 季度** 的 `eps_surprise_pct(q)` 算术平均值。

规则：

- 有效季度数为 `4` 时，正常计算
- 有效季度数为 `3` 或 `2` 时，使用现有有效季度计算，并记为降级结果
- 有效季度数 `< 2` 时，不计算该指标

### 4.3 `avg_revenue_surprise_pct_4q`

定义：最近 4 个 **有效营收季度** 的 `revenue_surprise_pct(q)` 算术平均值。

规则与 EPS surprise 相同。

### 4.4 `eps_revision_balance_30d`

定义：

```text
eps_revision_balance_30d =
  (eps_up_30d - eps_down_30d)
  / max(eps_up_30d + eps_down_30d, 1)
```

边界值：

- 取值范围固定为 `[-1.00, 1.00]`
- `1.00` 表示全部为上修
- `-1.00` 表示全部为下修
- `0.00` 表示修正平衡，或明确无修正事件

### 4.5 `eps_revision_balance_60d`

定义与 `eps_revision_balance_30d` 相同，只是窗口替换为 60 天。

### 4.6 `revenue_revision_balance_30d`

定义：

```text
revenue_revision_balance_30d =
  (revenue_up_30d - revenue_down_30d)
  / max(revenue_up_30d + revenue_down_30d, 1)
```

边界值与 EPS revision balance 相同。

### 4.7 `guidance_trend`

输出枚举：`Raised | Maintained | Lowered | NoGuidance`

判定顺序固定如下：

1. 最近一次记录 `explicit_no_guidance = true`，输出 `NoGuidance`
2. 若可比较的最新两次量化指引中，任一指标中点变化 `<= -2.00%`，输出 `Lowered`
3. 若不存在 `Lowered`，且任一指标中点变化 `>= 2.00%`，输出 `Raised`
4. 若所有可比较指标的中点变化都在 `(-2.00%, 2.00%)` 内，输出 `Maintained`
5. 若没有可比较量化指引，但公司明确不提供量化指引，输出 `NoGuidance`
6. 其余情况视为数据缺失，不在本字段中硬编码，转由第 7 节降级规则处理

冲突处理：

- EPS 指引与营收指引同时存在且方向冲突时，`Lowered` 优先级高于 `Raised`
- 只有在不存在任何下调时，才允许输出 `Raised`

### 4.8 `current_quarter_bar`

输出枚举：`High | Normal | Low`

该字段表示 **当前季度市场预期门槛**，不是公司经营质量本身。

使用以下 3 个信号投票：

1. `eps_consensus_change_pct_30d >= 5.00` 记 1 个 `High` 票
2. `eps_revision_balance_30d >= 0.50` 记 1 个 `High` 票
3. `revenue_revision_balance_30d >= 0.25` 记 1 个 `High` 票

1. `eps_consensus_change_pct_30d <= -5.00` 记 1 个 `Low` 票
2. `eps_revision_balance_30d <= -0.50` 记 1 个 `Low` 票
3. `revenue_revision_balance_30d <= -0.25` 记 1 个 `Low` 票

判定规则：

- 至少有 2 个有效信号时：
  - `High` 票 `>= 2` → `High`
  - `Low` 票 `>= 2` → `Low`
  - 其余 → `Normal`
- 有效信号 `< 2` 时，强制输出 `Normal`，并降低置信度

### 4.9 `earnings_momentum`

输出枚举：`Accelerating | Stable | Decelerating`

判定顺序固定如下：

1. 先判定 `Decelerating`
   - `guidance_trend = Lowered`
   - 或 `eps_revision_balance_30d <= -0.25`
   - 或 `avg_eps_surprise_pct_4q < 0` 且 `avg_revenue_surprise_pct_4q < 0`
2. 若不满足 1，再判定 `Accelerating`
   - `avg_eps_surprise_pct_4q >= 2.00`
   - 且 `eps_revision_balance_30d >= 0.25`
   - 且 `guidance_trend != Lowered`
   - 且满足以下任一条件：
     - `eps_beat_streak_quarters >= 2`
     - `eps_revision_balance_30d > eps_revision_balance_60d`
3. 其余情况输出 `Stable`

约束：

- 若最新财报发布日期距 `analysis_timestamp` 超过 140 天，则不得输出 `Accelerating`
- 若 30 天 EPS 修正数据缺失或过期，则不得输出 `Accelerating`

### 4.10 `earnings_score`

`earnings_score` 为 `0-100` 的整数分数，默认由 4 个子分项组成：

```text
earnings_score =
  beat_quality_score      (0-30) +
  revision_signal_score   (0-35) +
  revenue_confirmation    (0-15) +
  guidance_score          (0-20)
```

完整映射规则见第 6 节。

---

## 5. 标签生成规则

### 5.1 `guidance_trend` 标签表

| 条件 | 输出标签 |
|---|---|
| 最新一次明确不给量化指引 | `NoGuidance` |
| 任一可比较指引中点变化 `<= -2.00%` | `Lowered` |
| 不存在 `Lowered`，且任一可比较指引中点变化 `>= 2.00%` | `Raised` |
| 所有可比较中点变化在 `(-2.00%, 2.00%)` 内 | `Maintained` |

### 5.2 `current_quarter_bar` 标签表

| 条件 | 输出标签 |
|---|---|
| 3 个信号中至少 2 个满足 `High` 条件 | `High` |
| 3 个信号中至少 2 个满足 `Low` 条件 | `Low` |
| 其余情况 | `Normal` |

### 5.3 `earnings_momentum` 标签表

| 优先级 | 条件 | 输出标签 |
|---|---|---|
| 1 | `guidance_trend = Lowered` | `Decelerating` |
| 2 | `eps_revision_balance_30d <= -0.25` | `Decelerating` |
| 3 | `avg_eps_surprise_pct_4q < 0` 且 `avg_revenue_surprise_pct_4q < 0` | `Decelerating` |
| 4 | `avg_eps_surprise_pct_4q >= 2.00` 且 `eps_revision_balance_30d >= 0.25` 且 `guidance_trend != Lowered` 且 (`eps_beat_streak_quarters >= 2` 或 `eps_revision_balance_30d > eps_revision_balance_60d`) | `Accelerating` |
| 5 | 以上都不满足 | `Stable` |

说明：

- 标签判定是 **顺序执行**，命中更高优先级后立即停止
- `Decelerating` 的优先级高于 `Accelerating`
- `current_quarter_bar` 不直接决定 `earnings_momentum`，只用于刻画兑现门槛

---

## 6. 评分规则

### 6.1 `beat_quality_score` 映射

由两个部分组成：

```text
beat_quality_score =
  streak_score        (0-15) +
  eps_surprise_score  (0-15)
```

`streak_score`：

| `eps_beat_streak_quarters` | 分值 |
|---|---|
| `>= 4` | `15` |
| `3` | `12` |
| `2` | `8` |
| `1` | `4` |
| `0` | `0` |

`eps_surprise_score`：

| `avg_eps_surprise_pct_4q` | 分值 |
|---|---|
| `>= 10.00` | `15` |
| `[5.00, 10.00)` | `12` |
| `[2.00, 5.00)` | `9` |
| `[0.00, 2.00)` | `6` |
| `[-2.00, 0.00)` | `3` |
| `< -2.00` | `0` |

### 6.2 `revision_signal_score` 映射

由三个部分组成：

```text
revision_signal_score =
  eps_revision_30d_score   (0-20) +
  eps_revision_60d_score   (0-10) +
  revision_consistency     (0-5)
```

`eps_revision_30d_score`：

| `eps_revision_balance_30d` | 分值 |
|---|---|
| `>= 0.50` | `20` |
| `[0.25, 0.50)` | `16` |
| `[0.10, 0.25)` | `12` |
| `(-0.10, 0.10)` | `8` |
| `[-0.25, -0.10]` | `4` |
| `< -0.25` | `0` |

`eps_revision_60d_score`：

| `eps_revision_balance_60d` | 分值 |
|---|---|
| `>= 0.50` | `10` |
| `[0.25, 0.50)` | `8` |
| `[0.10, 0.25)` | `6` |
| `(-0.10, 0.10)` | `4` |
| `[-0.25, -0.10]` | `2` |
| `< -0.25` | `0` |

`revision_consistency`：

| 条件 | 分值 |
|---|---|
| `eps_revision_balance_30d >= 0.25` 且 `eps_revision_balance_60d >= 0.10` | `5` |
| `eps_revision_balance_30d > eps_revision_balance_60d` 且 `eps_revision_balance_30d > 0` | `3` |
| `abs(eps_revision_balance_30d - eps_revision_balance_60d) < 0.10` | `2` |
| 其余 | `0` |

### 6.3 `revenue_confirmation` 映射

由两个部分组成：

```text
revenue_confirmation =
  revenue_surprise_score   (0-10) +
  revenue_revision_score   (0-5)
```

`revenue_surprise_score`：

| `avg_revenue_surprise_pct_4q` | 分值 |
|---|---|
| `>= 4.00` | `10` |
| `[1.00, 4.00)` | `7` |
| `[-1.00, 1.00)` | `5` |
| `[-4.00, -1.00)` | `2` |
| `< -4.00` | `0` |

`revenue_revision_score`：

| `revenue_revision_balance_30d` | 分值 |
|---|---|
| `>= 0.25` | `5` |
| `[0.00, 0.25)` | `3` |
| `[-0.25, 0.00)` | `1` |
| `< -0.25` | `0` |

### 6.4 `guidance_score` 映射

| `guidance_trend` | 分值 |
|---|---|
| `Raised` | `20` |
| `Maintained` | `12` |
| `NoGuidance` | `6` |
| `Lowered` | `0` |

说明：

- `NoGuidance` 是公司真实状态，不等于数据缺失
- 为避免与预期修正重复计分，`current_quarter_bar` 不直接计入 `earnings_score`

### 6.5 完整数据下的总分计算

当 4 个子分项都可计算时：

```text
earnings_score =
  beat_quality_score +
  revision_signal_score +
  revenue_confirmation +
  guidance_score
```

输出要求：

- `earnings_score` 四舍五入为整数
- 结果限制在 `[0, 100]`

---

## 7. 缺失数据与过期数据处理

### 7.1 关键字段定义

以下字段组属于 **关键字段**：

| 关键字段组 | 字段 |
|---|---|
| `eps_surprise_core` | 最近 4 个有效季度的 `eps_actual`、`eps_consensus_pre_report` |
| `revenue_surprise_core` | 最近 4 个有效季度的 `revenue_actual`、`revenue_consensus_pre_report` |
| `eps_revision_core` | `eps_up_30d`、`eps_down_30d`、`eps_up_60d`、`eps_down_60d` |
| `revenue_revision_core` | `revenue_up_30d`、`revenue_down_30d` |
| `guidance_core` | 最近 2 次同口径量化指引，或明确 `explicit_no_guidance` |
| `current_quarter_consensus_core` | `eps_consensus_now`、`eps_consensus_30d_ago` |

### 7.2 过期阈值

| 数据类型 | 新鲜 | 警告 | 过期 |
|---|---|---|---|
| 最新财报结果 | `<= 100` 天 | `101-140` 天 | `> 140` 天 |
| 修正统计快照 | `<= 7` 天 | `8-14` 天 | `> 14` 天 |
| 当前季度一致预期快照 | `<= 7` 天 | `8-14` 天 | `> 14` 天 |
| 指引记录 | 跟随最新财报窗口 | 跟随最新财报窗口 | 最新财报已过期时同步过期 |

### 7.3 降级规则

#### 7.3.1 季度结果不完整

- 最近 4 季中：
  - 有效 EPS 季度数为 `3` 或 `2`：允许计算 `avg_eps_surprise_pct_4q`，但标记降级
  - 有效 EPS 季度数 `< 2`：`beat_quality_score` 不可计算
  - 有效营收季度数为 `3` 或 `2`：允许计算 `avg_revenue_surprise_pct_4q`，但标记降级
  - 有效营收季度数 `< 2`：`revenue_surprise_score` 不可计算

#### 7.3.2 分析师修正数据缺失

- 缺 `eps_revision_balance_30d`：
  - 不得输出 `Accelerating`
  - `eps_revision_30d_score = unavailable`
  - `revision_consistency = 0`
- 缺 `eps_revision_balance_60d`：
  - `eps_revision_60d_score = unavailable`
  - `revision_consistency` 仅允许取 `0`
- 缺 `revenue_revision_balance_30d`：
  - `revenue_revision_score = unavailable`
  - `current_quarter_bar` 少 1 个投票信号
- 30 天与 60 天 EPS 修正同时缺失：
  - `revision_signal_score = unavailable`
  - `current_quarter_bar` 最多只能输出 `Normal`

#### 7.3.3 管理层不给指引

- 若公司明确不给量化指引：
  - `guidance_trend = NoGuidance`
  - `guidance_score = 6`
  - 不计入数据缺失惩罚

#### 7.3.4 指引数据缺失

- 若无法判断公司是否给出量化指引，且缺少可比历史记录：
  - `guidance_score = unavailable`
  - `guidance_trend` 使用 `NoGuidance` 会误导，因此必须附带 `guidance_data_missing = true`
  - `earnings_momentum` 不得输出 `Accelerating`

#### 7.3.5 数据过期

- 最新财报结果过期：
  - `earnings_momentum` 不得输出 `Accelerating`
  - `earnings_score` 上限强制为 `60`
- 修正统计或当前季度预期快照过期：
  - `current_quarter_bar = Normal`
  - 所有依赖过期修正数据的子分项视为 `unavailable`

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
| `beat_quality_score` unavailable | `15` |
| `revision_signal_score` unavailable | `15` |
| `revenue_confirmation` unavailable | `5` |
| `guidance_score` unavailable | `5` |
| `current_quarter_bar` 因数据不足被强制 `Normal` | `5` |

最终：

```text
earnings_score =
  clamp(round(normalized_score - missing_penalty), 0, 100)
```

若 `available_score_cap < 60`，则强制回退为：

- `earnings_score = 50`
- `earnings_momentum = Stable`
- `confidence_level = Low`

### 7.5 置信度计算

初始值固定为 `1.00`，按下表扣减：

| 条件 | 扣减 |
|---|---|
| 最新财报结果处于警告区间 | `0.10` |
| 最新财报结果过期 | `0.20` |
| 缺 1 个有效 EPS 季度 | `0.10` |
| 缺 1 个有效营收季度 | `0.05` |
| 缺 30 天 EPS 修正 | `0.15` |
| 缺 60 天 EPS 修正 | `0.10` |
| 缺 30 天营收修正 | `0.10` |
| 缺当前季度 EPS 一致预期对比快照 | `0.05` |
| 缺可比指引记录且无法确认是否 NoGuidance | `0.10` |

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

- 本节 Schema 仅用于 `earnings_momentum` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

```json
{
  "schema_version": "1.0",
  "ticker": "string",
  "analysis_timestamp": "ISO 8601",
  "module": "EarningsMomentumAnalyzerV1",
  "staleness_days": "number",
  "missing_fields": ["string"],
  "metrics": {
    "eps_beat_streak_quarters": "number | null",
    "avg_eps_surprise_pct_4q": "number | null",
    "avg_revenue_surprise_pct_4q": "number | null",
    "eps_revision_balance_30d": "number | null",
    "eps_revision_balance_60d": "number | null",
    "revenue_revision_balance_30d": "number | null",
    "guidance_trend": "Raised | Maintained | Lowered | NoGuidance | null",
    "current_quarter_bar": "High | Normal | Low",
    "earnings_momentum": "Accelerating | Stable | Decelerating",
    "earnings_score": "number"
  },
  "subscores": {
    "beat_quality_score": "number | null",
    "revision_signal_score": "number | null",
    "revenue_confirmation": "number | null",
    "guidance_score": "number | null"
  },
  "confidence": {
    "confidence_score": "number",
    "confidence_level": "High | Medium | Low",
    "critical_missing_fields": ["string"],
    "stale_fields": ["string"]
  },
  "flags": {
    "guidance_data_missing": "boolean",
    "used_degraded_quarter_set": "boolean",
    "used_normalized_scoring": "boolean"
  },
  "source_trace": [
    {
      "dataset": "quarterly_results | revision_summary | current_quarter_consensus | guidance_history",
      "source": "string",
      "fetched_at": "ISO 8601",
      "staleness_days": "number",
      "missing_fields": ["string"]
    }
  ]
}
```

约束：

- 对外输出中的百分比字段统一保留 2 位小数
- `earnings_score` 输出整数
- `critical_missing_fields` 仅列关键字段组名，不列自然语言推断

---

## 9. 实现约束与示例

### 9.1 实现约束

1. 所有阈值必须硬编码在规则层，不允许由模型自由决定。
2. 所有标签先算指标、再按顺序命中规则，不允许直接从文本生成标签。
3. `Lowered` 优先级高于 `Raised`，`Decelerating` 优先级高于 `Accelerating`。
4. `current_quarter_bar` 只表达市场门槛，不直接进分，避免与修正数据重复计分。
5. 只允许使用财报前一致预期，不允许混入财报后修正值。
6. 不允许因文本摘要缺失而回填结构化字段。
7. 若数据不足，必须走第 7 节回退逻辑，不允许输出“由模型判断”。

### 9.2 JSON 输出示例

```json
{
  "schema_version": "1.0",
  "ticker": "NVDA",
  "analysis_timestamp": "2026-04-16T10:30:00Z",
  "module": "EarningsMomentumAnalyzerV1",
  "staleness_days": 1,
  "missing_fields": [],
  "metrics": {
    "eps_beat_streak_quarters": 4,
    "avg_eps_surprise_pct_4q": 8.46,
    "avg_revenue_surprise_pct_4q": 3.12,
    "eps_revision_balance_30d": 0.58,
    "eps_revision_balance_60d": 0.31,
    "revenue_revision_balance_30d": 0.27,
    "guidance_trend": "Raised",
    "current_quarter_bar": "High",
    "earnings_momentum": "Accelerating",
    "earnings_score": 86
  },
  "subscores": {
    "beat_quality_score": 27,
    "revision_signal_score": 31,
    "revenue_confirmation": 8,
    "guidance_score": 20
  },
  "confidence": {
    "confidence_score": 0.93,
    "confidence_level": "High",
    "critical_missing_fields": [],
    "stale_fields": []
  },
  "flags": {
    "guidance_data_missing": false,
    "used_degraded_quarter_set": false,
    "used_normalized_scoring": false
  },
  "source_trace": [
    {
      "dataset": "quarterly_results",
      "source": "primary_fundamental_feed",
      "fetched_at": "2026-04-16T10:05:00Z",
      "staleness_days": 1,
      "missing_fields": []
    },
    {
      "dataset": "revision_summary",
      "source": "primary_estimate_feed",
      "fetched_at": "2026-04-16T10:06:00Z",
      "staleness_days": 0,
      "missing_fields": []
    },
    {
      "dataset": "current_quarter_consensus",
      "source": "primary_estimate_feed",
      "fetched_at": "2026-04-16T10:06:00Z",
      "staleness_days": 0,
      "missing_fields": []
    },
    {
      "dataset": "guidance_history",
      "source": "company_filings",
      "fetched_at": "2026-04-16T10:08:00Z",
      "staleness_days": 1,
      "missing_fields": []
    }
  ]
}
```

该示例表示：

- 最近 4 季盈利兑现稳定且持续超预期
- 近 30 天修正强于 60 天，说明预期仍在继续上修
- 管理层指引上调，且当前季度门槛偏高
- 即使 `current_quarter_bar = High`，也不会重复加分，只通过风险与标签体现
