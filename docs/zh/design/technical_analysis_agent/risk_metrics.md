# ⑤ 风险指标计算 — 子模块设计文档

## 1. 模块职责与边界

### 职责

本模块负责量化个股的**波动性、系统性风险暴露和近期损失幅度**，为聚合层的 `setup_state` 判定和下游风险管理 Agent 的仓位计算提供定量依据。具体包括：

1. 计算 ATR、Beta、布林带宽度、最大回撤、IV vs HV 五项风险指标
2. 根据指标阈值生成 `risk_flags` 标记列表
3. 将结果输出为标准化 JSON 字段，供聚合器消费

### 边界

| 范围内 | 范围外 |
|---|---|
| 风险指标的计算与标记 | 仓位大小建议（由风险管理 Agent 负责） |
| 波动率压缩 / 膨胀的检测 | 期权策略构建或希腊字母计算 |
| IV 与 HV 的比值判读 | IV 曲面建模、波动率微笑拟合 |
| 单只股票的风险评估 | 投资组合级别的相关性 / VaR 分析 |

### 依赖关系

本模块依赖 ①②③ 子模块的**已完成输出**，具体接口如下：

| 上游模块 | 消费字段 | 用途 |
|---|---|---|
| ① 多周期结构分析 | `key_support`、`key_resistance` | 回撤幅度是否触及关键支撑；布林带宽度与价格结构的交叉验证 |
| ② 动量与强度量化 | `adx`、`relative_strength` | ADX 低迷时布林带收窄更具方向性意义；相对强度弱化时回撤 flag 权重提升 |
| ③ 价量关系分析 | `volume_pattern`、`obv_divergence` | 分布型量能叠加高回撤触发更强 flag；背离信号影响 IV 异常的解读 |

> 本模块不直接依赖 ④ 形态识别的输出；④ 和 ⑤ 并行运行，各自独立向聚合层提交结果。

---

## 2. 输入规格

### 2a. 个股日线 OHLCV

| 字段 | 类型 | 要求 |
|---|---|---|
| `date` | `datetime` | 交易日日期，按升序排列 |
| `open` | `float` | 开盘价 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `close` | `float` | 收盘价（调整后） |
| `volume` | `int` | 成交量 |

- **最少行数：** 252 个交易日（1 年），以满足 Beta 252 日回溯窗口和 HV 计算需求
- **数据源：** `yfinance`（主要）；数据记录必须包含来源名称和抓取时间戳

### 2b. SPY 日线数据

| 字段 | 类型 | 要求 |
|---|---|---|
| `date` | `datetime` | 与个股日线对齐的交易日序列 |
| `close` | `float` | SPY 收盘价（调整后） |

- **时间范围：** 与个股日线完全对齐（至少 252 个交易日）
- **用途：** Beta 回归计算的基准收益率序列

### 2c. 期权数据（IV）

| 字段 | 类型 | 要求 |
|---|---|---|
| `implied_volatility` | `float` | 当前隐含波动率（年化） |
| `expiration_date` | `datetime` | 期权到期日 |
| `option_type` | `string` | `call` 或 `put` |
| `strike` | `float` | 行权价 |

- **提取规则：** 从期权链中选取**最接近平价（ATM）、最近到期月（30 日左右）**的合约，取 call 和 put IV 的均值作为当前 IV
- **数据源：** `yfinance` 期权链接口
- **可选性：** 期权数据为可选输入（详见第 8 节降级策略）

---

## 3. 各指标的详细计算

### 3a. ATR(14) — 平均真实范围

#### True Range 定义

每个交易日的 True Range (TR) 取以下三者的最大值：

```
TR(t) = max(
    H(t) - L(t),                   # 情况1：当日振幅
    |H(t) - C(t-1)|,               # 情况2：当日最高价与前一日收盘价的差距
    |L(t) - C(t-1)|                 # 情况3：当日最低价与前一日收盘价的差距
)
```

- 情况 1 覆盖日内波动
- 情况 2 和 3 覆盖跳空缺口（向上或向下）

#### ATR 指数平滑计算

采用 Wilder 平滑法（等价于周期为 `2N-1` 的 EMA），N = 14：

```
ATR(t) = ATR(t-1) × (N-1)/N + TR(t) × 1/N
       = ATR(t-1) × 13/14 + TR(t) × 1/14
```

初始值：前 14 个交易日 TR 的简单算术平均值。

#### ATR 百分比

```
atr_pct = ATR(t) / C(t) × 100
```

**用途：**
- 跨不同价格水平的股票横向比较波动率（$10 股票的 ATR=1 与 $200 股票的 ATR=1 含义截然不同）
- 下游风险管理 Agent 用 `atr_pct` 进行仓位归一化

