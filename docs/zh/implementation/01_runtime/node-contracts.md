# 节点实现契约

## 1. 文档目标

本文逐个定义 `app/graph/nodes/` 下节点的编码级契约：

- 节点职责
- 最小输入
- 输出字段
- 快速失败条件
- 副作用
- 当前实现状态
- 后续扩展注意事项

如果后续要改节点逻辑，优先改这里对应的契约，而不是先改 graph 拓扑。

---

## 2. 共通约束

所有节点共享以下规则：

1. 入参类型允许 `TradePilotState | dict`。
2. 节点内部应先做 `TradePilotState.model_validate(...)`。
3. 节点本体返回完整 `TradePilotState`，真正写回 graph 的字段由 builder wrapper 决定。
4. 节点只负责自己的字段，不负责 graph merge。
5. 缺少前置字段时应直接抛 `ValueError`，不要隐式补默认值绕过契约。

---

## 3. `validate_request`

代码：

- `app/graph/nodes/validate_request.py`
- `tests/graph/nodes/test_validate_request.py`

### 3.1 职责

- 规范化 `request.ticker`
- 生成或保留 `request_id`
- 写入 `normalized_ticker`

### 3.2 最小输入

```json
{
  "request": {
    "ticker": " aapl "
  }
}
```

### 3.3 输出字段

- `request`
- `normalized_ticker`
- `request_id`

### 3.4 规则

- `ticker` 先 `strip()` 再 `upper()`
- 规范化后为空串时必须失败
- 已存在且非空白的 `request_id` 必须保留
- 缺失或空白 `request_id` 时生成 UUID

### 3.5 快速失败

- 空白 ticker：`ValueError("request ticker must not be blank after normalization")`

### 3.6 当前实现备注

- 节点会先在 `_prepare_state_payload` 阶段对空白 ticker 做一次提前检查
- 然后再通过 `TradePilotState` 完整校验

### 3.7 后续扩展建议

- 若未来要支持市场前缀、别名或 symbol mapping，应继续放在本节点完成
- 不要把市场识别逻辑塞到 API 层

---

## 4. `prepare_context`

代码：

- `app/graph/nodes/prepare_context.py`
- `tests/graph/nodes/test_prepare_context.py`

### 4.1 职责

- 为后续分析补齐统一上下文

当前默认值：

- `market = "US"`
- `benchmark = "SPY"`
- `analysis_window_days = (7, 90)`
- `analysis_time = datetime.now(timezone.utc)`

### 4.2 前置条件

- `normalized_ticker` 必须存在且非空

### 4.3 输出字段

- `context`

### 4.4 保留行为

- 已有合法 `context` 字段应优先保留
- 与 `context` 无关的现有字段不得被修改

### 4.5 快速失败

- `normalized_ticker` 缺失或空白：`ValueError("normalized_ticker is required to prepare context")`

### 4.6 当前实现备注

- 这是第一个真正写业务上下文字段的节点
- 后续 event 模块强依赖 `context.market` 和 `context.analysis_window_days`

### 4.7 后续扩展建议

- 如果后续引入行业、时区、交易所日历等上下文，继续集中放在这里
- 不要在各分析节点里各自补默认上下文

---

## 5. `run_technical`

代码：

- `app/graph/nodes/run_technical.py`
- `app/analysis/technical.py`
- `tests/graph/nodes/test_run_technical.py`

### 5.1 职责

- 运行技术分析模块
- 产出 `module_results.technical`
- 必要时更新 `diagnostics`
- provider 启用且成功时附带 `sources`

### 5.2 前置条件

严格前置条件较弱；当前允许缺少 provider，节点会自动走 degraded placeholder。

若启用 provider-backed 路径，则依赖：

- `normalized_ticker`
- `context.analysis_window_days`

### 5.3 输出字段

- `module_results.technical`
- `diagnostics`
- 可选 `sources`

### 5.4 当前实现分支

分为两条路径：

1. provider-backed 路径
   - 调用 `market_data_provider.get_daily_bars(...)`
   - 成功取到 bars 后执行 `analyze_market_bars(...)`
   - 输出 `status = usable`
2. placeholder 路径
   - provider 缺失、抛错、返回空 bars 时进入
   - 输出 `status = degraded`
   - 追加 diagnostics warning

### 5.5 诊断规则

degraded 时写入：

- `diagnostics.degraded_modules += ["technical"]`
- `diagnostics.warnings += ["Technical analysis degraded: ..."]`

provider-backed 成功时会尝试移除本模块已有 degraded/warning。

### 5.6 source 规则

- 仅当第一根 bar 的 `source.url` 非空时写入 `Source(type="technical", ...)`
- graph builder 还要求 `market_data_provider is not None` 才会把 `sources` 回写到 graph

