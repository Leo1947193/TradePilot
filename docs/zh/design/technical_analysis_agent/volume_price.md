# ③ 价量关系分析 — 子模块设计文档

## 1. 模块职责与边界

**职责：** 基于日线 OHLCV 数据，分析成交量与价格之间的关系，产出以下五类信号：

1. OBV 趋势方向（`obv_trend`）
2. OBV 与价格的背离（`obv_divergence`）
3. 高量突破确认（`breakout_confirmed`）
4. 高量破位确认（`breakdown_confirmed`）
5. 量价综合模式（`volume_pattern`）

**边界：**
- 仅消费日线粒度的 OHLCV，不处理周线、分钟线或盘中数据。
- 不计算均线排列、RSI、MACD 等指标——这些由 ① 多周期结构分析和 ② 动量与强度量化模块负责。
- 关键支撑位和阻力位由 ① 提供，本模块作为输入使用，不自行计算。
- 输出结构化字段，不产出自然语言解读；自然语言由聚合器统一生成。

---

## 2. 输入规格

### 2a. 日线 OHLCV

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | `date` | 交易日期 |
| `open` | `float` | 开盘价 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `close` | `float` | 收盘价 |
| `volume` | `int` | 成交量（股数） |

### 2b. 外部输入（来自 ① 多周期结构分析）

| 字段 | 类型 | 说明 |
|---|---|---|
| `key_support` | `[float]` | 关键支撑位列表（降序） |
| `key_resistance` | `[float]` | 关键阻力位列表（升序） |

### 2c. 最小数据量

- **硬性要求：** ≥60 个交易日（用于 52 周高点回溯和 OBV 背离检测的最低限度）
- **推荐：** ≥252 个交易日（1 年），以获得完整的 52 周高低点和稳定的 OBV 趋势

### 2d. 成交量异常处理

| 场景 | 处理方式 |
|---|---|
| `volume = 0` | 标记为缺失日，不纳入 OBV 累积；不纳入均量计算；该日不触发突破 / 破位判定 |
| `volume < 0` 或非整数 | 数据校验失败，抛出异常 |
| 单日成交量 > 20 日均量 × 10 | 标记为异常高量（可能除权除息或数据错误），仍参与计算但在输出中附加 `risk_flag: "abnormal_volume"` |

---

## 3. OBV 计算

### 3a. 逐日累积逻辑

OBV（On-Balance Volume）通过逐日累积成交量来衡量买卖压力：

```
OBV[0] = 0

对于每个交易日 i（i ≥ 1）：
  如果 close[i] > close[i-1]：OBV[i] = OBV[i-1] + volume[i]
  如果 close[i] < close[i-1]：OBV[i] = OBV[i-1] - volume[i]
  如果 close[i] = close[i-1]：OBV[i] = OBV[i-1]
```

> 如果某日 `volume = 0`（标记为缺失日），跳过该日，`OBV[i] = OBV[i-1]`。

### 3b. OBV 趋势判定

使用 OBV 的 **20 日简单移动均线（SMA-20）** 的斜率来判定趋势方向。

**斜率计算：** 对最近 20 日的 OBV-SMA 值进行线性回归，取回归斜率 `slope`。为消除绝对值差异，将斜率标准化：

```
normalized_slope = slope / abs(mean(OBV[last 20 days]))
```

若 `mean(OBV) = 0`，使用 `abs(OBV[-1])` 代替；若仍为 0，判定为 `flat`。

**判定规则：**

| 条件 | `obv_trend` |
|---|---|
| `normalized_slope > 0.001` | `rising` |
| `normalized_slope < -0.001` | `falling` |
| 其余 | `flat` |

> 阈值 `0.001` 表示 OBV-SMA 每日变化率约为均值的 0.1%，可根据回测结果调整。

---

## 4. OBV 背离检测算法

### 4a. 价格局部极值识别

**回溯窗口：** 最近 60 个交易日（约 3 个月）。