**参考阈值：**
| atr_pct | 解读 |
|---|---|
| < 2% | 低波动 |
| 2%–5% | 正常波动 |
| 5%–8% | 高波动 |
| > 8% | 极端波动，触发 risk_flag |

---

### 3b. Beta — 系统性风险暴露

#### 回归计算方法

1. **计算日收益率序列：**
   ```
   r_stock(t) = (C_stock(t) - C_stock(t-1)) / C_stock(t-1)
   r_spy(t)   = (C_spy(t) - C_spy(t-1)) / C_spy(t-1)
   ```

2. **回溯窗口：** 252 个交易日（约 1 年）

3. **OLS 回归：**
   ```
   r_stock = α + β × r_spy + ε
   ```
   β 即为所求 Beta 值。等价公式：
   ```
   β = Cov(r_stock, r_spy) / Var(r_spy)
   ```

4. **实现说明：** 使用协方差 / 方差公式即可，无需引入完整回归库。若数据不足 252 日，使用可用的最大窗口但不少于 60 日，并在输出中附加 `data_quality` 标记。

#### Beta 解读阈值分级

| Beta 范围 | 分级 | 含义 |
|---|---|---|
| β < 0.5 | `low` | 防御型，受市场波动影响小 |
| 0.5 ≤ β < 1.0 | `moderate` | 低于市场平均波动 |
| 1.0 ≤ β < 1.5 | `high` | 与市场同步或略高 |
| β ≥ 1.5 | `very_high` | 市场波动放大器，触发 risk_flag |

> 负 Beta 极为罕见（反向 ETF 除外），若出现应在 `risk_flags` 中标记为 `"anomalous negative beta"`。

---

### 3c. 布林带宽度

#### 计算公式

1. **中轨：** 20 周期简单移动平均（SMA）
   ```
   SMA_20(t) = (1/20) × Σ C(t-i),  i = 0..19
   ```

2. **标准差：**
   ```
   σ_20(t) = sqrt((1/20) × Σ (C(t-i) - SMA_20(t))²),  i = 0..19
   ```

3. **上下轨：**
   ```
   Upper = SMA_20 + 2 × σ_20
   Lower = SMA_20 - 2 × σ_20
   ```

4. **布林带宽度（标准化）：**
   ```
   bb_width = (Upper - Lower) / SMA_20
   ```
   标准化为相对于中轨的比例，使不同价格水平的股票可以横向比较。

#### Bollinger Squeeze 判定条件

```
bb_squeeze = True  当且仅当  bb_width(t) ≤ min(bb_width(t-1), ..., bb_width(t-125))
```

即：当前 bb_width 为近 **126 个交易日（约 6 个月）** 的最低值。

**解读：**
- `bb_squeeze = True` 意味着波动率压缩到半年来的极端水平，通常预示即将发生方向性突破或破位
- 需结合 ①（趋势方向）和 ③（量能模式）判断突破方向

---

### 3d. 最大回撤（63 日滚动）

#### 计算公式

在滚动 63 个交易日（约 3 个月）窗口内：

```
running_max(t) = max(C(t-62), C(t-61), ..., C(t))
drawdown(t)    = (C(t) - running_max(t)) / running_max(t)
max_drawdown_63d = min(drawdown(t-62), drawdown(t-61), ..., drawdown(t))
```

输出值为**负数或零**（例如 -0.15 表示 15% 的回撤），聚合层和 risk_flag 判定统一使用绝对值进行阈值比较。

#### 标记规则

| |max_drawdown_63d| | 解读 |
|---|---|
| < 10% | 正常波动范围 |
| 10%–20% | 中等回撤，需关注 |
| > 20% | 深度回撤，触发 risk_flag |
| > 30% | 严重回撤，强烈建议回避 |

> 当 `|max_drawdown_63d| > 20%` 时，聚合层将该指标作为 `setup_state = avoid` 的候选条件之一。

---

### 3e. IV vs HV — 隐含波动率与历史波动率之比

#### 隐含波动率（IV）的数据提取

1. 从 `yfinance` 获取目标股票的**完整期权链**
2. **筛选到期日：** 选择距当前日期最近的月度到期日，且剩余天数在 **20–45 天**范围内（目标约 30 天）
3. **筛选行权价：** 选取最接近当前股价的 ATM 行权价（允许上下各一档）
4. **取值方式：** 分别取 ATM call 和 ATM put 的 `impliedVolatility` 字段，计算其算术平均值作为当前 IV
   ```
   IV = (IV_call_atm + IV_put_atm) / 2
   ```
5. **注意：** `yfinance` 返回的 IV 已为年化值，无需额外转换

#### 30 日历史波动率（HV）计算

1. **计算日对数收益率：**
   ```
   ln_return(t) = ln(C(t) / C(t-1))
   ```

2. **取近 30 个交易日的对数收益率标准差：**
   ```
   σ_daily = std(ln_return(t-29), ..., ln_return(t))
   ```