### 5.7 快速失败

当前 provider-backed 路径内部不会因 provider 异常上抛；异常会被吞掉并走 degraded。

### 5.8 当前实现备注

- 该节点目前只产出统一摘要和方向，没有把多周期、形态、支撑阻力等设计级细节沉入 state
- 这是当前 runtime 与技术设计文档之间的主要缺口之一

---

## 6. `run_fundamental`

代码：

- `app/graph/nodes/run_fundamental.py`
- `app/analysis/fundamental.py`
- `tests/graph/nodes/test_run_fundamental.py`

### 6.1 职责

- 运行基本面分析模块
- 产出 `module_results.fundamental`
- 更新 `diagnostics`
- 成功时附带 financial source

### 6.2 前置条件

- provider 缺失时允许降级
- provider-backed 路径要求 `normalized_ticker`

### 6.3 输出字段

- `module_results.fundamental`
- `diagnostics`
- 可选 `sources`

### 6.4 当前实现分支

1. provider-backed
   - 调用 `financial_data_provider.get_financial_snapshot(...)`
   - 成功后执行 `analyze_financial_snapshot(...)`
   - 输出 `status = usable`
2. placeholder
   - provider 缺失、抛错或返回 `None`
   - 输出 `status = degraded`

### 6.5 source 规则

- 使用 snapshot 上的 `source`
- 写入 `Source(type="financial", ...)`

### 6.6 当前实现备注

- 当前 direction 只有 `bullish/neutral/bearish`
- 设计文档里的 `disqualified` 语义尚未在模块层真正产出
- 后续若引入 `disqualified`，要同步检查：
  - `app/schemas/modules.py`
  - `synthesize_decision`
  - `build_public_module_payloads`

---

## 7. `run_sentiment`

代码：

- `app/graph/nodes/run_sentiment.py`
- `app/analysis/sentiment.py`
- `tests/graph/nodes/test_run_sentiment.py`

### 7.1 职责

- 运行情绪分析模块
- 产出 `module_results.sentiment`
- 更新 `diagnostics`
- 成功时附带 news source

### 7.2 前置条件

- provider 缺失时允许降级
- provider-backed 路径要求 `normalized_ticker`

### 7.3 当前实现分支

1. provider-backed
   - `news_data_provider.get_company_news(..., limit=5)`
   - 成功后执行 `analyze_news_sentiment(...)`
2. placeholder
   - provider 缺失、异常或空新闻时降级

### 7.4 输出字段

- `module_results.sentiment`
- `diagnostics`
- 可选 `sources`

### 7.5 当前实现备注

- 当前实现主要基于标题/摘要关键词命中
- design 中的 `expectation_shift`、`narrative_crowding` 细粒度结构尚未进入 runtime state

---

## 8. `run_event`

代码：

- `app/graph/nodes/run_event.py`
- `app/analysis/event.py`
- `tests/graph/nodes/test_run_event.py`

### 8.1 职责

- 运行事件分析模块
- 产出 `module_results.event`
- 在 provider-backed 成功时产出 event/macro sources

### 8.2 前置条件

若走 provider-backed 路径，必须同时满足：

- `normalized_ticker`
- `context.market`
- `context.analysis_window_days`
- `company_events_provider is not None`
- `macro_calendar_provider is not None`

### 8.3 当前实现分支

1. provider-backed
   - 并发拉取 company events 与 macro events
   - 调用 `analyze_event_inputs(...)`
   - 输出 `status = usable`
2. placeholder
   - 任一 provider 缺失时直接降级
   - provider-backed 过程中异常时递归回退到 degraded placeholder

### 8.4 输出字段

- `module_results.event`
- `diagnostics`
- 可选 `sources`

### 8.5 source 规则

- company events 映射成 `SourceType.EVENT`
- macro events 映射成 `SourceType.MACRO`
- 本地节点内先 merge 去重，graph 层还会再次去重排序

### 8.6 快速失败

仅在“provider 已齐全但缺少上下文字段”时会抛 `ValueError`：

- `normalized_ticker is required for event analysis`
- `context.market is required for event analysis`
- `context.analysis_window_days is required for event analysis`

### 8.7 当前实现备注

- 当前 event 模块还没有把 design 中的事件风险旗标完整映射到 `decision_synthesis.blocking_flags`
- 目前系统级 `event_risk_block` 只是在综合层根据 event direction 为 bearish/disqualified 时简单生成

---

## 9. `synthesize_decision`

代码：

- `app/graph/nodes/synthesize_decision.py`
- `app/analysis/decision.py`
- `tests/graph/nodes/test_synthesize_decision.py`

### 9.1 职责

- 读取四模块聚合结果
- 生成系统级 `decision_synthesis`

