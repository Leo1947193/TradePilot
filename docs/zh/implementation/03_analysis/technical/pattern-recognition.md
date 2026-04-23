# 形态识别实现契约

## 1. 目标

实现 design 中定义的预设形态，并输出：

- `pattern_direction`
- `pattern_detected`
- `pattern_quality`
- `entry_trigger`
- `target_price`
- `stop_loss_price`
- `risk_reward_ratio`

当前仓库完全没有这一层。

---

## 2. 输入

- `daily_bars`
- `multi_timeframe_result`
- `momentum_result`
- `volume_price_result`
- `atr_14` 或可复用 ATR helper

实现建议：

- 不要让 `patterns.py` 直接依赖 `risk_metrics.py` 的完整输出对象，否则会形成脆弱耦合
- 若只需要 ATR，优先抽共享 helper，或把 `atr_14` 显式作为输入

---

## 3. 实现策略

1. 先实现统一的局部高低点和几何结构工具函数。
2. 再按形态逐个增加检测器。
3. 每个检测器只返回自己的命中结果，不做全局优先级决策。
4. 全局优先级、冲突裁决、`pattern_quality` 排序集中在本模块尾部完成。

建议接口：

```text
detect_vcp(...)
detect_bull_flag(...)
detect_flat_base(...)
...
select_best_pattern(matches)
```

---

## 4. 输出约束

- 未命中时统一输出 `pattern_detected = none`
- `pattern_quality = low` 的形态可以保留在内部调试对象，但不应贡献聚合器方向
- `target_price`、`stop_loss_price`、`risk_reward_ratio` 任一不可算时，不能硬凑数值

---

## 5. 与聚合器的关系

聚合器只消费：

- `pattern_direction`
- `pattern_quality`
- `pattern_detected`
- RR 与触发价用于 `setup_state` 和 public payload

不要在形态模块里直接决定 `setup_state`。

---

## 6. 测试重点

- 各形态至少 1 个正样例和 1 个负样例
- 多形态同时命中时的优先级稳定
- 无法计算 RR 时的空值路径
- ATR helper 来源变化时结果不漂移
