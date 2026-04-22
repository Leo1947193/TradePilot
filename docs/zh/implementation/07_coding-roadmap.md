# 编码顺序与迭代边界

## 1. 文档目标

本文档不复述产品设计，而是把 `docs/zh/prd`、`docs/zh/design`、`docs/zh/implementation` 已经确定的约束，整理成一份可直接指导真实编码推进的路线文档，明确三件事：

- 先写什么，后写什么
- 当前阶段的目标是什么
- 每一轮开发允许做什么，不允许越界做什么

本文默认遵守以下既有前提：

- 对外仍只有 `POST /api/v1/analyses`
- 主链路固定为  
  `validate_request -> prepare_context -> run_technical/run_fundamental/run_sentiment/run_event -> synthesize_decision -> generate_trade_plan -> assemble_response -> persist_analysis`
- 四个分析模块是平级核心模块，`event` 不是可选能力
- `DecisionSynthesis` 和 `TradePlan` 的 public shape 短期保持稳定

---

## 2. 当前阶段判断

基于现有实现文档和当前代码，仓库当前不是“从 0 到 1 的架构设计阶段”，而是：

**骨架已定、规则偏轻、模块仍以 placeholder 为主的真实编码前中期阶段。**

当前已经稳定的部分：

- `FastAPI + Pydantic v2 + LangGraph + PostgreSQL + uv` 技术栈
- 单入口 API、固定 graph 拓扑、provider 注入方式、持久化主链路
- `AnalyzeRequest` / `AnalysisResponse` / `DecisionSynthesis` / `TradePlan` 这些公共契约
- 模块降级、sources merge、diagnostics、repository 写入顺序等基础运行时语义

当前尚未完成的部分：

- 四个分析模块的真实规则实现
- `04_synthesis` 的独立输入适配层、评分层、输出层
- `05_trade_plan` 的约束层、场景层、锚点解析层
- `source_trace`、`evidence`、golden case、richer diagnostics
- 模块 richer 输出到公共响应和持久化的完整接线

### 当前阶段目标

当前阶段的目标不是继续讨论“系统要不要这样设计”，而是把现有可运行骨架收口成**可持续增量开发的平台**：

- 锁死对外契约和主链路
- 把散落在 node 内的规则拆回 analysis / adapter / rules 层
- 为四个模块的真实实现准备稳定输入面和测试基线
- 让 `synthesis` 与 `trade_plan` 先具备可承接 richer 模块输出的内部结构
- 在不扩 public API 的前提下，逐轮把 placeholder 模块替换为真实规则模块

### 当前阶段禁止项

- 不新增业务入口或扩 `AnalyzeRequest`
- 不改变主链路节点顺序
- 不把 provider、repository 或 API 层变成业务规则层
- 不先做大规模重构再补规则
- 不为了后续可能的能力，提前引入新基础设施、后台任务或第二套运行方式

---

## 3. 总体编码顺序

推荐按下面顺序推进，而不是按“想到哪个模块就先写哪个模块”推进。

1. **先锁契约与基线，再补实现。**  
   先把 API、graph、node、docs contract、基础测试锁住，再进入 richer 规则编码。

2. **先补 runtime/data/synthesis/trade plan 的承接层，再补四个分析模块。**  
   否则模块一旦 richer 化，很快又会把逻辑塞回 node，或者让输出 shape 再漂一次。

3. **四个分析模块按 `technical -> fundamental -> sentiment -> event` 顺序推进。**  
   这是当前系统默认模块顺序，也最符合依赖关系：
   - `technical` 权重最高，后续还要给 trade plan 提供锚点
   - `fundamental` 最早影响 `disqualified` 与系统级压制
   - `sentiment` 依赖标准化和去重层，适合在前两者之后落
   - `event` 要接通受控 `blocking_flags`，适合在前面规则和适配层稳定后接入

4. **最后做 richer 集成收口，而不是每个模块做完就立刻扩 public API。**  
   richer 输出先在模块内部和 persistence JSON 稳定，再决定哪些字段进入公共响应。

5. **最后一轮才做 golden case 和 observability 收口。**  
   否则 case 会随着规则骨架变化频繁重录，信号价值很低。

---

## 4. 推荐迭代拆分

### Round 0: 契约冻结与基线补强

本轮目标：

- 确认 `docs/zh/prd`、`docs/zh/design`、`docs/zh/implementation` 的主链路和边界一致
- 把当前已经稳定的 public contract、graph topology、node fail-fast 语义锁成测试基线

本轮工作：

- 校准并补齐 schema / node / graph / docs contract 测试
- 明确哪些字段和 condition id 短期不能改名
- 明确哪些实现事实只是过渡态，不能被误写成目标态

完成标准：

- 现有 public schema、graph 顺序、主要 node 契约有直接测试
- coding agent 可以在不猜测主链路的前提下继续编码

本轮禁止：

- 不改 public API shape
- 不做模块 richer 规则实现
- 不引入新的 provider 体系或新的持久化语义

