# 技术分析模块实现架构

## 1. 文档目标

本文档定义技术分析模块在实现阶段的代码拆分、输入输出契约和迁移路径。目标是指导真实编码，而不是重复 design 中的指标定义。

当前实现入口：

- [`app/analysis/technical.py`](/Users/leo/Dev/TradePilot/app/analysis/technical.py:1)
- [`app/graph/nodes/run_technical.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_technical.py:1)
- [`tests/graph/nodes/test_run_technical.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_technical.py:1)

---

## 2. 当前实现事实

当前仓库只有一个占位分析函数：

- 输入：`MarketBar[]`
- 计算：价格涨跌幅 + 近 20 根均值
- 输出：`TechnicalSignal(direction, summary, data_completeness_pct, low_confidence)`

这意味着当前代码还没有真正实现：

- 日线/周线结构
- RSI / MACD / ADX / 相对强度
- OBV / 突破破位 / 背离
- 形态识别
- ATR / Beta / IV 风险指标

后续实现必须把这些能力补进分析层，而不是继续把复杂规则堆在 `run_technical.py`。

---

## 3. 推荐代码组织

推荐把单文件演进为子包：

```text
app/analysis/technical/
  __init__.py
  schemas.py
  module.py
  aggregate.py
  multi_timeframe.py
  momentum.py
  volume_price.py
  patterns.py
  risk_metrics.py
```

职责划分：

- `schemas.py`
  - 技术模块内部子结果 schema
- `module.py`
  - 模块总入口；只负责编排 5 个子模块并返回聚合结果
- `aggregate.py`
  - 子信号映射、权重、`technical_signal`、`setup_state`、模块 summary
- `multi_timeframe.py`
  - 日线/周线结构、均线排列、支撑阻力
- `momentum.py`
  - RSI / MACD / ADX / benchmark 相对强度
- `volume_price.py`
  - OBV、背离、量价确认
- `patterns.py`
  - 形态识别、触发价、止损、目标价、RR
- `risk_metrics.py`
  - ATR / Beta / 布林带宽度 / 回撤 / IV vs HV / 风险旗标

实现约束：

- graph node 仍只调用模块总入口，不直接调用子模块
- 所有子模块只消费标准化数据集，不直接访问 provider 实现
- 最终仍要能映射回当前 `AnalysisModuleResult`

---

## 4. 输入数据契约

当前 runtime 只能稳定提供：

- `MarketBar[]`：个股日线

目标实现至少需要：

- `daily_bars`
- `weekly_bars`
- `benchmark_bars`
- `option_snapshot` 或 `iv_inputs`
- `short_interest_inputs`（可后补）

实现建议：

1. 不在技术子模块内部做第三方 provider 调用。
2. 周线数据优先在 dataset adapter 中从日线重采样，而不是在子模块里重复生成。
3. benchmark 选择优先使用 `context.benchmark`，当前默认 `SPY`。
4. 衍生数据缺失时允许子模块降级，但不能阻塞整个技术模块。

---

## 5. 输出契约

模块内部应先输出两层结果：

1. 子模块结果
2. 聚合后的 `TechnicalAggregateResult`

`TechnicalAggregateResult` 至少应包含：

- `technical_signal`
- `trend`
- `setup_state`
- `summary`
- `data_completeness_pct`
- `low_confidence`
- `risk_flags`
- `key_support`
- `key_resistance`
- `volume_pattern`
- `entry_trigger`
- `target_price`
- `stop_loss_price`
- `risk_reward_ratio`
- `subsignals`

然后再由模块总入口把它映射为当前 graph 可消费的：

- `AnalysisModuleResult(module="technical", ...)`
- 未来扩展的 `report_json`

---

## 6. 与 runtime 的对接方式

`run_technical` 只保留四件事：

1. 校验 `normalized_ticker` 和数据窗口
2. 调 dataset adapter / provider 取得标准化输入
3. 调 `app.analysis.technical.module.analyze_technical_module(...)`
4. 处理 `usable / degraded / excluded` 与 diagnostics

不要继续把以下逻辑留在 node：

- 技术指标计算
- 汇总权重
- public summary 生成
- risk flag 细化

---

## 7. 分阶段迁移顺序

推荐编码顺序：

1. 先落 `schemas.py` 与 `aggregate.py`
2. 再落 `multi_timeframe.py` 和 `momentum.py`
3. 再落 `volume_price.py`
4. 再落 `risk_metrics.py`
5. 最后落 `patterns.py`

原因：

- 聚合器和基础结构先稳定，后续 node 和测试才有锚点
- `patterns.py` 依赖最多，应该最后接入

---

## 8. 测试落点

至少补以下测试层：

- `tests/analysis/technical/test_multi_timeframe.py`
- `tests/analysis/technical/test_momentum.py`
- `tests/analysis/technical/test_volume_price.py`
- `tests/analysis/technical/test_patterns.py`
- `tests/analysis/technical/test_risk_metrics.py`
- `tests/analysis/technical/test_aggregate.py`
- 现有 [`test_run_technical.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_technical.py:1) 保留，改为覆盖 node 契约而不是算法细节
