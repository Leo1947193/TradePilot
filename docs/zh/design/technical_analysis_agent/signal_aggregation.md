# 聚合与信号综合模块

## 1. 模块职责与边界

聚合器是技术分析模块的**终端汇总节点**，不执行任何独立的技术指标计算。它的唯一职责是：

1. 消费五个子 Agent（① 多周期结构分析、② 动量与强度量化、③ 价量关系分析、④ 形态识别、⑤ 风险指标计算）的结构化输出
2. 将各子 Agent 输出映射为方向性子信号（`bullish / neutral / bearish`）
3. 执行加权评分，生成模块级 `technical_signal` 和 `setup_state`
4. 组装完整输出 Schema，供下游主调度 Agent、风险管理 Agent 和人类决策者消费

**明确排除：**
- 不重新计算任何原始指标（SMA、RSI、OBV 等）
- 不访问原始 OHLCV 数据
- 不修改子 Agent 的输出值，仅基于其输出做逻辑推断

---

## 2. 输入规格

### 2.1 完整依赖清单

聚合器从五个子 Agent 接收以下字段：

**① 多周期结构分析**

| 字段 | 类型 | 必需 | 缺失处理 |
|---|---|---|---|
| `trend_daily` | `bullish \| bearish \| neutral` | 是 | 结构信号降为 `neutral`，`trend` 字段标记为 `neutral` |
| `trend_weekly` | `bullish \| bearish \| neutral` | 是 | 结构信号降为 `neutral`，`trend` 字段标记为 `neutral` |
| `ma_alignment` | `fully_bullish \| partially_bullish \| mixed \| fully_bearish` | 否 | 跳过均线修正步骤，仅依据日/周线方向判定 |
| `key_support` | `[float]` | 否 | 输出中填空数组 `[]`，不影响信号计算 |
| `key_resistance` | `[float]` | 否 | 输出中填空数组 `[]`，不影响信号计算 |

**② 动量与强度量化**

| 字段 | 类型 | 必需 | 缺失处理 |
|---|---|---|---|
| `rsi` | `float` | 是 | 动量信号降为 `neutral` |
| `rsi_signal` | `overbought \| healthy \| oversold` | 否 | 直通输出，缺失时由 `rsi` 值推导 |
| `macd_signal` | `bullish_cross \| bearish_cross \| flat` | 是 | 动量信号降为 `neutral` |
| `adx` | `float` | 否 | 跳过可信度调节，默认系数 1.0 |
| `adx_trend_strength` | `strong \| moderate \| weak` | 否 | 直通输出 |
| `benchmark_used` | `SPY \| QQQ \| sector_etf` | 否 | 直通输出，缺失时填 `"SPY"` |
| `relative_strength` | `float` | 是 | 动量信号降为 `neutral` |
| `momentum_summary` | `string` | 否 | 直通输出 |

**③ 价量关系分析**

| 字段 | 类型 | 必需 | 缺失处理 |
|---|---|---|---|
| `obv_trend` | `rising \| falling \| flat` | 否 | 直通输出 |
| `obv_divergence` | `bullish \| bearish \| none` | 否 | 背离条件不参与组合判定，仅 breakout/breakdown 和 volume_pattern 决定价量信号 |
| `breakout_confirmed` | `boolean` | 是 | 默认 `false` |
| `breakdown_confirmed` | `boolean` | 是 | 默认 `false` |
| `volume_pattern` | `accumulation \| distribution \| neutral \| pullback_healthy \| bounce_weak` | 是 | 价量信号降为 `neutral` |

**④ 形态识别**

| 字段 | 类型 | 必需 | 缺失处理 |
|---|---|---|---|
| `pattern_direction` | `bullish \| bearish \| none` | 是 | 形态信号降为 `neutral` |
| `pattern_detected` | 枚举值 | 否 | 直通输出，填 `"none"` |
| `pattern_quality` | `high \| medium \| low` | 是 | 缺失时形态信号降为 `neutral` |
| `entry_trigger` | `string` | 否 | 直通输出 |
| `target_price` | `float` | 否 | 直通输出，缺失时填 `null` |
| `stop_loss_price` | `float` | 否 | 直通输出，缺失时填 `null` |
| `risk_reward_ratio` | `float` | 否 | 直通输出，缺失时填 `null` |

