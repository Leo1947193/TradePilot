# 技术模块聚合实现契约

## 1. 目标

聚合器是技术模块唯一允许做跨子模块评分的地方，负责输出：

- `technical_signal`
- `trend`
- `setup_state`
- `technical_summary`
- `risk_flags`
- `data_completeness_pct`
- `low_confidence`

当前仓库的 `analyze_market_bars(...)` 是占位聚合器；后续应被独立 `aggregate.py` 替代。

---

## 2. 输入

- `MultiTimeframeResult`
- `MomentumResult`
- `VolumePriceResult`
- `PatternRecognitionResult`
- `RiskMetricsResult`

每个子模块要先映射成方向子信号：

- 结构信号
- 动量信号
- 价量信号
- 形态信号

风险模块不直接提供方向，只提供 `setup_state` 修饰和风险旗标。

---

## 3. 评分与状态

按 design 固定：

- `structure = 0.35`
- `momentum = 0.25`
- `volume_price = 0.20`
- `pattern = 0.20`

实现要求：

- 先做子信号映射，再做加权分数
- `ADX` 可信度调节只影响动量项，不影响其他项
- `setup_state` 的否决条件只来自聚合层

`setup_state` 判定顺序：

1. 先看硬风险旗标
2. 再看 pattern / RR / breakout 等执行性条件
3. 最后落到 `actionable / watch / avoid`

---

## 4. 输出到当前 runtime 的映射

技术聚合器内部应先返回 richer 对象；模块总入口再映射为当前 `AnalysisModuleResult`：

- `direction <- technical_signal`
- `summary <- technical_summary`
- `data_completeness_pct`
- `low_confidence`
- `reason` 只在 degraded/excluded 时写

实现约束：

- 不要把 `setup_state` 丢进 `reason`
- richer 技术字段应进入未来 `report_json` 或内部 schema，不要提前塞进 node diagnostics

---

## 5. 当前迁移策略

推荐替换顺序：

1. 保留现有 node 和 `AnalysisModuleResult` 形状不动
2. 在分析层先引入 richer 聚合器
3. 用 richer 聚合器生成当前 summary
4. 等 response/persistence 层准备好后，再把结构化字段向外透传

---

## 6. 测试重点

- 子信号映射正确
- 权重与 ADX 调节正确
- `setup_state` 优先级正确
- degraded/excluded 子模块进入归一化后的行为正确
