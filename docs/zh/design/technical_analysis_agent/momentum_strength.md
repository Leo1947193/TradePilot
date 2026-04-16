# ② 动量与强度量化 — 子模块设计文档

> 本文档是技术分析模块 [overview.md](./overview.md) 中"② 动量与强度量化"子 Agent 的详细设计。文档目标：给出可直接实现的完整计算规则、阈值定义与边界情况处理。

---

## 1. 模块职责与边界

**职责：**
- 接收个股与基准 ETF 的日线 OHLCV 数据，计算 RSI、MACD、ADX、相对强度四类动量指标。
- 对每个指标输出数值与分类信号，并生成一句话 `momentum_summary`。
- 输出结构化字段供下游聚合器、形态识别模块（④）、风险指标模块（⑤）消费。

**边界：**
- 本模块**不**负责均线排列、支撑阻力（属于 ① 多周期结构分析）。
- 本模块**不**负责成交量分析、OBV、突破/破位确认（属于 ③ 价量关系分析）。
- 本模块**不**生成最终方向结论 `technical_signal`；它只输出子信号，由聚合器综合。
- 本模块**不**处理周线数据；所有计算均基于日线。

---

## 2. 输入规格

### 2a. 个股日线 OHLCV

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | `date` | 交易日日期 |
| `open` | `float` | 开盘价 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `close` | `float` | 收盘价 |
| `volume` | `int` | 成交量 |

- **最小数据量：** 200 个交易日（满足 ADX 的 14 周期 + 充分平滑、MACD 的 26 周期 EMA 预热、以及相对强度的 63 日窗口）。
- **推荐数据量：** ≥252 个交易日（1 完整交易年），与 overview 中的全局要求一致。

### 2b. 基准 ETF 日线 OHLCV

与个股格式相同。时间范围须与个股对齐（相同的起止日期）。基准 ETF 的选择逻辑见第 6 节。

### 2c. 数据质量要求

- 不允许 `close` 或 `high` / `low` 为 `null` 或 ≤0。
- 若输入数据存在缺失交易日（节假日除外），模块应记录警告但不插值，跳过缺失日期后继续计算。
- 若 `volume = 0` 或 `null`，不影响本模块计算（成交量分析属于 ③）。

---

## 3. RSI 计算

### 3a. 完整计算公式

RSI（Relative Strength Index）使用 Wilder 的平滑方法，周期 N = 14。

**第一步：计算每日价格变动**

```
change[i] = close[i] - close[i-1]
gain[i]   = max(change[i], 0)
loss[i]   = abs(min(change[i], 0))
```

**第二步：初始平均值（第 N 期）**

使用前 N 期的简单算术平均作为种子值：

```
avg_gain[N] = sum(gain[1..N]) / N
avg_loss[N] = sum(loss[1..N]) / N
```

**第三步：指数平滑（第 N+1 期起）**

```
avg_gain[i] = (avg_gain[i-1] × (N-1) + gain[i]) / N
avg_loss[i] = (avg_loss[i-1] × (N-1) + loss[i]) / N
```

**第四步：RSI**

```
RS  = avg_gain[i] / avg_loss[i]
RSI = 100 - (100 / (1 + RS))
```

若 `avg_loss[i] = 0`，则 `RSI = 100`。若 `avg_gain[i] = 0`，则 `RSI = 0`。

### 3b. 信号分类规则

RSI 信号分类为 `overbought | healthy | oversold`，阈值因市场状态而异。市场状态由 ADX 判定（见第 5 节）。

**趋势市场（ADX ≥ 25）：**

| 信号 | 条件 | 说明 |
|---|---|---|
| `overbought` | RSI ≥ 80 | 趋势市场中 RSI 可长期偏高，仅极端值视为超买 |
| `healthy` | 40 ≤ RSI < 80 | 趋势上行中 RSI 50-70 为健康区间；40-50 仍可接受 |
| `oversold` | RSI < 40 | 在强趋势中 RSI 跌破 40 已属明显回调 |

**震荡市场（ADX < 25）：**