3. **年化：**
   ```
   HV_30 = σ_daily × sqrt(252)
   ```

#### IV vs HV 比值及解读

```
iv_vs_hv = IV / HV_30
```

| iv_vs_hv | 解读 |
|---|---|
| < 0.8 | IV 折价：市场对未来波动的预期低于近期实际波动，期权相对便宜 |
| 0.8–1.2 | 正常范围：IV 与 HV 基本一致 |
| 1.2–1.5 | IV 轻微溢价：市场预期波动加大，可能存在催化事件 |
| > 1.5 | IV 显著溢价：期权昂贵，暗示市场预期重大波动（财报、FDA 审批等），触发 risk_flag |

---

## 4. risk_flags 规则集

### 4a. 完整 flag 枚举

| Flag ID | Flag 文本模板 | 触发条件 | 严重程度 |
|---|---|---|---|
| `HIGH_ATR` | `"high volatility: ATR {atr_pct:.1f}% of price"` | `atr_pct > 8%` | `high` |
| `ELEVATED_BETA` | `"elevated beta: {beta:.2f} vs SPY"` | `β ≥ 1.5` | `medium` |
| `EXTREME_BETA` | `"extreme beta: {beta:.2f} vs SPY — loss amplification risk"` | `β ≥ 2.5` | `high` |
| `NEGATIVE_BETA` | `"anomalous negative beta: {beta:.2f}"` | `β < 0` | `medium` |
| `BB_SQUEEZE` | `"bollinger squeeze: volatility at 6-month low — breakout imminent"` | `bb_squeeze = True` | `info` |
| `DEEP_DRAWDOWN` | `"deep drawdown: {abs(max_drawdown_63d)*100:.1f}% in 63 days"` | `\|max_drawdown_63d\| > 20%` | `high` |
| `SEVERE_DRAWDOWN` | `"severe drawdown: {abs(max_drawdown_63d)*100:.1f}% in 63 days — avoid"` | `\|max_drawdown_63d\| > 30%` | `critical` |
| `IV_PREMIUM` | `"iv premium: implied vol {iv_vs_hv:.2f}x historical — jump risk elevated"` | `iv_vs_hv > 1.5` | `high` |
| `IV_EXTREME` | `"extreme iv premium: {iv_vs_hv:.2f}x — jump risk extreme"` | `iv_vs_hv > 2.5` | `critical` |
| `IV_UNAVAILABLE` | `"IV data unavailable — options risk assessment degraded"` | 期权数据缺失 | `info` |

### 4b. Flag 生成格式规范

每个 flag 为一个 **小写英文字符串**，嵌入具体数值，遵循以下格式：

```
"{描述性短语}: {指标名} {具体数值}{单位} — {影响说明}"
```

示例输出：
```json
[
  "elevated beta: 1.73 vs SPY",
  "deep drawdown: 24.3% in 63 days",
  "iv premium: implied vol 1.82x historical — jump risk elevated"
]
```

### 4c. Flag 组合效应

当多个 flag 同时触发时，按以下规则处理：

1. **分级叠加：** 同一指标的低级别 flag 被高级别 flag **覆盖**（不共存）
   - `ELEVATED_BETA` + `EXTREME_BETA` → 仅保留 `EXTREME_BETA`
   - `DEEP_DRAWDOWN` + `SEVERE_DRAWDOWN` → 仅保留 `SEVERE_DRAWDOWN`
   - `IV_PREMIUM` + `IV_EXTREME` → 仅保留 `IV_EXTREME`

2. **跨指标累积：** 不同指标的 flag 全部保留，因为它们反映不同维度的风险
   - `ELEVATED_BETA` + `DEEP_DRAWDOWN` + `IV_PREMIUM` → 三个 flag 全部输出

3. **聚合层的 avoid 升级规则：**
   - 任意 `critical` 级别 flag → 强烈建议 `setup_state = avoid`
   - 两个或以上 `high` 级别 flag 同时触发 → 建议 `setup_state = avoid`
   - 单个 `high` 级别 flag → 聚合层将 `setup_state` 最高设为 `watch`（除非其他子信号足够强）
   - `info` 级别 flag 不影响 `setup_state` 判定，仅作为参考信息传递

4. **输出排序：** `risk_flags` 数组按严重程度降序排列（`critical` → `high` → `medium` → `info`）

---

## 5. 与下游的接口

### 5a. 聚合层消费方式

聚合层在计算 `setup_state` 时，按以下逻辑消费 `risk_flags`：

```text
if any flag.severity == "critical":
    setup_state 强制降级为 "avoid"
elif count(flag.severity == "high") >= 2:
    setup_state 强制降级为 "avoid"
elif count(flag.severity == "high") == 1:
    setup_state 最高为 "watch"（即使技术信号为 actionable）
else:
    setup_state 不受 risk_flags 影响，由技术信号决定
```