**⑤ 风险指标计算**

| 字段 | 类型 | 必需 | 缺失处理 |
|---|---|---|---|
| `atr_14` | `float` | 否 | 直通输出 |
| `atr_pct` | `float` | 否 | 跳过 atr_pct 否决检查 |
| `beta` | `float` | 否 | 直通输出 |
| `bb_width` | `float` | 否 | 直通输出 |
| `bb_squeeze` | `boolean` | 否 | 直通输出 |
| `max_drawdown_63d` | `float` | 否 | 跳过回撤否决检查 |
| `iv_vs_hv` | `float` | 否 | 跳过 IV 否决检查 |
| `risk_flags` | `[string]` | 否 | 视为空数组，无风险标记否决 |

### 2.2 缺失处理总则

- **必需字段缺失：** 对应子信号自动降为 `neutral`（得分 0），不阻塞整体聚合流程
- **非必需字段缺失：** 使用上表中指定的默认值或跳过相关逻辑，直通字段在输出中填默认值
- 缺失原因（超时、错误、数据不足）记入 `risk_flags`，格式为 `"agent_{N}_unavailable"`

---

## 3. 子信号生成规则

### 3.1 结构信号（基于子 Agent ①）

#### 3.1.1 日线/周线方向组合真值表

| `trend_daily` | `trend_weekly` | 基础结构信号 |
|---|---|---|
| bullish | bullish | **bullish** |
| bullish | neutral | neutral |
| bullish | bearish | neutral |
| neutral | bullish | neutral |
| neutral | neutral | neutral |
| neutral | bearish | neutral |
| bearish | bullish | neutral |
| bearish | neutral | neutral |
| bearish | bearish | **bearish** |

> 核心原则：只有日线和周线方向完全一致时，才输出方向性信号。任何冲突或单周期成立均降为 `neutral`。

#### 3.1.2 均线排列修正

在日/周线同向的基础上，`ma_alignment` 提供进一步的确认或降级：

| 基础信号 | `ma_alignment` | 最终结构信号 |
|---|---|---|
| bullish | `fully_bullish` | **bullish**（强确认） |
| bullish | `partially_bullish` | **bullish**（通过最低门槛） |
| bullish | `mixed` | **neutral**（均线未确认，降级） |
| bullish | `fully_bearish` | **neutral**（均线严重背离，降级） |
| bearish | `fully_bearish` | **bearish**（强确认） |
| bearish | `partially_bullish` 或 `mixed` | **neutral**（均线未确认，降级） |
| bearish | `fully_bullish` | **neutral**（均线严重背离，降级） |
| neutral | 任意 | **neutral**（不修正） |

> 说明：`partially_bullish` 对 bearish 信号执行降级是因为它表示均线仍存在部分多头结构，与空头方向矛盾。

#### 3.1.3 ma_alignment 缺失时的行为

当 `ma_alignment` 字段缺失时，跳过修正步骤，直接使用 3.1.1 真值表的基础结构信号作为最终结构信号。

---

### 3.2 动量信号（基于子 Agent ②）

#### 3.2.1 RSI + MACD + RS 组合判定矩阵

动量信号通过三个维度的"投票"机制生成：

| 维度 | 看涨条件 | 看跌条件 |
|---|---|---|
| RSI | `rsi > 50` | `rsi < 50` |
| MACD | `macd_signal = bullish_cross` | `macd_signal = bearish_cross` |
| 相对强度 | `relative_strength > 1.0` | `relative_strength < 1.0` |

**判定规则：**
- **bullish**：三个维度中至少两个满足看涨条件，且无维度满足看跌条件的"强看跌"（RSI < 40 或 RS < 0.8）
- **bearish**：三个维度中至少两个满足看跌条件，且无维度满足看涨条件的"强看涨"（RSI > 60 或 RS > 1.2）
- **neutral**：其余所有情况（包括信号矛盾、维度各持己见、处于临界区间）