| 信号 | 条件 | 说明 |
|---|---|---|
| `overbought` | RSI ≥ 70 | 经典超买阈值 |
| `healthy` | 30 ≤ RSI < 70 | 中性区间 |
| `oversold` | RSI < 30 | 经典超卖阈值 |

> **实现顺序说明：** RSI 的信号分类依赖 ADX 值。在单次计算流程中，应先计算 ADX，再据此确定 RSI 信号分类。

---

## 4. MACD 计算

### 4a. EMA 计算

MACD 使用三个 EMA：快线 12 周期、慢线 26 周期、信号线 9 周期。

EMA 通用公式（周期 N）：

```
multiplier = 2 / (N + 1)
EMA[0]     = SMA of first N closing prices        # 种子值
EMA[i]     = (close[i] - EMA[i-1]) × multiplier + EMA[i-1]
```

各周期的乘数：
- EMA-12：`multiplier = 2/13 ≈ 0.153846`
- EMA-26：`multiplier = 2/27 ≈ 0.074074`
- EMA-9（信号线）：`multiplier = 2/10 = 0.2`

### 4b. MACD 线、信号线、柱状图

```
MACD_line[i]   = EMA_12[i] - EMA_26[i]
signal_line[i] = EMA_9(MACD_line)           # 对 MACD_line 序列做 9 周期 EMA
histogram[i]   = MACD_line[i] - signal_line[i]
```

### 4c. 信号判定逻辑

#### bullish_cross（看涨交叉）

同时满足以下条件：

1. **上穿：** `MACD_line[i] > signal_line[i]` 且 `MACD_line[i-1] ≤ signal_line[i-1]`
2. **柱状图确认：** 交叉发生后连续 2 个交易日 `histogram > 0`（防止假交叉）
3. **有效期：** 上穿信号在发生后 5 个交易日内有效；超过 5 日未被形态或价量信号消费则衰减为 `flat`

#### bearish_cross（看跌交叉）

同时满足以下条件：

1. **下穿：** `MACD_line[i] < signal_line[i]` 且 `MACD_line[i-1] ≥ signal_line[i-1]`
2. **柱状图确认：** 交叉发生后连续 2 个交易日 `histogram < 0`
3. **有效期：** 与 bullish_cross 相同，5 个交易日

#### flat（无明确信号）

不满足 `bullish_cross` 或 `bearish_cross` 条件的所有其他情况，包括：
- MACD 线与信号线缠绕（交叉后未能维持 2 日确认）
- 交叉信号已超过 5 日有效期
- MACD 线与信号线同向运行无交叉

### 4d. 柱状图扩张/收缩的量化定义

柱状图动态用于辅助描述动量变化方向，写入 `momentum_summary`：

- **扩张（expanding）：** 连续 3 个交易日 `|histogram[i]| > |histogram[i-1]|`，方向一致（同为正或同为负）
- **收缩（contracting）：** 连续 3 个交易日 `|histogram[i]| < |histogram[i-1]|`，方向一致
- **其余情况不单独标记**

---

## 5. ADX 计算

### 5a. 完整计算流程

ADX（Average Directional Index）周期 N = 14。

**第一步：True Range（TR）**

```
TR[i] = max(
    high[i] - low[i],
    abs(high[i] - close[i-1]),
    abs(low[i] - close[i-1])
)
```

**第二步：方向运动（Directional Movement）**

```
up_move[i]   = high[i] - high[i-1]
down_move[i] = low[i-1] - low[i]

+DM[i] = up_move[i]   if (up_move[i] > down_move[i] and up_move[i] > 0)   else 0
-DM[i] = down_move[i]  if (down_move[i] > up_move[i] and down_move[i] > 0) else 0
```

**第三步：Wilder 平滑（14 周期）**

初始值（第 N 期）使用前 N 期的简单求和：

```
smoothed_TR[N]  = sum(TR[1..N])
smoothed_+DM[N] = sum(+DM[1..N])
smoothed_-DM[N] = sum(-DM[1..N])
```

后续值使用 Wilder 平滑：

