# Golden Cases 实现说明

## 1. 文档目标

本文档定义 golden case 在本项目中的职责、组织方式与落地顺序。

golden case 的目标是：

- 为规则型系统提供稳定回归基线
- 在设计继续演进时，防止 coding agent 改出“看起来合理、实际上偏了”的输出
- 让 `03_analysis`、`04_synthesis`、`05_trade_plan` 的关键行为能跨层回放

---

## 2. 为什么当前阶段必须引入 golden cases

本项目不只是 CRUD 或简单 API，它的核心风险是规则漂移：

- 技术、基本面、情绪、事件各自会持续补规则
- 综合层会继续引入压制链和阻断标记
- trade plan 会继续接入 richer anchor

如果只有散点单元测试，会出现两个问题：

1. 每条规则都测了，但模块组合后的结果悄悄变了
2. 自然语言摘要、risk 列表、condition id、actionability 在重构后漂移

golden case 的职责就是补这个空白。

---

## 3. golden case 的覆盖对象

golden case 不覆盖所有随机输入，只覆盖“必须长期稳定”的代表性场景。

推荐覆盖 4 层输出：

1. `AnalysisModuleResult`
2. `DecisionSynthesis`
3. `TradePlan`
4. `AnalysisResponse` 的关键字段切片

实现要求：

- 不要求保存完整响应全文
- 只保存后续实现真正需要稳定的结构化字段

---

## 4. 推荐目录结构

推荐在测试目录新增：

```text
tests/golden/
├── fixtures/
│   ├── technical/
│   ├── fundamental/
│   ├── sentiment/
│   ├── event/
│   └── pipeline/
├── test_technical_golden_cases.py
├── test_fundamental_golden_cases.py
├── test_sentiment_golden_cases.py
├── test_event_golden_cases.py
├── test_synthesis_golden_cases.py
└── test_trade_plan_golden_cases.py
```

原则：

- fixture 与断言文件分离
- 模块级 case 与跨层 pipeline case 分离

---

## 5. 单个 golden case 的结构

每个 case 建议固定为：

```yaml
id: technical_bullish_breakout_001
scope: technical
input:
  ...
expected:
  module_result:
    status: usable
    direction: bullish
    data_completeness_pct: 92
    low_confidence: false
  key_markers:
    - breakout
    - volume_confirmed
notes: >
  用于锁定多周期结构与价量确认同时支持看多时的聚合输出。
```

### 5.1 必填字段

- `id`
- `scope`
- `input`
- `expected`

### 5.2 `expected` 中应优先锁定

- `status`
- `direction` / `overall_bias`
- `data_completeness_pct`
- `low_confidence`
- `conflict_state`
- `actionability_state`
- `blocking_flags`
- `do_not_trade_conditions`

### 5.3 不建议直接锁定

- 完整 summary 自然语言全文
- provider 原始 payload 全量内容
- 与实现无关的排序噪音字段

---

## 6. 第一批必须落的 golden cases

### 6.1 technical

- 明确看多突破
- 明确看空破位
- 信号冲突但非完全失效
- 数据不全导致 degraded

### 6.2 fundamental

- 盈利动量 + 财务健康共振看多
- 估值一般但基本面强，最终仍 bullish
- 关键财务字段缺失导致 degraded
- `disqualified` 基本面否决 case

### 6.3 sentiment

- 新闻基调持续改善
- 预期变化转弱
- 文章数量不足导致 low confidence
- 热门叙事拥挤但方向未翻转

### 6.4 event

- 近端财报 / 宏观高敏感事件压制
- 公司催化剂偏正面
- 公司与宏观事件混合但净偏空
- provider 空结果或异常导致 degraded

### 6.5 synthesis

- 四模块一致看多
- technical bullish 与 event bearish 冲突
- available weight 不足
- 全部 degraded

### 6.6 trade plan

- actionable bullish
- watch bearish
- avoid neutral
- `blocking_flags` 透传为 `do_not_trade_conditions`

---

## 7. golden case 与普通单元测试的分工

普通单元测试负责：

- 一个规则、一个阈值、一个边界

golden case 负责：

- 一个完整场景在跨函数、跨层聚合后仍稳定

因此不要把 golden case 写成替代单元测试的“大而全断言”。

---

## 8. 当前阶段的实现建议

当前代码还处于 placeholder-heavy 阶段，golden case 应分两步做。

### 8.1 第一阶段

先给当前已稳定的输出结构建 case：

- `synthesize_decision`
- `generate_trade_plan`
- provider-backed / degraded 的四个 `run_*` node

这样可以先锁：

- `status`
- `direction`
- `confidence_score`
- `actionability_state`
- `do_not_trade_conditions`

### 8.2 第二阶段

等 `03_analysis` 真正拆成 richer 子模块后，再为每个模块补更细的 fixture。

---

## 9. case 更新规则

golden case 不是快照越多越好，必须受控更新。

更新前必须回答：

1. 这是设计变更，还是实现回归？
2. 若是设计变更，是否先同步 implementation 文档？
3. 若是实现回归，为什么旧 case 不再正确？

要求：

- 不允许在没有文档与代码依据的情况下直接重录 expected
- 更新 golden case 时，PR 说明必须写清“为什么该变”

---

## 10. 断言策略

推荐优先断言：

- 枚举值
- 数值区间或精确边界
- condition id 集合与顺序
- 风险标记集合

对文案类字段建议：

- 优先断关键词或短 marker
- 只对明确要求稳定的模板化文案做全文断言

---

## 11. 与 persistence / observability 的关系

golden case 不直接替代 persistence 测试，也不替代日志测试。

但当后续引入：

- `source_trace`
- `evidence`
- richer diagnostics

应新增 pipeline golden case，锁定这些结构在：

- module result
- decision synthesis
- response / persisted payload

之间不会丢失。

---

## 12. 完成标准

当 golden case 体系开始可用时，至少应满足：

- 四分析模块各有至少 2 个代表场景
- synthesis 至少有 4 个系统级代表场景
- trade plan 至少覆盖 `actionable/watch/avoid`
- 每个 golden case 都能说明它要防止哪类回归