> 特殊情况：`macd_signal = flat` 时，MACD 维度不计入任何一方的投票，仅由 RSI 和 RS 两票决定（两票一致则取该方向，否则 neutral）。

#### 3.2.2 ADX 可信度调节

ADX 不参与方向判定，但影响动量信号的**得分权重**：

| ADX 区间 | 可信度系数 | 含义 |
|---|---|---|
| ADX >= 25 | 1.0 | 趋势明确，动量信号可信 |
| 20 <= ADX < 25 | 0.75 | 趋势边缘，信号打七五折 |
| ADX < 20 | 0.50 | 震荡市场，信号打五折 |

**应用方式：** 在模块评分阶段，动量信号的原始得分（+1 / 0 / -1）乘以可信度系数后再乘以权重 0.25。

```text
momentum_contribution = momentum_signal_value × adx_confidence × 0.25
```

例如：动量信号为 bullish（+1），ADX = 18（系数 0.50），则动量贡献 = +1 × 0.50 × 0.25 = **0.125**，而非完整的 0.25。

---

### 3.3 价量信号（基于子 Agent ③）

#### 3.3.1 组合判定逻辑

**bullish 条件（满足任一即可）：**

| 条件编号 | 规则 | 含义 |
|---|---|---|
| V-B1 | `breakout_confirmed = true` | 放量突破已确认，最强看涨信号 |
| V-B2 | `volume_pattern = accumulation` **且** `obv_divergence = bullish` | 积累 + 看涨背离共振 |
| V-B3 | `volume_pattern = accumulation` **且** `breakout_confirmed = false` **且** `obv_divergence = none` | 单独积累，但无其他确认时**降为 neutral** |

> V-B3 说明：单独的 `accumulation` 不足以产生 bullish 信号，需要突破确认或背离配合。

**bearish 条件（满足任一即可）：**

| 条件编号 | 规则 | 含义 |
|---|---|---|
| V-S1 | `breakdown_confirmed = true` | 放量破位已确认，最强看跌信号 |
| V-S2 | `volume_pattern = distribution` **且** `obv_divergence = bearish` | 派发 + 看跌背离共振 |
| V-S3 | `volume_pattern = distribution` **且** `breakdown_confirmed = false` **且** `obv_divergence = none` | 单独派发，降为 neutral |

**neutral 条件：**
- 不满足以上任何 bullish 或 bearish 条件
- `volume_pattern` 为 `neutral`、`pullback_healthy` 或 `bounce_weak`
- `pullback_healthy` 不直接产生方向信号，但在 `technical_summary` 中作为背景描述

---

### 3.4 形态信号（基于子 Agent ④）

#### 3.4.1 形态方向与质量的组合判定

| `pattern_direction` | `pattern_quality` | 形态信号 |
|---|---|---|
| bullish | high | **bullish** |
| bullish | medium | **bullish** |
| bullish | low | **neutral** |
| bearish | high | **bearish** |
| bearish | medium | **bearish** |
| bearish | low | **neutral** |
| none | 任意 | **neutral** |

> 核心规则：**`low` 质量直接判定为 `neutral`**，无论形态方向如何。低质量形态不可靠，不应贡献方向性得分。

#### 3.4.2 有效看涨形态

以下 `pattern_detected` 值被视为有效看涨形态（需 `pattern_quality` >= medium）：
- `vcp`
- `bull_flag`
- `flat_base`
- `ascending_triangle`
- `cup_and_handle`

#### 3.4.3 有效看跌形态

以下 `pattern_detected` 值被视为有效看跌形态（需 `pattern_quality` >= medium）：
- `bear_flag`
- `breakdown_base`
- `descending_triangle`

---

## 4. 模块评分计算

### 4.1 权重公式

```text
technical_score =
  structure_signal × 0.35 +
  momentum_signal  × adx_confidence × 0.25 +
  volume_signal    × 0.20 +
  pattern_signal   × 0.20
```

**信号值映射：**
- `bullish` = **+1**
- `neutral` = **0**
- `bearish` = **-1**