```
smoothed_TR[i]  = smoothed_TR[i-1]  - (smoothed_TR[i-1] / N)  + TR[i]
smoothed_+DM[i] = smoothed_+DM[i-1] - (smoothed_+DM[i-1] / N) + +DM[i]
smoothed_-DM[i] = smoothed_-DM[i-1] - (smoothed_-DM[i-1] / N) + -DM[i]
```

**第四步：+DI / -DI**

```
+DI[i] = (smoothed_+DM[i] / smoothed_TR[i]) × 100
-DI[i] = (smoothed_-DM[i] / smoothed_TR[i]) × 100
```

**第五步：DX**

```
DX[i] = (|+DI[i] - -DI[i]| / (+DI[i] + -DI[i])) × 100
```

若 `+DI[i] + -DI[i] = 0`，则 `DX[i] = 0`。

**第六步：ADX**

ADX 是 DX 的 N 周期 Wilder 平滑移动平均：

```
ADX[N] = mean(DX[1..N])                              # 初始 ADX：前 N 个 DX 的简单平均
ADX[i] = (ADX[i-1] × (N-1) + DX[i]) / N             # 后续 Wilder 平滑
```

> **注意：** ADX 的完全稳定需要约 100-150 个数据点。前 28 个交易日（14 周期平滑 + 14 周期 ADX 平均）的 ADX 值不可靠，不应参与信号判定。

### 5b. 趋势强度分类

| 信号 | ADX 范围 | 含义 |
|---|---|---|
| `strong` | ADX ≥ 25 | 趋势明确，动量指标信号可信度高 |
| `moderate` | 20 ≤ ADX < 25 | 趋势正在形成或减弱，信号可信度中等 |
| `weak` | ADX < 20 | 震荡市场，动量信号易产生噪声 |

### 5c. ADX 对其他信号可信度的调节机制

ADX 不单独决定方向（参见 overview 聚合规则），但通过以下方式调节其他信号的解读：

1. **RSI 阈值切换：** 见第 3b 节。ADX ≥ 25 时使用趋势阈值，ADX < 25 时使用震荡阈值。

2. **MACD 信号降权：** 当 `ADX < 20` 时，`momentum_summary` 中应注明"震荡环境，MACD 交叉信号可靠性降低"。该信息传递给聚合器，聚合器在子信号生成阶段据此降低动量信号可信度（具体体现为：即使 RSI + MACD + RS 均满足 bullish 条件，若 ADX < 20，聚合器仍可将动量子信号降为 `neutral`）。

3. **ADX 方向变化：** 若 ADX 值本身在上升（`ADX[i] > ADX[i-5]`，5 日变化），表示趋势正在加强，反之表示趋势正在减弱。此信息写入 `momentum_summary`，供聚合器参考。

---

## 6. 相对强度计算

### 6a. 基准 ETF 选择逻辑

基准 ETF 选择遵循从具体到宽基的优先级：

**优先级 1 — 板块 ETF（sector_etf）**

若个股所属 GICS 板块可确定，优先使用对应的板块 ETF 作为基准，以衡量个股相对于同业的强度。

板块 ETF 映射表：

| GICS 板块 | 板块 ETF |
|---|---|
| 信息技术（Information Technology） | XLK |
| 通信服务（Communication Services） | XLC |
| 非必需消费品（Consumer Discretionary） | XLY |
| 必需消费品（Consumer Staples） | XLP |
| 能源（Energy） | XLE |
| 金融（Financials） | XLF |
| 医疗保健（Health Care） | XLV |
| 工业（Industrials） | XLI |
| 材料（Materials） | XLB |
| 房地产（Real Estate） | XLRE |
| 公用事业（Utilities） | XLU |

**优先级 2 — QQQ**

若个股为纳斯达克 100 成份股，且板块 ETF 数据不可用，使用 QQQ。

**优先级 3 — SPY（默认）**

上述两项均不适用或数据不可用时，回退到 SPY。

**选择结果记录：** 最终使用的基准 ETF 写入输出字段 `benchmark_used`。

### 6b. 63 日收益率比值计算

