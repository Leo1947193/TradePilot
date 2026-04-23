# 价量关系分析实现契约

## 1. 目标

实现：

- `obv_trend`
- `obv_divergence`
- `breakout_confirmed`
- `breakdown_confirmed`
- `volume_pattern`

这部分不能继续留在 graph node；应成为独立子模块。

---

## 2. 输入

- `daily_bars`
- 可选 `key_support`
- 可选 `key_resistance`

最低要求：

- OBV 和 20 日均量：建议 `>= 40` 根
- 52 周突破/破位识别：建议 `>= 252` 根；若不足则只做局部突破检测并标记 degraded

---

## 3. 实现步骤

1. 计算 OBV 序列。
2. 判定 OBV 最近窗口是 `rising/falling/flat`。
3. 基于价格和 OBV 局部极值做背离识别。
4. 计算 20 日均量和量比。
5. 检测：
   - 高量突破
   - 高量破位
   - 低量回调
   - 弱量反弹
6. 最后统一映射到 `volume_pattern`。

实现约束：

- `breakout_confirmed` 与 `breakdown_confirmed` 必须互斥
- 单独的 `accumulation` / `distribution` 只是背景，不应在本子模块直接输出最终方向

---

## 4. 输出口径

建议内部 schema：

```text
VolumePriceResult(
  obv_trend,
  obv_divergence,
  breakout_confirmed,
  breakdown_confirmed,
  volume_pattern,
  data_completeness_pct,
  low_confidence,
  warnings,
)
```

---

## 5. 与其他子模块的边界

- 结构模块提供关键价位，但不提供成交量结论
- 形态模块可以消费 `breakout_confirmed/breakdown_confirmed`
- 聚合器只读取结果，不回头改写底层量价状态

---

## 6. 测试重点

- OBV 上升/下降/走平
- 看涨/看跌背离
- breakout 与 breakdown 互斥
- 数据长度不足 252 根时的 degraded 逻辑