**ADX 可信度系数**（详见 3.2.2）：
- ADX >= 25 → 1.0
- 20 <= ADX < 25 → 0.75
- ADX < 20 → 0.50
- ADX 缺失 → 1.0（不做调节）

### 4.2 得分范围与方向结论

`technical_score` 的理论范围为 **[-1.0, +1.0]**（当 ADX 系数 < 1 时，实际范围收窄）。

| 条件 | `technical_signal` |
|---|---|
| `technical_score > 0.30` | **bullish** |
| `technical_score < -0.30` | **bearish** |
| `-0.30 <= technical_score <= 0.30` | **neutral** |

> 边界值处理：恰好等于 +0.30 或 -0.30 时归为 **neutral**。阈值采用严格不等号（`>` 和 `<`），确保边界情况偏保守。

### 4.3 计算示例

**示例 1：强看涨场景**
- 结构信号 = bullish (+1)，动量信号 = bullish (+1)，ADX = 30（系数 1.0），价量信号 = bullish (+1)，形态信号 = bullish (+1)
- `score = 1×0.35 + 1×1.0×0.25 + 1×0.20 + 1×0.20 = 1.00` → **bullish**

**示例 2：混合信号场景**
- 结构信号 = bullish (+1)，动量信号 = bearish (-1)，ADX = 15（系数 0.50），价量信号 = neutral (0)，形态信号 = neutral (0)
- `score = 1×0.35 + (-1)×0.50×0.25 + 0×0.20 + 0×0.20 = 0.35 - 0.125 = 0.225` → **neutral**

**示例 3：边界值场景**
- 结构信号 = bullish (+1)，动量信号 = neutral (0)，ADX = 28（系数 1.0），价量信号 = neutral (0)，形态信号 = neutral (0)
- `score = 1×0.35 + 0 + 0 + 0 = 0.35` → **bullish**（严格大于 0.30）

---

## 5. setup_state 判定规则

`setup_state` 是一个独立于 `technical_signal` 的**可执行状态**标签，描述当前是否适合采取行动。

### 5.1 判定优先级

判定顺序为 **avoid → actionable → watch**（否决优先）：

```text
if 满足任一 avoid 条件:
    setup_state = "avoid"
elif 满足全部 actionable 条件:
    setup_state = "actionable"
else:
    setup_state = "watch"
```

### 5.2 avoid 条件集

满足**任一**以下条件即判定为 `avoid`：

| 编号 | 条件 | 说明 |
|---|---|---|
| AV-1 | `technical_signal = neutral` **且** 四个子信号中存在 bullish 与 bearish 的直接冲突（至少一个 bullish + 至少一个 bearish） | 方向严重分歧，无法形成一致判断 |
| AV-2 | `max_drawdown_63d > 0.20`（即 > 20%） | 近期回撤过大，标的处于受损状态 |
| AV-3 | `atr_pct > 0.05`（即 ATR 占价格 > 5%） | 日波动率过高，风险不可控 |
| AV-4 | `iv_vs_hv > 1.5` | 隐含波动率溢价过高，期权定价反映潜在二元事件风险 |
| AV-5 | `risk_flags` 中包含以下关键字之一：`"liquidity_crisis"`、`"max_drawdown_breach"`、`"extreme_volatility"` | 仅技术执行层面的极端风险标记，具有一票否决权 |

#### 5.2.1 风险标记否决权规则

以下 `risk_flags` 具有**一票否决权**，可将任何状态（包括原本符合 actionable 条件的）直接降为 `avoid`：

| risk_flag 关键字 | 否决原因 |
|---|---|
| `"liquidity_crisis"` | 流动性枯竭，无法有效执行 |
| `"max_drawdown_breach"` | 回撤超限（与 AV-2 联动） |
| `"extreme_volatility"` | 极端波动率（与 AV-3 联动） |

其他 `risk_flags`（如 `"elevated beta"`、`"iv premium"`）**不具备否决权**，但会记入输出的 `risk_flags` 数组中，并在 `technical_summary` 中标注为注意事项。

### 5.3 actionable 条件集

需同时满足**全部**以下条件：