```
stock_return_63d = (stock_close[today] - stock_close[today - 63]) / stock_close[today - 63]
bench_return_63d = (bench_close[today] - bench_close[today - 63]) / bench_close[today - 63]
```

相对强度：

```
relative_strength = (1 + stock_return_63d) / (1 + bench_return_63d)
```

> 使用 `(1 + return)` 比值而非 `return / return`，以避免基准收益为零或负时的除零和符号翻转问题。

### 6c. RS 趋势方向判定

为判断相对强度的变化方向，比较当前 RS 与 21 日前的 RS：

```
rs_trend = "improving"  if RS[today] > RS[today - 21] × 1.02
rs_trend = "declining"  if RS[today] < RS[today - 21] × 0.98
rs_trend = "stable"     otherwise
```

> 2% 的容差带（×1.02 / ×0.98）用于过滤噪声。

RS 趋势写入 `momentum_summary`，不单独设置输出字段。

---

## 7. momentum_summary 生成规则

`momentum_summary` 是一句自然语言描述，供人类审阅者快速理解动量状态。生成规则按以下模板拼接：

### 7a. 模板结构

```
"[ADX 趋势强度描述]。[RSI 状态]，[MACD 状态]。相对 [benchmark] [RS 状态]。"
```

### 7b. 各片段生成规则

**ADX 趋势强度描述：**
- `strong`：`"趋势明确（ADX {value:.1f}）"`
- `moderate`：`"趋势温和（ADX {value:.1f}）"`
- `weak`：`"震荡环境（ADX {value:.1f}），动量信号可靠性降低"`

**RSI 状态：**
- `overbought`：`"RSI {value:.1f} 超买"`
- `healthy` + RSI > 50：`"RSI {value:.1f} 偏强"`
- `healthy` + RSI ≤ 50：`"RSI {value:.1f} 偏弱"`
- `oversold`：`"RSI {value:.1f} 超卖"`

**MACD 状态：**
- `bullish_cross`：`"MACD 看涨交叉"`
- `bullish_cross` + histogram expanding：`"MACD 看涨交叉，柱状图扩张"`
- `bearish_cross`：`"MACD 看跌交叉"`
- `bearish_cross` + histogram expanding：`"MACD 看跌交叉，柱状图扩张"`
- `flat` + histogram contracting：`"MACD 平稳，动量收敛"`
- `flat`（其余）：`"MACD 无明确信号"`

**RS 状态：**
- RS > 1.1 + improving：`"强于 {benchmark}（RS {value:.2f}，持续走强）"`
- RS > 1.0 + improving：`"略强于 {benchmark}（RS {value:.2f}，趋势改善）"`
- RS > 1.0 + stable/declining：`"略强于 {benchmark}（RS {value:.2f}）"`
- RS ≤ 1.0 + declining：`"弱于 {benchmark}（RS {value:.2f}，持续走弱）"`
- RS ≤ 1.0 + stable/improving：`"弱于 {benchmark}（RS {value:.2f}）"`
- RS < 0.8：追加 `"，显著落后"`

### 7c. 示例

> "趋势明确（ADX 32.5）。RSI 62.3 偏强，MACD 看涨交叉，柱状图扩张。相对 XLK 略强于 XLK（RS 1.08，趋势改善）。"

> "震荡环境（ADX 17.2），动量信号可靠性降低。RSI 44.1 偏弱，MACD 无明确信号。相对 SPY 弱于 SPY（RS 0.91）。"

---

## 8. 输出字段

输出为结构化 JSON 对象，字段定义与 overview 保持一致：

```json
{
  "rsi": 62.3,
  "rsi_signal": "healthy",
  "macd_signal": "bullish_cross",
  "adx": 32.5,
  "adx_trend_strength": "strong",
  "benchmark_used": "XLK",
  "relative_strength": 1.08,
  "momentum_summary": "趋势明确（ADX 32.5）。RSI 62.3 偏强，MACD 看涨交叉，柱状图扩张。相对 XLK 略强于 XLK（RS 1.08，趋势改善）。"
}
```

**各字段规格：**