**局部极小值（谷）定义：** 交易日 `i` 是局部极小值，当且仅当：
- `low[i]` 是以 `i` 为中心、左右各 5 个交易日窗口内的最低价
- 即 `low[i] = min(low[i-5 : i+5])`
- 边界情况：如果距序列起点或终点不足 5 日，则使用可用的最大窗口

**局部极大值（峰）定义：** 对称定义，`high[i] = max(high[i-5 : i+5])`。

**价格"新低"：** 在回溯窗口内，最近一个局部极小值的 `low` 低于前一个局部极小值的 `low`。

**价格"新高"：** 在回溯窗口内，最近一个局部极大值的 `high` 高于前一个局部极大值的 `high`。

### 4b. OBV 局部极值识别

使用与价格相同的方法识别 OBV 的局部极值，但以 OBV 值替代价格值。窗口参数相同（中心左右各 5 日）。

**OBV "更高低点"：** 最近一个 OBV 局部极小值高于前一个 OBV 局部极小值。

**OBV "更低高点"：** 最近一个 OBV 局部极大值低于前一个 OBV 局部极大值。

### 4c. 背离确认的时间窗口和容差

- **时间对齐容差：** 价格极值与对应 OBV 极值之间的时间差 ≤ 5 个交易日。即如果价格在第 `i` 日形成局部低点，OBV 的对应局部低点必须出现在 `[i-5, i+5]` 范围内。
- **极值对数要求：** 至少需要两对时间上对齐的（价格极值, OBV 极值）才能形成背离判定。
- **幅度容差：** 价格"新低 / 新高"要求差值 > 当前价格的 0.5%，避免噪声触发。OBV 极值差的方向性是关键判据，不设绝对幅度阈值。

### 4d. 看涨背离判定流程

```
1. 在最近 60 个交易日中，找到所有价格局部极小值 P1, P2（P1 较早，P2 较近）
2. 在最近 60 个交易日中，找到所有 OBV 局部极小值 O1, O2（O1 较早，O2 较近）
3. 检查时间对齐：|P1.date - O1.date| ≤ 5 且 |P2.date - O2.date| ≤ 5
4. 检查价格新低：P2.low < P1.low 且 (P1.low - P2.low) / P1.low > 0.005
5. 检查 OBV 更高低点：O2.value > O1.value
6. 若 3、4、5 均满足 → obv_divergence = "bullish"
```

### 4e. 看跌背离判定流程

```
1. 在最近 60 个交易日中，找到所有价格局部极大值 P1, P2（P1 较早，P2 较近）
2. 在最近 60 个交易日中，找到所有 OBV 局部极大值 O1, O2（O1 较早，O2 较近）
3. 检查时间对齐：|P1.date - O1.date| ≤ 5 且 |P2.date - O2.date| ≤ 5
4. 检查价格新高：P2.high > P1.high 且 (P2.high - P1.high) / P1.high > 0.005
5. 检查 OBV 更低高点：O2.value < O1.value
6. 若 3、4、5 均满足 → obv_divergence = "bearish"
```

> 如果同时检测到看涨和看跌背离（极少见），优先取距今更近的那一组。若无任何背离，`obv_divergence = "none"`。

---

## 5. 成交量均线与量比

### 5a. 20 日均量

```
vol_ma20[i] = mean(volume[i-19 : i+1])
```

- 仅包含 `volume > 0` 的交易日。如果 20 日窗口内有效日数 < 15，标记当日均量为不可靠，不进行突破 / 破位的量能确认。

### 5b. 量比

```
volume_ratio[i] = volume[i] / vol_ma20[i]
```

| 量比范围 | 含义 |
|---|---|
| `> 2.0` | 极度放量 |
| `> 1.5` | 显著放量（突破 / 破位确认阈值） |
| `0.7 ~ 1.5` | 正常 |
| `< 0.7` | 缩量 |
| `< 0.5` | 极度缩量 |

---

## 6. 突破 / 破位检测

### 6a. 突破（Breakout）

**定义：** 收盘价突破关键阻力位或近 52 周高点，且伴随充足量能。

**判定流程：**