| 编号 | 条件 | 说明 |
|---|---|---|
| AC-1 | `technical_signal` 为 `bullish` 或 `bearish`（方向明确） | 加权得分通过方向阈值 |
| AC-2 | 存在触发确认：`breakout_confirmed = true` 或 `breakdown_confirmed = true`，或 `pattern_detected != none` 且 `pattern_quality` >= medium 且 `entry_trigger` 非空 | 已有或即将到来的入场点 |
| AC-3 | 未触发任何 avoid 条件（AV-1 ~ AV-5） | 无重大风险标记 |
| AC-4 | `target_price` 和 `stop_loss_price` 均非 null，且 `risk_reward_ratio >= 2.0` | 风险收益比可接受 |

### 5.4 watch 条件集

不满足 avoid 条件，也不满足 actionable 的全部条件时，默认归为 `watch`。典型场景包括：

| 场景 | 说明 |
|---|---|
| 方向存在但未触发 | `technical_signal` 有方向，但 `breakout_confirmed` 和 `breakdown_confirmed` 均为 false，形态触发价尚未到达 |
| 风险可接受但偏高 | 风险指标未触及 avoid 阈值，但处于警戒区间（如 `max_drawdown_63d` 在 15%–20%、`atr_pct` 在 3.5%–5%） |
| 方向为 neutral 但无冲突 | 四个子信号没有明确矛盾，只是缺乏一致性 |
| 风险收益比不足 | `risk_reward_ratio < 2.0` 或 `target_price` / `stop_loss_price` 缺失 |

---

## 6. trend 与 technical_signal 的关系

### 6.1 定义区别

| 字段 | 含义 | 来源 |
|---|---|---|
| `trend` | 趋势背景描述，反映标的当前所处的结构性趋势方向 | 继承自子 Agent ① 的结构分析总体方向 |
| `technical_signal` | 模块级方向结论，是所有子信号加权聚合的结果 | 由 `technical_score` 经阈值判定产生 |

### 6.2 trend 的取值规则

`trend` 默认继承结构信号的方向：

```text
if 结构信号 = bullish:
    trend = "bullish"
elif 结构信号 = bearish:
    trend = "bearish"
else:
    trend = "neutral"
```

> 注意：`trend` 使用的是 3.1 节最终结构信号（经均线修正后的结果），而非原始 `trend_daily` 或 `trend_weekly`。

### 6.3 两者不一致的场景

| 场景 | `trend` | `technical_signal` | 含义与处理 |
|---|---|---|---|
| 趋势向上但动量衰竭 | bullish | neutral | 结构仍多头，但动量/价量/形态未确认。通常处于 `watch` 状态，等待新的触发信号 |
| 趋势向下但出现反转信号 | bearish | neutral 或 bullish | 结构仍空头，但底部形态或看涨背离正在形成。高风险反转机会，需谨慎对待 |
| 无明确趋势但形态突破 | neutral | bullish | 趋势尚未确立，但形态和价量已给出突破信号。可能是趋势启动的早期阶段 |
| 趋势向上但形态破位 | bullish | bearish | 结构多头但出现破位信号，可能是趋势反转的前兆。应标记为 `avoid` 或 `watch` |

**不一致时的处理原则：**
- **不修改任一字段的值**——两者各自反映不同维度的事实
- 在 `technical_summary` 中明确说明分歧，例如："趋势结构仍为多头，但动量和价量信号偏弱，整体方向判定为中性"
- 不一致本身是一个重要的信息信号，下游消费者（尤其是人类决策者）应据此做出更审慎的判断

---

## 7. technical_summary 生成规则

`technical_summary` 是一段面向人类决策者的自然语言摘要，将所有信号综合为可读的结论。

### 7.1 结构模板

```text
[方向判定句]。[趋势背景句]。[关键确认/缺失句]。[风险提示句（如有）]。[操作建议句]。
```

各句对应的信息优先级（从高到低）：

