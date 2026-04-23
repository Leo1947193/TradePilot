# 风险指标计算实现契约

## 1. 目标

实现：

- `atr_14`
- `atr_pct`
- `beta`
- `bb_width`
- `bb_squeeze`
- `max_drawdown_63d`
- `iv_vs_hv`
- `risk_flags`

---

## 2. 输入

- `daily_bars`
- `benchmark_bars`
- 可选 `iv_inputs`

最低要求：

- ATR / 布林带 / 回撤：建议 `>= 63` 根
- Beta：建议 `>= 252` 根对齐后的收益序列
- `iv_vs_hv`：需要 ATM 近月 IV；没有时允许局部降级

---

## 3. 实现步骤

1. 先计算 ATR(14) 与 `atr_pct`。
2. 再计算布林带宽度与 `bb_squeeze`。
3. 再计算 63 日最大回撤。
4. 有 benchmark 时计算 Beta。
5. 有 IV 输入时计算 `iv_vs_hv`。
6. 最后统一生成 `risk_flags`。

实现约束：

- 风险旗标生成集中在一个函数里，避免在各指标函数里散落字符串
- `risk_flags` 必须稳定可测试，后续可迁移到 `app/rules/technical.py`

---

## 4. 输出口径

建议内部 schema：

```text
RiskMetricsResult(
  atr_14,
  atr_pct,
  beta,
  bb_width,
  bb_squeeze,
  max_drawdown_63d,
  iv_vs_hv,
  risk_flags,
  data_completeness_pct,
  low_confidence,
  warnings,
)
```

---

## 5. 与其他子模块的边界

- 不依赖 `patterns.py`
- 可读取 `volume_pattern` / `relative_strength` 作为风险旗标修饰条件，但不要把这些字段变成硬依赖
- 聚合器才决定哪些风险旗标拥有 `setup_state` 否决权

---

## 6. 测试重点

- ATR 和 `atr_pct`
- 252 日 Beta 回归
- squeeze 判定
- IV 缺失时的 degraded 路径
- `risk_flags` 顺序和去重稳定