> 注意：`risk_flags` 只做**降级**操作，不会将 `setup_state` 升级。即使所有风险指标正常，`setup_state` 也不会因此从 `watch` 升为 `actionable`。

### 5b. 风险管理 Agent 消费方式

风险管理 Agent 直接消费以下数值字段（不依赖 flag）：

| 字段 | 用途 |
|---|---|
| `atr_14` | 止损距离计算（通常为 1–2 × ATR） |
| `atr_pct` | 仓位大小归一化（波动率越高，仓位越小） |
| `beta` | 组合级系统性风险敞口评估 |
| `max_drawdown_63d` | 历史风险容忍度参考 |

### 5c. 人类决策者消费方式

`risk_flags` 数组中的文本直接呈现在最终分析报告中，作为**易读的风险提示**。文本需自解释，无需额外上下文即可理解。

---

## 6. 数据缺失处理

### 6a. OHLCV 数据缺失

| 场景 | 处理策略 |
|---|---|
| 数据行数 < 252 但 ≥ 126 | ATR、布林带、回撤正常计算；Beta 使用可用窗口计算，输出附加 `"beta computed on {n} days (< 252)"` 注释 |
| 数据行数 < 126 但 ≥ 63 | ATR、布林带正常计算；Beta 标记为 `"low confidence"`；最大回撤仍使用 63 日窗口 |
| 数据行数 < 63 | ATR 正常计算（仅需 14 日）；最大回撤使用可用窗口；Beta 和 bb_squeeze 标记为 `null` |
| 数据行数 < 14 | 本模块拒绝执行，返回错误信息 `"insufficient data: {n} days available, minimum 14 required"` |
| 个别日期缺失（非连续） | 跳过缺失日，序列按实际交易日顺序计算；不做插值 |

### 6b. SPY 数据缺失

| 场景 | 处理策略 |
|---|---|
| SPY 日线与个股日线存在日期不对齐 | 取两者日期的交集进行 Beta 计算 |
| SPY 数据完全不可用 | Beta 设为 `null`，`risk_flags` 中添加 `"beta unavailable — SPY data missing"` |

### 6c. 期权数据不可用时的降级策略

期权数据为**可选依赖**。当期权数据不可用时（`yfinance` 返回空、目标股票无上市期权、网络错误等）：

1. `iv_vs_hv` 字段设为 `null`
2. `risk_flags` 中添加 `"IV data unavailable — options risk assessment degraded"`（severity: `info`）
3. 其余四项指标（ATR、Beta、布林带宽度、最大回撤）正常计算，不受影响
4. 聚合层在缺少 IV 数据时，不会因 IV 相关条件触发 `avoid`，但会在 `technical_summary` 中注明 IV 评估不可用

> 设计原则：期权数据缺失是常见情况（许多股票无活跃期权市场），模块必须在无期权数据时仍能提供有意义的风险评估。

---

## 7. 输出字段

### 完整输出 Schema

API 对齐说明：

- 本节 Schema 仅用于 `risk_metrics` 子模块内部契约
- 不直接作为公共 HTTP API 响应输出
- 最终对外响应见 [../api/schemas.md](../api/schemas.md) 和 [../api/openapi.yaml](../api/openapi.yaml)

```json
{
  "atr_14": float,
  "atr_pct": float,
  "beta": float | null,
  "bb_width": float,
  "bb_squeeze": boolean,
  "max_drawdown_63d": float,
  "iv_vs_hv": float | null,
  "risk_flags": ["string"]
}
```

### 字段定义

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `atr_14` | `float` | 14 周期 ATR 绝对值（与价格同单位） | `3.42` |
| `atr_pct` | `float` | ATR 占收盘价百分比 | `2.41` |
| `beta` | `float \| null` | 相对于 SPY 的 252 日 Beta；数据不足时为 `null` | `1.32` |
| `bb_width` | `float` | 布林带宽度（标准化为相对于中轨的比例） | `0.087` |
| `bb_squeeze` | `boolean` | 当前 bb_width 是否为近 126 日最低值 | `true` |
| `max_drawdown_63d` | `float` | 滚动 63 日最大回撤（负数或零） | `-0.153` |
| `iv_vs_hv` | `float \| null` | 隐含波动率 / 30 日历史波动率；期权数据不可用时为 `null` | `1.34` |
| `risk_flags` | `[string]` | 风险标记文本数组，按严重程度降序排列；无标记时为空数组 | `["elevated beta: 1.73 vs SPY"]` |

### 与 overview 输出 Schema 的一致性

本模块输出的 8 个字段与 overview 第 5 节输出 Schema 中定义的字段**完全一致**，无新增、无缺失、无类型变更。聚合器直接将本模块输出合并入最终 JSON，不做字段映射。