| 优先级 | 内容 | 对应字段 | 示例 |
|---|---|---|---|
| P0 | 模块方向结论 | `technical_signal` | "技术面整体看涨" / "技术面整体看跌" / "技术面信号中性" |
| P1 | 趋势背景 | `trend`、`trend_daily`、`trend_weekly`、`ma_alignment` | "日线和周线趋势同步向上，均线完全多头排列" |
| P2 | 关键确认信号 | `breakout_confirmed`、`breakdown_confirmed`、`pattern_detected`、`volume_pattern` | "已确认放量突破，VCP 形态质量高" |
| P3 | 动量状态 | `rsi`、`macd_signal`、`relative_strength`、`adx` | "RSI 62 处于健康区间，MACD 多头交叉，相对强度 1.15 跑赢大盘" |
| P4 | 风险标记 | `risk_flags`、`max_drawdown_63d`、`atr_pct`、`iv_vs_hv` | "注意：隐含波动率溢价偏高（IV/HV = 1.6），近期最大回撤 18%" |
| P5 | 操作状态 | `setup_state`、`entry_trigger`、`target_price`、`stop_loss_price`、`risk_reward_ratio` | "当前可操作：入场触发为收盘突破 $142.50，目标 $158，止损 $135，风险收益比 2.3:1" |

### 7.2 生成规则

1. **必须包含 P0 和 P5**——方向结论和操作状态是摘要的核心
2. **P1–P4 按相关性裁剪**——仅包含对当前判定有实质影响的信息，避免信息过载
3. **不一致时必须说明**——当 `trend` 与 `technical_signal` 不一致时（见第 6 节），在 P1 句中明确点出分歧
4. **风险优先于机会**——当存在 avoid 条件时，P4 提升至 P1 之后立即展示
5. **字数控制**——摘要总长度控制在 100-300 字（中文字符），避免冗长

### 7.3 各 setup_state 的摘要风格

| setup_state | 开头模板 | 重点 |
|---|---|---|
| actionable | "技术面整体{方向}，当前具备入场条件。" | 强调入场触发、目标价、止损价、风险收益比 |
| watch | "技术面偏{方向}，但尚需等待进一步确认。" | 强调缺失的确认条件、需要观察的触发点 |
| avoid | "技术面信号矛盾/风险过高，建议回避。" | 强调具体的风险标记和否决原因 |

---

## 8. 输出 Schema

API 对齐说明：

- 本节 Schema 定义的是技术聚合器内部输出
- 它是公共 `technical_analysis` 对象的上游来源，但不等同于最终 HTTP 响应
- 最终对外契约见 [../implementation/01_runtime/response-assembly-and-api-mapping.md](../implementation/01_runtime/response-assembly-and-api-mapping.md)

### 8.1 完整 Schema 定义

```json
{
  "technical_signal": "bullish | bearish | neutral",
  "trend": "bullish | bearish | neutral",
  "trend_daily": "bullish | bearish | neutral",
  "trend_weekly": "bullish | bearish | neutral",
  "ma_alignment": "fully_bullish | partially_bullish | mixed | fully_bearish",
  "key_support": [float],
  "key_resistance": [float],
  "volume_pattern": "accumulation | distribution | neutral | pullback_healthy | bounce_weak",
  "obv_divergence": "bullish | bearish | none",
  "breakout_confirmed": boolean,
  "breakdown_confirmed": boolean,
  "momentum": "string",
  "benchmark_used": "SPY | QQQ | sector_etf",
  "rsi": float,
  "rsi_signal": "overbought | healthy | oversold",
  "macd_signal": "bullish_cross | bearish_cross | flat",
  "adx": float,
  "relative_strength": float,
  "pattern_direction": "bullish | bearish | none",
  "pattern_detected": "vcp | bull_flag | flat_base | ascending_triangle | cup_and_handle | bear_flag | breakdown_base | descending_triangle | none",
  "pattern_quality": "high | medium | low",
  "entry_trigger": "string",
  "target_price": float,
  "stop_loss_price": float,
  "risk_reward_ratio": float,
  "atr_14": float,
  "atr_pct": float,
  "beta": float,
  "bb_width": float,
  "bb_squeeze": boolean,
  "max_drawdown_63d": float,
  "iv_vs_hv": float,
  "risk_flags": ["string"],
  "setup_state": "actionable | watch | avoid",
  "technical_summary": "string"
}
```