---

### Round 1: Runtime / Rules / Data Spine 收口

本轮目标：

- 把后续所有 richer 规则都会复用的公共脊柱先搭好

本轮工作：

- 新增并收敛 `app/rules/`，把权重、阈值、窗口、诊断文案、版本号从各文件中抽离
- 明确 dataset adapter / normalization 入口，统一 `normalized_ticker`、UTC、`analysis_time`、`fetched_at`、`staleness_days`
- 继续保持 graph node 小而同步，只做校验、调 adapter、调 analysis、维护 diagnostics

完成标准：

- 核心阈值和稳定文案不再散落在 node / analysis 函数内部
- 后续四个模块都能消费“标准化输入”而不是 provider 原始 payload

本轮禁止：

- 不在 provider 内计算模块结论
- 不把 `source_trace` / `evidence` 直接扩成新 public schema
- 不在这一轮扩 richer 模块算法

---

### Round 2: 决策综合层内化

本轮目标：

- 把 `04_synthesis` 从“node 里的一坨逻辑”拆成可测试、可承接 richer 模块输出的内部层

本轮工作：

- 新增 `app/analysis/synthesis/`
- 落 `schemas.py`、`adapt.py`、`scoring.py`、`output.py`
- 引入 `NormalizedModuleSignal`
- 保留当前 public `DecisionSynthesis` shape，不在这一轮改字段名

完成标准：

- `synthesize_decision` node 只负责调适配层、评分层、输出层
- `bias_score`、`conflict_state`、`confidence_score`、`actionability_state` 的计算顺序固定
- richer 模块输出未来能以“适配层输入”接入，而不是继续靠 summary 猜

本轮禁止：

- 不让 `trade_plan` 直接读 `module_results`
- 不把 `blocking_flags` 继续长期维持为自由字符串集合
- 不在这一轮扩 public `DecisionSynthesis`

---

### Round 3: 交易计划层基线收口

本轮目标：

- 让 `05_trade_plan` 先完成“结构正确、边界正确”，即使还没有价格锚点

本轮工作：

- 新增 `app/analysis/trade_plan/`
- 先落 `schemas.py`、`constraints.py`、`scenarios.py`、`module.py`
- 显式拆开 `actionable / watch / avoid` 三种模板层级
- 保持 `DecisionSynthesis -> TradePlan` 的单向依赖

完成标准：

- `do_not_trade_conditions` 生成顺序和去重逻辑固定
- 当前已稳定的 condition id 保持不变
- `watch` 与 `avoid` 不再共用同一套模板语义

本轮禁止：

- 不在没有 planning context 的情况下伪造价格锚点
- 不重算方向
- 不从 `module_results` 或 provider payload 回读信息

---

### Round 4: 技术模块真实化

本轮目标：

- 先把权重最高、同时又是 trade plan 锚点主要来源的技术模块补成真实规则模块

本轮工作：

- 把 `app/analysis/technical.py` 演进为子包
- 推荐顺序：`schemas.py -> aggregate.py -> multi_timeframe.py -> momentum.py -> volume_price.py -> risk_metrics.py -> patterns.py`
- 先产出 `setup_state`、`risk_flags`、关键支撑阻力和触发锚点，再考虑更复杂形态

完成标准：

- `run_technical` node 只做输入校验、数据准备、模块调用、degraded/excluded 处理
- 技术模块能稳定产出后续 `synthesis` 和 `trade_plan` 所需的结构化字段

本轮禁止：

- 不在子模块里直接调 provider
- 不把复杂技术规则塞回 `run_technical.py`
- 不立即扩 public technical payload；先让内部输出稳定

---

### Round 5: 基本面模块真实化

本轮目标：

- 接通基本面否决门、关键风险和 richer 子模块，为系统级压制链准备真实输入

本轮工作：

- 把 `app/analysis/fundamental.py` 演进为子包
- 推荐顺序：`schemas.py -> aggregate.py -> financial_health.py -> earnings_momentum.py -> valuation_anchor.py`
- 优先把 `disqualified`、`key_risks`、完整度和低置信度的结构化输出做实

完成标准：

- 基本面聚合层可以稳定给 `synthesis` 提供 `disqualified`、风险与完整度信号
- node 不再自己拼 summary 或计算否决门

本轮禁止：

- 不继续依赖单一 summary 承载所有子维度含义
- 不直接在 `synthesize_decision` 里硬编码基本面特例

---

### Round 6: 情绪模块真实化

本轮目标：

- 先解决标准化和去重，再解决评分；避免情绪层长期被标题关键词命中绑死

本轮工作：

- 把 `app/analysis/sentiment.py` 演进为子包
- 推荐顺序：`normalize.py -> schemas.py -> news_tone.py -> aggregate.py -> expectation_shift.py -> narrative_crowding.py`
- 在内部保留 `dedupe_cluster_id`、`source_trace`、`classifier_version` 这类后续可追溯字段

完成标准：