| 字段 | 类型 | 取值范围 | 说明 |
|---|---|---|---|
| `rsi` | `float` | 0.0 – 100.0 | 14 周期 RSI 当前值，保留一位小数 |
| `rsi_signal` | `string` | `overbought \| healthy \| oversold` | 依 ADX 切换阈值体系（见第 3b 节） |
| `macd_signal` | `string` | `bullish_cross \| bearish_cross \| flat` | 交叉信号含 2 日确认、5 日有效期（见第 4c 节） |
| `adx` | `float` | 0.0 – 100.0 | 14 周期 ADX 当前值，保留一位小数 |
| `adx_trend_strength` | `string` | `strong \| moderate \| weak` | 见第 5b 节阈值表 |
| `benchmark_used` | `string` | `SPY \| QQQ \| {sector_etf}` | 实际使用的基准 ETF 代码 |
| `relative_strength` | `float` | > 0 | 63 日 RS 比值，保留两位小数 |
| `momentum_summary` | `string` | — | 自然语言摘要（见第 7 节） |

---

## 9. 边界情况处理

### 9a. 数据不足时的降级策略

| 可用数据量 | 降级行为 |
|---|---|
| < 15 个交易日 | 无法计算任何指标。所有数值字段输出 `null`，信号字段输出 `null`，`momentum_summary` = `"数据不足，无法计算动量指标"` |
| 15 – 27 个交易日 | 可计算 RSI（14 期）。MACD 需至少 26 + 9 = 35 个数据点，输出 `null`。ADX 需至少 28 个数据点，输出 `null`；RSI 信号使用震荡市场阈值（因 ADX 不可用）。`momentum_summary` 注明降级。 |
| 28 – 34 个交易日 | RSI 和 ADX 可计算（ADX 值可能不够稳定，`momentum_summary` 注明"ADX 尚未充分稳定"）。MACD 输出 `null`。 |
| 35 – 62 个交易日 | RSI、MACD、ADX 均可计算。相对强度需 63 日窗口，输出 `null`。 |
| ≥ 63 个交易日 | 所有指标均可计算。若 < 150 个数据点，`momentum_summary` 注明"ADX 预热期不足，精度有限"。 |
| 基准 ETF 数据缺失 | 相对强度输出 `null`，`benchmark_used` = `null`。其余指标正常计算。 |

### 9b. 指标极端值处理

| 情况 | 处理方式 |
|---|---|
| RSI = 100（连续上涨无回调） | 正常输出。信号为 `overbought`。`momentum_summary` 追加"RSI 达到极端值，短期回调风险较高"。 |
| RSI = 0（连续下跌无反弹） | 正常输出。信号为 `oversold`。`momentum_summary` 追加"RSI 达到极端值，可能存在超卖反弹机会"。 |
| ADX > 50 | 正常输出。`momentum_summary` 追加"趋势极强"。此时 RSI 超买/超卖阈值不再进一步放宽，仍使用趋势市场阈值。 |
| MACD 线与信号线数值极小（< 0.001 × close） | 视为 `flat`，避免浮点噪声触发假交叉。判定条件：`abs(MACD_line) < close × 0.001` 且 `abs(histogram) < close × 0.0005` 时，强制 `macd_signal = flat`。 |
| 相对强度极端值（RS > 2.0 或 RS < 0.5） | 正常输出数值，但 `momentum_summary` 追加"相对强度偏离异常，建议核实数据"。 |
| 个股单日涨跌幅 > 20% | 不过滤或剔除，正常纳入计算。指标自身的平滑机制已能消化单日异动。但 `momentum_summary` 可注明"近期出现大幅波动"。 |

### 9c. 计算顺序

由于 RSI 信号分类依赖 ADX，模块内部计算顺序为：

```
1. ADX（含 +DI / -DI）
2. RSI（数值计算与信号分类）
3. MACD（独立，可与 ADX 并行）
4. 相对强度（独立，可与上述并行）
5. momentum_summary（依赖上述所有结果）
```

在实现中，步骤 1-4 除 RSI 信号分类外的数值计算可并行执行；RSI 信号分类须等待 ADX 结果。