### 8.2 字段说明

| 字段 | 类型 | 来源 | 业务含义 | 边界值/约束 |
|---|---|---|---|---|
| `technical_signal` | string | 聚合器计算 | 模块级方向结论，供系统级加权器消费 | 枚举：`bullish \| bearish \| neutral` |
| `trend` | string | 聚合器（继承结构信号） | 趋势背景描述，反映结构性方向 | 枚举：`bullish \| bearish \| neutral` |
| `trend_daily` | string | 子 Agent ① 直通 | 日线级别趋势方向 | 枚举：`bullish \| bearish \| neutral` |
| `trend_weekly` | string | 子 Agent ① 直通 | 周线级别趋势方向 | 枚举：`bullish \| bearish \| neutral` |
| `ma_alignment` | string | 子 Agent ① 直通 | 均线多空排列状态 | 枚举：`fully_bullish \| partially_bullish \| mixed \| fully_bearish` |
| `key_support` | [float] | 子 Agent ① 直通 | 关键支撑位列表，按价格从高到低排序 | 0-5 个价位，空数组表示未识别 |
| `key_resistance` | [float] | 子 Agent ① 直通 | 关键阻力位列表，按价格从低到高排序 | 0-5 个价位，空数组表示未识别 |
| `volume_pattern` | string | 子 Agent ③ 直通 | 近期价量关系模式 | 枚举：`accumulation \| distribution \| neutral \| pullback_healthy \| bounce_weak` |
| `obv_divergence` | string | 子 Agent ③ 直通 | OBV 与价格的背离状态 | 枚举：`bullish \| bearish \| none` |
| `breakout_confirmed` | boolean | 子 Agent ③ 直通 | 是否已确认放量突破 | `true \| false` |
| `breakdown_confirmed` | boolean | 子 Agent ③ 直通 | 是否已确认放量破位 | `true \| false` |
| `momentum` | string | 子 Agent ② `momentum_summary` 直通 | 动量状态的文字描述 | 自由文本 |
| `benchmark_used` | string | 子 Agent ② 直通 | 相对强度计算所用基准 | 枚举：`SPY \| QQQ \| sector_etf` |
| `rsi` | float | 子 Agent ② 直通 | 14 周期 RSI 值 | 范围 [0, 100] |
| `rsi_signal` | string | 子 Agent ② 直通 | RSI 区间解读 | 枚举：`overbought \| healthy \| oversold` |
| `macd_signal` | string | 子 Agent ② 直通 | MACD 交叉状态 | 枚举：`bullish_cross \| bearish_cross \| flat` |
| `adx` | float | 子 Agent ② 直通 | 14 周期 ADX 值 | 范围 [0, 100]，通常 10-60 |
| `relative_strength` | float | 子 Agent ② 直通 | 个股 vs. 基准的相对强度（63 日） | 范围 (0, +∞)，>1.0 为跑赢基准 |
| `pattern_direction` | string | 子 Agent ④ 直通 | 已识别形态的方向 | 枚举：`bullish \| bearish \| none` |
| `pattern_detected` | string | 子 Agent ④ 直通 | 已识别的具体形态名称 | 枚举值见 overview 第 194 行 |
| `pattern_quality` | string | 子 Agent ④ 直通 | 形态质量评级 | 枚举：`high \| medium \| low` |
| `entry_trigger` | string | 子 Agent ④ 直通 | 入场触发条件的文字描述 | 自由文本，null 表示无明确触发 |
| `target_price` | float \| null | 子 Agent ④ 直通 | 形态投影目标价 | > 0，null 表示无法计算 |
| `stop_loss_price` | float \| null | 子 Agent ④ 直通 | 建议止损价 | > 0，null 表示无法计算 |
| `risk_reward_ratio` | float \| null | 子 Agent ④ 直通 | 风险收益比（目标涨幅 / 止损跌幅） | >= 0，null 表示无法计算；>= 2.0 为可接受 |
| `atr_14` | float | 子 Agent ⑤ 直通 | 14 周期平均真实波幅（绝对值） | > 0 |
| `atr_pct` | float | 子 Agent ⑤ 直通 | ATR 占价格的百分比 | > 0，通常 0.01-0.08；> 0.05 触发 avoid |
| `beta` | float | 子 Agent ⑤ 直通 | 相对于 SPY 的 252 日 Beta | 可为负值（反向相关），通常 0.5-2.5 |
| `bb_width` | float | 子 Agent ⑤ 直通 | 布林带宽度（上轨-下轨）/ 中轨 | > 0，收窄趋势暗示即将突破或破位 |
| `bb_squeeze` | boolean | 子 Agent ⑤ 直通 | 布林带是否处于挤压状态 | `true \| false` |
| `max_drawdown_63d` | float | 子 Agent ⑤ 直通 | 滚动 63 日最大回撤（绝对值） | 范围 [0, 1]；> 0.20 触发 avoid |
| `iv_vs_hv` | float | 子 Agent ⑤ 直通 | 隐含波动率 / 30 日历史波动率 | > 0；> 1.5 触发 avoid |
| `risk_flags` | [string] | 子 Agent ⑤ 直通 + 聚合器追加 | 风险标记列表 | 聚合器可追加 `"agent_{N}_unavailable"` |
| `setup_state` | string | 聚合器计算 | 可执行状态 | 枚举：`actionable \| watch \| avoid` |
| `technical_summary` | string | 聚合器生成 | 面向人类的综合文字摘要 | 100-300 中文字符 |