- 情绪模块的方向、预期变化和拥挤度来自标准化输入，而不是 provider 原始文章列表
- `run_sentiment` node 只承担模块调用和回退逻辑

本轮禁止：

- 不引入 LLM 依赖来替代规则层
- 不把标题去重、相关性过滤继续留在 node 或 provider

---

### Round 7: 事件模块真实化

本轮目标：

- 把事件模块从“简单事件计数器”补成系统级阻断与执行性约束的正式输入源

本轮工作：

- 把 `app/analysis/event.py` 演进为子包
- 推荐顺序：`schemas.py -> aggregate.py -> scheduled_events.py -> macro_sensitivity.py -> company_catalysts.py`
- 先把 `event_risk_flags` 做成受控结构，再补 richer 事件对象

完成标准：

- 事件模块能够显式产出近端风险、催化剂和系统可消费的 risk flag
- `blocking_flags` 不再主要靠“事件方向是 bearish/disqualified”这种捷径推断

本轮禁止：

- 不让事件模块去解释价格行为
- 不把宏观敏感性逻辑塞进 sentiment 或 fundamental
- 不继续把受控阻断条件编码成自由文本

---

### Round 8: Richer 集成回接

本轮目标：

- 把四个 richer 模块输出重新接回 `04_synthesis`、`05_trade_plan`、`assemble_response`、`persistence`

本轮工作：

- 用真实模块字段补齐 `NormalizedModuleSignal`
- 接通方向压制链、受控 `blocking_flags`、`actionability_state`
- 接通 `technical_context` / `event_context` 到 trade plan 的只读锚点解析
- 决定哪些 richer 字段进入 response，哪些先只进入 persistence JSON
- 开始落 `source_trace`、`evidence` 到模块级 `report_json`

完成标准：

- `synthesis` 不再依赖 summary 猜模块状态
- `trade_plan` 可以消费只读锚点，但仍不重算方向
- response / persistence / diagnostics 之间的字段流向清晰

本轮禁止：

- 不新增业务 endpoint
- 不把 `trade_plan` 变成综合层的第二实现
- 不把 persistence 改成异步后台最佳努力写入

---

### Round 9: 质量收口与回归基线

本轮目标：

- 在 richer 规则和 richer 输出都接通后，补齐长期可回归的测试和诊断基线

本轮工作：

- 按 `06_quality` 落 L1-L6 测试补强
- 引入 `tests/golden/` 的第一批 golden cases
- 增补 diagnostics、excluded/degraded/failed、sources/source_trace/evidence 一致性测试
- 做 API、graph、repository 的回归收口

完成标准：

- 核心规则变化可以被单元测试、node 测试、golden case 至少一层直接捕获
- 系统具备稳定的 diagnostics 和回归能力

本轮禁止：

- 不在没有文档依据的情况下重录 golden case
- 不只补 end-to-end 测试而跳过规则层测试

---

## 5. 每轮开发的统一边界

无论当前处于哪一轮，都应遵守以下边界：

- **先锁输入输出，再写算法。** 每轮先明确 schema、adapter、node contract，再补规则实现。
- **node 只做编排，不做业务堆积。** 复杂规则必须回到 `app/analysis/` 或 `app/rules/`。
- **provider 只负责取数和 DTO 映射。** 不在 provider 内做评分、冲突处理或交易计划推导。
- **trade plan 永远只消费系统级结论。** 即使后续接入技术/事件上下文，也只能补锚点和说明。
- **public shape 稳定优先于内部 shape 漂亮。** 内部可以逐轮演进，公共字段短期不要频繁改名。
- **降级只允许发生在四个分析模块。** `validate_request`、`prepare_context`、`assemble_response`、`persist_analysis` 仍应 fail-fast。

---

## 6. 推荐的里程碑判断

如果要判断当前是否可以“进入下一大阶段”，建议按下面三个里程碑看，而不是按文件数量看。

### Milestone A: 可持续编码基线建立

满足条件：

- Round 0-3 完成
- 契约、runtime、synthesis、trade plan 基线稳定
- coding agent 不需要猜 node 边界和 public shape

### Milestone B: 核心规则模块可用

满足条件：

- Round 4-7 完成
- 四个分析模块都有 richer 内部输出
- `synthesis` 的方向、冲突、执行性已经主要消费结构化字段，而不是 summary

### Milestone C: V1 收口可联调

满足条件：

- Round 8-9 完成
- richer 输出完成 response / persistence / diagnostics 接线
- golden cases 和回归测试足以保护后续迭代

---

## 7. 最终建议

如果只允许现在立刻启动一轮真实编码，**推荐从 Round 0-3 开始，而不是直接扑向四个模块的细节算法**。

原因很简单：

- 现有主链路和 public contract 已经基本固定
- 当前最大的风险不是“没有更多规则”，而是“规则一多就再次把边界打乱”
- 只有先把 `rules -> adapter -> synthesis -> trade_plan` 这条内部承接链稳定下来，后面的技术、基本面、情绪、事件模块实现才不会反复返工