### 9.2 最小输入

理论上只需要 `module_results`；但完整链路下还会带着已有 `request`、`sources`、`diagnostics` 等字段进入。

### 9.3 输出字段

- `decision_synthesis`

### 9.4 规则

当前实现固定：

- 配置权重：technical 0.5 / fundamental 0.1 / sentiment 0.2 / event 0.2
- `usable` 与 `degraded` 都算 available
- `excluded` 与 `not_enabled` 不参与 applied weight
- `module_contributions` 固定输出四项
- `bias_score` 为 contribution 求和后保留两位
- `risk` 列表根据可用性和低置信度生成

### 9.5 当前实现与设计差异

- 当前 `overall_bias` 阈值是 `>= 0.15 / <= -0.15`
- design 文档给出的目标阈值是更保守的 `> 0.30 / < -0.30`
- 当前实现没有按 design 文档把 `available_weight_ratio < 0.70`、`data_completeness_pct < 60`、`conflict_state = conflicted` 统一压制为 neutral

因此，后续 coding agent 在改这一层时，必须同步更新：

- 节点实现
- 决策分析 helper
- 对应测试
- 本目录其余 runtime 文档

---

## 10. `generate_trade_plan`

代码：

- `app/graph/nodes/generate_trade_plan.py`
- `app/analysis/trade_plan.py`
- `tests/graph/nodes/test_generate_trade_plan.py`

### 10.1 职责

- 将 `decision_synthesis` 映射为 `trade_plan`

### 10.2 前置条件

- `decision_synthesis` 必须存在

### 10.3 输出字段

- `trade_plan`

### 10.4 快速失败

- `decision_synthesis` 缺失：`ValueError("decision_synthesis is required to generate trade plan")`

### 10.5 当前实现备注

- 当前 plan 生成完全基于系统级字段
- 还没有消费技术锚点和事件上下文
- 这是符合 design 边界的，但实现深度仍是 placeholder

后续扩展时必须保持：

- 方向不重算
- 双向场景始终都输出
- `do_not_trade_conditions` 由系统级约束驱动

---

## 11. `assemble_response`

代码：

- `app/graph/nodes/assemble_response.py`
- `app/analysis/response.py`
- `tests/graph/nodes/test_assemble_response.py`

### 11.1 职责

- 将内部状态映射为公共 `AnalysisResponse`
- 去重并固定 `sources`

### 11.2 前置条件

- `normalized_ticker`
- `context.analysis_time`
- `decision_synthesis`
- `trade_plan`

缺一不可。

### 11.3 输出字段

- `response`
- `sources`（去重后的最终版本）

### 11.4 快速失败

- `normalized_ticker is required to assemble response`
- `context.analysis_time is required to assemble response`
- `decision_synthesis is required to assemble response`
- `trade_plan is required to assemble response`

### 11.5 当前实现备注

- 该节点通过 `build_public_module_payloads(...)` 把 `module_results` 转成四个 public 子对象
- 当前很多 public 字段仍是 placeholder：
  - `key_support = []`
  - `key_resistance = []`
  - `upcoming_catalysts = []`
  - `risk_events` 主要来自统一 risk flags，而不是结构化事件列表

---

## 12. `persist_analysis`

代码：

- `app/graph/nodes/persist_analysis.py`
- `tests/graph/nodes/test_persist_analysis.py`

### 12.1 职责

- 组装 `AnalysisReportPayload`
- 调用 repository 持久化分析报告
- 写回 `persistence`

### 12.2 前置条件

- `response`
- `decision_synthesis`
- `trade_plan`
- `normalized_ticker`
- `context.analysis_time`

### 12.3 输出字段

- `persistence`

### 12.4 快速失败

缺少任一前置字段时直接抛 `ValueError`。

repository 报错时：

- 当前实现会先在节点内部把 `persistence` 设为 `FAILED`
- 然后抛 `RuntimeError("analysis report persistence failed")`

### 12.5 当前实现备注

- 由于节点最终会抛异常，graph 不会把这个 failed state 当作成功结果继续传下去，API 也不会返回它
- `persistence` 更像内部审计字段，而不是当前对外可见状态

---

## 13. 节点改造优先级建议

如果后续要把 runtime 从“可运行 placeholder”推进到“可指导真实编码”，推荐顺序：

1. 扩充四个 `run_*` 节点的 provider-backed 输出深度
2. 对齐 `synthesize_decision` 与 design 的评分/压制规则
3. 让 `generate_trade_plan` 消费更多已结构化的锚点字段
4. 最后再扩充 `assemble_response` 的公共输出细节

原因：

- 前三步决定系统是否真的能做出正确结论
- `assemble_response` 只是把已有内部结果对外映射