---

## 9. 异常处理与降级策略

### 9.1 子 Agent 故障场景

| 故障类型 | 检测方式 | 处理 |
|---|---|---|
| 超时 | 子 Agent 在规定时间窗口内未返回结果 | 视为该子 Agent 全部字段缺失 |
| 返回错误 | 子 Agent 返回错误码或异常信息 | 同上，视为全部字段缺失 |
| 部分字段缺失 | 返回了结果但某些字段为 null 或未包含 | 按第 2 节"缺失处理"列逐字段处理 |
| 数据异常 | 字段值超出合理范围（如 RSI = -5） | 丢弃异常字段，按缺失处理 |

### 9.2 最低可用子 Agent 数量

聚合器至少需要 **3 个子 Agent** 的有效输出才能生成有效结论。

**必需的最低组合：**

| 优先级 | 最低组合 | 理由 |
|---|---|---|
| 1 | ① + ② + ③ | 结构 + 动量 + 价量覆盖了方向和确认的核心维度 |
| 2 | ① + ② + ⑤ | 结构 + 动量 + 风险，缺少价量确认但仍可判断方向和风险 |
| 3 | 任意 3 个子 Agent | 只要能覆盖至少一个方向维度和一个确认/风险维度 |

**降级行为矩阵：**

| 可用子 Agent 数 | 行为 |
|---|---|
| 5 | 正常执行全部逻辑 |
| 4 | 正常执行，缺失子 Agent 的权重分摊至其余子信号（按比例重新归一化），在 `risk_flags` 中追加 `"agent_{N}_unavailable"` |
| 3 | 执行降级模式：缺失子 Agent 的子信号固定为 neutral，权重不重新分配，`setup_state` 最高只能为 `watch`（不可为 `actionable`），在 `technical_summary` 中注明数据不完整 |
| 2 或更少 | **拒绝生成结论**：`technical_signal = neutral`、`setup_state = avoid`，`technical_summary` 输出 "子 Agent 输出不足，无法生成有效技术分析结论"，`risk_flags` 追加 `"insufficient_agent_outputs"` |

### 9.3 权重重新归一化（4 个子 Agent 可用时）

当一个子 Agent 缺失时，其权重按比例分配给其余子信号：

```text
# 假设形态信号（权重 0.20）缺失
剩余权重总和 = 0.35 + 0.25 + 0.20 = 0.80
归一化后：
  structure = 0.35 / 0.80 = 0.4375
  momentum  = 0.25 / 0.80 = 0.3125
  volume    = 0.20 / 0.80 = 0.2500
```

方向结论阈值（±0.30）保持不变。