```
1. 取 key_resistance 中最接近当前价格的阻力位 R（从 ① 模块获取）
2. 计算近 52 周最高价 high_52w = max(high[last 252 trading days])
3. 突破目标价 breakout_level = min(R, high_52w)
   - 如果 key_resistance 为空，仅使用 high_52w
4. 突破条件：
   a. close[today] > breakout_level
   b. volume_ratio[today] > 1.5（量能确认）
5. 假突破过滤：
   要求最近 3 个交易日（含今日）中至少 2 日满足 close > breakout_level
   - 即 count(close[today-2 : today+1] > breakout_level) ≥ 2
6. 若 4a、4b、5 均满足 → breakout_confirmed = true
```

### 6b. 破位（Breakdown）

**定义：** 收盘价跌破关键支撑位，且伴随充足量能。

**判定流程：**

```
1. 取 key_support 中最接近当前价格的支撑位 S（从 ① 模块获取）
2. 如果 key_support 为空，不进行破位检测，breakdown_confirmed = false
3. 破位条件：
   a. close[today] < S
   b. volume_ratio[today] > 1.5（量能确认）
4. 假破位过滤：
   要求最近 3 个交易日（含今日）中至少 2 日满足 close < S
   - 即 count(close[today-2 : today+1] < S) ≥ 2
5. 若 3a、3b、4 均满足 → breakdown_confirmed = true
```

### 6c. 互斥规则

`breakout_confirmed` 和 `breakdown_confirmed` 不能同时为 `true`。若出现逻辑冲突（理论上不应发生），优先取今日收盘价方向对应的信号。

---

## 7. 低量回调与弱反弹

### 7a. 回调日识别

**回调日定义：** 在上升趋势背景下（`obv_trend = rising` 或由 ① 模块给出 `trend_daily = bullish`），出现价格下跌的交易日：

```
close[i] < close[i-1]
```

连续回调：连续 ≥ 2 个回调日视为一次回调事件。

### 7b. 反弹日识别

**反弹日定义：** 在下降趋势背景下（`obv_trend = falling` 或由 ① 模块给出 `trend_daily = bearish`），出现价格上涨的交易日：

```
close[i] > close[i-1]
```

连续反弹：连续 ≥ 2 个反弹日视为一次反弹事件。

### 7c. "低量"阈值

```
低量 = volume_ratio < 0.7
```

即当日成交量低于 20 日均量的 70%。

### 7d. 判定条件

**`pullback_healthy`（低量回调 → 健康）：**
- 最近一次回调事件中，回调日的平均量比 < 0.7
- 且回调幅度（回调起点收盘价到回调最低收盘价）≤ 5%
- 含义：上升趋势中的缩量回调，卖压不足，趋势大概率延续

**`bounce_weak`（低量反弹 → 弱势）：**
- 最近一次反弹事件中，反弹日的平均量比 < 0.7
- 且反弹幅度（反弹起点收盘价到反弹最高收盘价）≤ 5%
- 含义：下降趋势中的缩量反弹，买压不足，趋势大概率延续

> "最近一次"指最近 10 个交易日内发生的回调 / 反弹事件。若无此类事件，不输出 `pullback_healthy` 或 `bounce_weak`。

---

## 8. volume_pattern 综合判定

`volume_pattern` 是本模块的综合量价模式判定，按以下优先级依次匹配（首个匹配即输出）：

| 优先级 | 值 | 条件 |
|---|---|---|
| 1 | `accumulation` | 以下条件全部满足：① `obv_trend = rising`；② 最近 20 日中，上涨日（`close > prev_close`）的平均成交量 > 下跌日的平均成交量 × 1.2；③ 无 `breakdown_confirmed` |
| 2 | `distribution` | 以下条件全部满足：① `obv_trend = falling`；② 最近 20 日中，下跌日的平均成交量 > 上涨日的平均成交量 × 1.2；③ 无 `breakout_confirmed` |
| 3 | `pullback_healthy` | 满足第 7d 节的 `pullback_healthy` 条件 |
| 4 | `bounce_weak` | 满足第 7d 节的 `bounce_weak` 条件 |
| 5 | `neutral` | 以上条件均不满足 |

