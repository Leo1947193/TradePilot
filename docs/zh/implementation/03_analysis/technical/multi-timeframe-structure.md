# 多周期结构分析实现契约

## 1. 目标

实现日线/周线结构识别，输出聚合器可直接消费的：

- `trend_daily`
- `trend_weekly`
- `ma_alignment`
- `key_support`
- `key_resistance`
- `warnings`

当前代码没有这一层；不能在现有 `analyze_market_bars(...)` 上继续堆条件分支。

---

## 2. 输入

- `daily_bars: list[MarketBar]`
- `weekly_bars: list[MarketBar]`
- `analysis_time`

最低要求：

- 日线建议 `>= 252` 根
- 周线建议 `>= 52` 根

降级规则：

- 日线不足 200 根：子模块降为 `degraded`
- 周线不足 40 根：允许只输出 `trend_daily`，但 `trend_weekly = neutral` 且写 warning

---

## 3. 实现步骤

1. 先校验时间升序、价格有效、symbol 一致。
2. 计算：
   - 日线 `SMA20/50/200`
   - 日线 `EMA10/21`
   - 周线 `SMA10/40`
3. 计算均线斜率时不要在子模块内引入 pandas 依赖魔法写法；保持纯函数。
4. 先独立判 `trend_daily`、`trend_weekly`。
5. 再判 `ma_alignment`。
6. 最后扫描 52 周波段高低点，生成支撑/阻力并做聚类合并。

---

## 4. 输出口径

建议内部 schema：

```text
MultiTimeframeResult(
  trend_daily,
  trend_weekly,
  ma_alignment,
  key_support,
  key_resistance,
  data_completeness_pct,
  low_confidence,
  warnings,
)
```

实现约束：

- `key_support`、`key_resistance` 必须按离当前价格由近到远排序
- 同一价位聚类后的结果要稳定，避免每次排序漂移
- 不要在这里生成模块级 `technical_signal`

---

## 5. 与其他子模块的边界

- `momentum.py` 不应回写结构方向
- `volume_price.py` 可消费 `key_support/key_resistance`，但不能修改它们
- `patterns.py` 可以消费趋势和关键价位
- `aggregate.py` 才负责把结构结果映射为结构子信号

---

## 6. 测试重点

- 均线初始化边界
- 日线/周线冲突降级
- `ma_alignment` 四分类
- 缺失周线时的 degraded 路径
- 关键价位聚类后顺序稳定
