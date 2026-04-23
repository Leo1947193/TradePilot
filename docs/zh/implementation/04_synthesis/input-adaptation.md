# 决策综合输入适配实现契约

## 1. 文档目标

本文档定义 `04_synthesis` 的入口适配层，回答三个实现问题：

- 四个分析模块的最终结果如何统一成可综合的内部结构
- 当前仓库已经在做哪些适配，哪些还没做
- 后续 coding agent 应把适配逻辑放在哪，而不是继续散落在 `synthesize_decision.py`

相关代码：

- [`app/graph/nodes/synthesize_decision.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/synthesize_decision.py:1)
- [`app/schemas/modules.py`](/Users/leo/Dev/TradePilot/app/schemas/modules.py:1)
- [`app/schemas/api.py`](/Users/leo/Dev/TradePilot/app/schemas/api.py:1)
- [`tests/graph/nodes/test_synthesize_decision.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_synthesize_decision.py:1)

---

## 2. 当前实现事实

当前仓库没有独立的“输入适配层”文件。实际适配逻辑散落在：

- `_build_module_contribution(...)`
- `_map_direction(...)`
- `_map_direction_value(...)`
- `_resolve_data_completeness(...)`

当前它直接从 `AnalysisModuleResult` 映射出 public `ModuleContribution`，而不是先生成 design 中的 `normalized_module_signal`。

当前已经实现的适配行为：

- `result is None` -> `enabled = false`、`status = not_enabled`
- `usable/degraded` 会进入可用模块集合
- `excluded/not_enabled` 不进入 `available_weight_sum`
- `disqualified` 只通过 `AnalysisDirection.DISQUALIFIED` 映射成 `FundamentalBias.DISQUALIFIED`

当前还没有实现的适配行为：

- 单独的适配层 schema
- 模块级 `blocking_flags`、`diagnostic_flags`、`key_risks` 统一输入面
- design 要求的关键字段校验和非法枚举排除逻辑
- “字段缺失导致 excluded”的显式原因编码

---

## 3. 推荐代码组织

推荐新增：

```text
app/analysis/synthesis/
  __init__.py
  schemas.py
  adapt.py
  scoring.py
  output.py
```

其中本文件对应：

- `schemas.py`
  - `NormalizedModuleSignal`
- `adapt.py`
  - 四个模块结果到 `NormalizedModuleSignal` 的显式映射

`synthesize_decision.py` 后续只负责：

1. 调 `adapt_module_signals(...)`
2. 调 `score_decision(...)`
3. 调 `build_decision_output(...)`

不要继续把适配、评分、输出拼装耦在同一个 node 文件里。

---

## 4. 目标内部结构

建议新增内部 schema：

```text
NormalizedModuleSignal(
  module,
  enabled,
  status,
  direction,
  direction_value,
  configured_weight,
  data_completeness_pct,
  low_confidence,
  blocking_flags,
  diagnostic_flags,
  key_risks,
  summary,
)
```

与当前 public `ModuleContribution` 的区别：

- `ModuleContribution` 是输出对象
- `NormalizedModuleSignal` 是综合层内部对象

后续评分层只消费 `NormalizedModuleSignal`，不要直接依赖 `AnalysisModuleResult`。

---

## 5. 从当前模块结果到内部结构的映射

### 5.1 技术模块

当前输入只有：

- `status`
- `direction`
- `data_completeness_pct`
- `low_confidence`
- `summary`
- `reason`

当前缺口：

- 没有 `setup_state`
- 没有结构化 `risk_flags`
- 没有 design 里的 `technical_signal`

因此当前阶段的适配规则应是：

- 方向来自 `AnalysisModuleResult.direction`
- `blocking_flags = []`
- `key_risks = []`
- `summary <- summary/reason`

目标态：

- 由技术聚合器显式提供 `setup_state` 和 risk flags
- 适配层再把 `technical_setup_avoid` 映射到系统级 `blocking_flags`

### 5.2 基本面模块

当前阶段：

- `direction = bullish/neutral/bearish/disqualified`
- `disqualified` 已能合法进入综合层

当前缺口：

- 没有结构化 `key_risks`
- 没有 `low_confidence_modules`

当前适配规则应保守处理：

- `direction = disqualified` -> `direction_value = -1`
- 先不伪造 `fundamental_long_disqualified`，除非聚合器显式输出该阻断原因

目标态：

- 基本面聚合器显式输出 `key_risks`
- 适配层再把 `disqualified` 转成受控系统级 `blocking_flags`

### 5.3 情绪模块

当前阶段只有：

- `direction`
- `summary`
- `data_completeness_pct`
- `low_confidence`

当前缺口：

- `market_expectation`
- `key_risks`
- `composite_score`

因此当前适配层只能保留最小方向信号，不应凭 summary 反推预期变化。

### 5.4 事件模块

当前阶段：

- `direction`
- `summary`
- `data_completeness_pct`
- `low_confidence`

当前实现并没有 design 里的 `event_risk_flags`。

当前代码实际做法是：

- 只要 event module 方向为 `bearish/disqualified`，后续 `_build_blocking_flags(...)` 就写入 `event_risk_block`

这是一个实现级捷径，不等于 design 契约。

目标态：

- 事件聚合器先输出受控 `event_risk_flags`
- 适配层再透传这些 flag，不再靠 direction 猜阻断

---

## 6. 状态判定

当前仓库的状态判定比 design 简化很多：

- `result is None` -> `not_enabled`
- `status in {usable, degraded}` -> available
- `status = excluded` -> unavailable

后续应显式补齐：

1. `not_enabled`
2. `excluded`
3. `degraded`
4. `usable`

实现要求：

- 判定顺序固定，避免后续把低置信度覆盖成 excluded
- `status` 映射必须保留与 [`ModuleExecutionStatus`](/Users/leo/Dev/TradePilot/app/schemas/modules.py:13) 一致

---

## 7. 完整度与低置信度口径

当前实现：

- `usable + completeness None` -> 100
- `degraded + completeness None` -> 70
- `excluded` -> 0
- `not_enabled` -> null

这套代理值已经被：

- `data_completeness_pct`
- `module_contributions`
- `risks`

共同依赖，所以在真正的适配层落地前，不能随意改。

建议把这些代理值迁移到：

- `app/rules/decision.py`

由适配层显式读取，而不是继续硬编码在 node 文件里。

---

## 8. 当前实现与目标实现差异

| 主题 | 当前实现 | 目标实现 |
|---|---|---|
| 输入统一结构 | 无独立结构 | `NormalizedModuleSignal` |
| 模块字段校验 | 主要依赖 Pydantic schema | 适配层显式校验关键字段与非法枚举 |
| 系统级阻断输入 | 仅由后续评分层简单推导 | 适配层保留模块级 `blocking_flags` |
| 诊断标记 | 无显式 `diagnostic_flags` | 显式区分系统级阻断和实现诊断 |
| key risks 透传 | 尚未接通 | 各模块显式透传 |

---

## 9. 编码顺序

推荐顺序：

1. 先定义 `NormalizedModuleSignal`
2. 再写四个模块的适配函数
3. 再把 `synthesize_decision.py` 改成先适配再评分
4. 最后更新 tests

---

## 10. 测试重点

- `None -> not_enabled`
- `excluded` 模块不参与 available 权重
- `disqualified -> direction_value = -1`
- completeness 代理值稳定
- 当前轻量输入与目标态 richer 输入都能被同一适配层消费
