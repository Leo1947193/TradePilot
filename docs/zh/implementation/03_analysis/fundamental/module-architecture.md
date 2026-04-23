# 基本面模块实现架构

## 1. 文档目标

本文档定义基本面模块在实现阶段的代码拆分、输入数据契约和迁移顺序。

当前实现入口：

- [`app/analysis/fundamental.py`](/Users/leo/Dev/TradePilot/app/analysis/fundamental.py:1)
- [`app/graph/nodes/run_fundamental.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_fundamental.py:1)
- [`tests/graph/nodes/test_run_fundamental.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_fundamental.py:1)

---

## 2. 当前实现事实

当前只有单次 `FinancialSnapshot` 的占位分析：

- 统计 7 个字段是否存在
- 用净利润、EPS、毛利率、营业利润率、PE 做简单正负计数
- 输出统一 `FundamentalSignal`

这离 design 目标差距很大。当前还没有：

- 季度序列
- 一致预期修正
- 指引变化
- 现金流与杠杆红旗
- 历史估值分位与同行比较
- `Disqualified` 的真实否决门

---

## 3. 推荐代码组织

推荐演进为：

```text
app/analysis/fundamental/
  __init__.py
  schemas.py
  module.py
  aggregate.py
  earnings_momentum.py
  financial_health.py
  valuation_anchor.py
```

职责：

- `schemas.py`
  - 三个子模块结果 + 聚合结果 schema
- `module.py`
  - 基本面模块总入口
- `aggregate.py`
  - 权重、否决门、`fundamental_bias`、`key_risks`
- `earnings_momentum.py`
  - 盈利兑现、修正、指引
- `financial_health.py`
  - 现金流、流动性、杠杆、硬风险
- `valuation_anchor.py`
  - 历史分位、同行相对、PEG、空间标签

---

## 4. 输入数据契约

当前稳定输入只有：

- `FinancialSnapshot`

目标实现至少要新增：

- `quarterly_results`
- `revision_summary`
- `current_quarter_consensus`
- `guidance_history`
- `cashflow_and_balance_sheet_snapshot`
- `valuation_snapshot`
- `valuation_history`
- `peer_multiples`

实现要求：

- 基本面子模块只消费标准化数据集，不直接消费 provider 原始 dict
- dataset adapter 要先负责 `staleness_days` 和 `missing_fields`
- 单次 `FinancialSnapshot` 只能作为 V1 fallback，不应再作为目标态主输入

---

## 5. 输出契约

模块内部聚合结果至少应包含：

- `fundamental_bias`
- `composite_score`
- `key_risks`
- `data_completeness_pct`
- `low_confidence_modules`
- `weight_scheme_used`
- `subresults`

然后由模块入口映射到当前 `AnalysisModuleResult`：

- `direction <- fundamental_bias`
- `summary`
- `data_completeness_pct`
- `low_confidence`

实现约束：

- 若触发 `Disqualified`，聚合层必须显式产出，而不是靠 summary 暗示
- 当前 graph/runtime 尚未完全接受 richer 基本面对象，因此先在分析层保留双层输出

---

## 6. 与 runtime 的对接方式

`run_fundamental` 应逐步收敛为：

1. 取标准化基本面数据集
2. 调 `analyze_fundamental_module(...)`
3. 映射回 `AnalysisModuleResult`
4. 处理 degraded/excluded 与 source

不要在 node 中继续实现：

- 分数计算
- key risks 拼接
- 否决门判断

---

## 7. 编码顺序

推荐顺序：

1. `schemas.py`
2. `aggregate.py`
3. `financial_health.py`
4. `earnings_momentum.py`
5. `valuation_anchor.py`

原因：

- 否决门由 `financial_health` 驱动，应该比其他子模块先稳定

---

## 8. 测试落点

- `tests/analysis/fundamental/test_earnings_momentum.py`
- `tests/analysis/fundamental/test_financial_health.py`
- `tests/analysis/fundamental/test_valuation_anchor.py`
- `tests/analysis/fundamental/test_aggregate.py`
- 现有 [`test_run_fundamental.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_fundamental.py:1) 继续保留 node 契约测试
