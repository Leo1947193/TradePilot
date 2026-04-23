# 基本面模块聚合实现契约

## 1. 目标

聚合器负责：

- 先执行否决门
- 再计算 `composite_score`
- 再生成 `fundamental_bias`
- 提取 `key_risks`
- 计算 `data_completeness_pct`

当前仓库没有这个独立层；现有 `analyze_financial_snapshot(...)` 只是占位版统一打分。

---

## 2. 输入

- `EarningsMomentumResult`
- `FinancialHealthResult`
- `ValuationAnchorResult`

固定权重：

- `earnings = 0.45`
- `health = 0.35`
- `valuation = 0.20`

---

## 3. 实现步骤

1. 先评估三个子模块是 `usable / degraded / excluded`。
2. 先读 `financial_health.disqualify`。
3. 若触发且时效有效，直接输出：
   - `fundamental_bias = disqualified`
   - `composite_score = 0`
4. 若未触发，再对可用模块做权重归一化。
5. 根据 design 阈值产出 `bullish / neutral / bearish`。

实现约束：

- `Disqualified` 不是普通 bearish；必须保留枚举语义
- `available_weight_sum < 0.70` 时只能输出 `neutral` 或 `disqualified`

---

## 4. 输出到当前 runtime 的映射

当前 `AnalysisModuleResult.direction` 已支持 `disqualified`，因此聚合器应直接映射，而不是在 node 层二次解释。

建议模块入口返回：

- richer `FundamentalAggregateResult`
- 当前兼容 `AnalysisModuleResult`

---

## 5. 测试重点

- 否决门先于打分
- 权重归一化
- `available_weight_sum < 0.70` 压制
- `key_risks` 去重与优先级
- `disqualified` 到 `AnalysisModuleResult` 的映射