**补充说明：**
- `accumulation`（吸筹）与 `distribution`（派发）关注的是中期量价结构，反映机构行为。
- `pullback_healthy` 与 `bounce_weak` 关注的是短期量价事件，反映趋势延续质量。
- 如果 `breakout_confirmed = true`，`volume_pattern` 仍按上述规则判定——突破本身不直接决定 `volume_pattern`。

---

## 9. 输出字段

| 字段 | 类型 | 取值范围 | 说明 |
|---|---|---|---|
| `obv_trend` | `string` | `rising \| falling \| flat` | OBV 的 20 日均线趋势方向 |
| `obv_divergence` | `string` | `bullish \| bearish \| none` | OBV 与价格的背离状态 |
| `breakout_confirmed` | `boolean` | `true \| false` | 是否确认高量突破 |
| `breakdown_confirmed` | `boolean` | `true \| false` | 是否确认高量破位 |
| `volume_pattern` | `string` | `accumulation \| distribution \| neutral \| pullback_healthy \| bounce_weak` | 综合量价模式 |

**聚合器消费规则（来自 overview）：**
- `bullish`：`breakout_confirmed = true`，或 `accumulation` + `obv_divergence = bullish`
- `bearish`：`breakdown_confirmed = true`，或 `distribution` + `obv_divergence = bearish`
- `neutral`：其余情况

---

## 10. 示例

### 示例 A：看涨背离

某股票最近 60 个交易日的关键数据点：

| 日期 | 事件 | 收盘价 | 最低价 | 成交量 | OBV |
|---|---|---|---|---|---|
| Day 20 | 价格局部低点 P1 | 48.50 | **47.80** | 3,200,000 | -5,600,000 |
| Day 21 | OBV 局部低点 O1 | 48.90 | 48.60 | 2,800,000 | **-5,800,000** |
| Day 45 | 价格局部低点 P2 | 47.00 | **46.50** | 2,100,000 | -4,200,000 |
| Day 44 | OBV 局部低点 O2 | 47.30 | 47.00 | 1,900,000 | **-4,500,000** |

**验证：**
1. 时间对齐：|P1.date - O1.date| = 1 ≤ 5 ✓；|P2.date - O2.date| = 1 ≤ 5 ✓
2. 价格新低：P2.low (46.50) < P1.low (47.80)，差值 = 2.72% > 0.5% ✓
3. OBV 更高低点：O2.value (-4,500,000) > O1.value (-5,800,000) ✓

**结论：** `obv_divergence = "bullish"` — 价格创新低但 OBV 未创新低，表明抛售力量正在减弱。

若此时 `obv_trend = rising` 且上涨日均量 > 下跌日均量 × 1.2，则 `volume_pattern = "accumulation"`。
结合聚合规则：`accumulation` + 看涨背离 → 价量信号 = **bullish**。

---

### 示例 B：高量突破

| 参数 | 值 |
|---|---|
| 近 52 周最高价 | 152.30 |
| 最近阻力位（来自 ①） | 150.00 |
| `breakout_level` | min(150.00, 152.30) = **150.00** |
| 20 日均量 | 4,000,000 |

| 日期 | 收盘价 | 成交量 | 量比 | close > 150.00? |
|---|---|---|---|---|
| Day T-2 | 149.80 | 3,500,000 | 0.88 | 否 |
| Day T-1 | 150.50 | 5,200,000 | 1.30 | 是 |
| Day T（今日） | 153.20 | **7,800,000** | **1.95** | 是 |

**验证：**
1. 收盘价突破：close[T] (153.20) > breakout_level (150.00) ✓
2. 量能确认：volume_ratio[T] (1.95) > 1.5 ✓
3. 假突破过滤：最近 3 日中 2 日收盘价 > 150.00（Day T-1, Day T）≥ 2 ✓

**结论：** `breakout_confirmed = true`。
结合聚合规则：`breakout_confirmed = true` → 价量信号 = **bullish**。
