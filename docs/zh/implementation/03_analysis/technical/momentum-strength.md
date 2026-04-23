# 动量与强度量化实现契约

## 1. 目标

实现：

- `rsi`
- `rsi_signal`
- `macd_signal`
- `adx`
- `adx_trend_strength`
- `benchmark_used`
- `relative_strength`
- `momentum_summary`

当前代码没有这些字段；现有技术模块 summary 不能复用为这里的输出。

---

## 2. 输入

- `daily_bars`
- `benchmark_bars`
- `benchmark_symbol`

最低要求：

- 计算 RSI / MACD：建议 `>= 60` 根日线
- 计算 ADX：建议 `>= 60` 根日线
- 计算相对强度：建议 `>= 63` 根个股和基准同步日线

缺失处理：

- 无 benchmark 数据时，仍可输出 RSI / MACD / ADX，但 `relative_strength = null`，子模块降级
- 数据窗口不足时，不要造默认值；应写 warning 并降级

---

## 3. 实现步骤

1. 对个股与 benchmark 时间轴做交集对齐。
2. 计算 RSI(14)。
3. 计算 MACD(12,26,9) 和最后一根的交叉状态。
4. 计算 ADX(14)，并映射 `strong/moderate/weak`。
5. 计算 63 日相对强度。
6. 根据 design 阈值生成 summary，但 summary 只做解释，不承载最终方向。

实现建议：

- 所有核心指标写纯函数，避免把状态塞进 dataclass 外部缓存
- benchmark 选择逻辑放在 adapter 或模块入口，不放在指标函数内部

---

## 4. 输出口径

建议内部 schema：

```text
MomentumResult(
  rsi,
  rsi_signal,
  macd_signal,
  adx,
  adx_trend_strength,
  benchmark_used,
  relative_strength,
  momentum_summary,
  data_completeness_pct,
  low_confidence,
  warnings,
)
```

约束：

- `rsi`、`adx` 输出保留原始浮点值，不要先离散化再丢失数值
- `benchmark_used` 必须来自真实输入，不要硬编码在 summary 文本里

---

## 5. 与聚合器的关系

`aggregate.py` 只消费：

- `rsi`
- `macd_signal`
- `adx`
- `relative_strength`

`rsi_signal` 和 `momentum_summary` 主要服务 public payload 和可解释性，不应反过来驱动指标计算。

---

## 6. 测试重点

- RSI 边界值
- MACD bullish/bearish/flat 三态
- ADX 阈值映射
- benchmark 缺失时的降级行为
- 个股和 benchmark 日期不完全重合时的对齐策略
