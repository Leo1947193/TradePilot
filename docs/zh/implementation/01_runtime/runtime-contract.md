# Runtime 实现契约

## 1. 文档目标

本文定义 TradePilot 在运行时层面的实现契约，服务对象是后续 coding agent 与实现者。重点不是复述设计目标，而是把当前代码里已经固定下来的运行时事实写清楚：

- 单次请求如何从 HTTP 入口进入 LangGraph
- `TradePilotState` / `AnalysisGraphState` 的字段职责与生命周期
- 并行模块如何回写状态、如何 merge
- 哪些错误会中断主链路，哪些只能降级
- 当前实现与目标实现之间还存在什么差距

相关代码入口：

- `app/api/main.py`
- `app/graph/builder.py`
- `app/graph/nodes/*.py`
- `app/schemas/api.py`
- `app/schemas/graph_state.py`
- `tests/api/test_main.py`
- `tests/graph/**/*.py`

---

## 2. 单次请求生命周期

当前 V1 的一次同步请求固定走以下链路：

```text
POST /api/v1/analyses
-> AnalyzeRequest 校验
-> build_analysis_graph(...)
-> graph.invoke({"request": ...})
-> validate_request
-> prepare_context
-> run_technical / run_fundamental / run_sentiment / run_event 并行
-> synthesize_decision
-> generate_trade_plan
-> assemble_response
-> persist_analysis
-> 返回 AnalysisResponse
```

代码对应关系：

- HTTP 入口在 `app/api/main.py:create_analysis`
- graph 构建在 `app/graph/builder.py:build_analysis_graph`
- 每个节点实现位于 `app/graph/nodes/`
- 状态 schema 在 `app/schemas/graph_state.py`

运行时关键约束：

1. 这是同步请求链路，没有后台任务补偿。
2. `persist_analysis` 属于主链路的一部分；持久化失败时整个请求失败。
3. 所有中间结果都通过 graph state 传递，不通过全局变量或隐式上下文传递。
4. 当前 graph 没有 checkpoint、resume、streaming 或人工干预节点。

---

## 3. 运行时状态模型

### 3.1 双层状态定义

当前实现同时存在两层状态定义：

- `app/schemas/graph_state.py:TradePilotState`
  - 强类型 Pydantic 模型，节点内部校验和测试统一使用它
- `app/graph/builder.py:AnalysisGraphState`
  - LangGraph `TypedDict`，声明 graph reducer 和并行 merge 规则

实现约束：

- 节点函数可以接收 `TradePilotState | dict`
- 节点内部第一步通常是 `TradePilotState.model_validate(state)`
- graph 真正传播的是 `dict` 形态；wrapper 只把指定键回写到 LangGraph state

这意味着：

- 文档、实现和测试应以 `TradePilotState` 作为“语义真源”
- graph builder 上的 reducer 定义，才是并行 merge 的“执行真源”

### 3.2 顶层字段职责

| 字段 | 生产节点 | 消费节点 | 当前约束 |
|---|---|---|---|
| `request` | API 入口 / `validate_request` | 全链路 | 必须符合 `AnalyzeRequest` |
| `normalized_ticker` | `validate_request` | `prepare_context`、四个分析节点、`assemble_response`、`persist_analysis` | 规范化后必须是非空大写代码 |
| `request_id` | `validate_request` | `persist_analysis` | 若缺失或空白则生成 UUID |
| `context` | `prepare_context` | `run_event`、`assemble_response`、`persist_analysis` | 至少补齐 `analysis_time`、`market`、`benchmark`、`analysis_window_days` |
| `provider_payloads` | 当前无节点写入 | 当前无节点消费 | 预留字段，V1 尚未接通 |
| `module_results` | 四个分析节点 | `synthesize_decision`、`assemble_response`、`persist_analysis` | 每个模块最多一项最终聚合结果 |
| `decision_synthesis` | `synthesize_decision` | `generate_trade_plan`、`assemble_response`、`persist_analysis` | 缺失时后续节点必须失败 |
| `trade_plan` | `generate_trade_plan` | `assemble_response`、`persist_analysis` | 缺失时后续节点必须失败 |
| `response` | `assemble_response` | `persist_analysis`、API 入口 | 公共 HTTP 响应快照 |
| `sources` | provider-backed 模块节点、`assemble_response` | `assemble_response`、`persist_analysis` | 必须可去重且顺序稳定 |
| `persistence` | `persist_analysis` | API 目前不直接消费 | 记录持久化状态 |
| `diagnostics` | 四个分析节点 | `persist_analysis` | 当前用于降级/警告追踪 |

### 3.3 状态不变量

后续实现必须保持以下不变量：

1. `validate_request` 之后，`request.ticker` 与 `normalized_ticker` 必须一致，且已大写。
2. `prepare_context` 之后，`context.analysis_time` 必须带时区，当前统一为 UTC。
3. 任一模块节点只能写自己的 `module_results.<module>`，不能覆盖其他模块结果。
4. `synthesize_decision` 之后，`decision_synthesis.module_contributions` 必须固定四项，顺序固定为 `technical -> fundamental -> sentiment -> event`。
5. `generate_trade_plan` 不得重算方向，只消费 `decision_synthesis`。
6. `assemble_response` 之后，`response` 必须可被 `AnalysisResponse` 校验通过。
7. `persist_analysis` 之前，`response`、`decision_synthesis`、`trade_plan` 都必须已经存在。

---

## 4. 并行 merge 语义

并行 merge 语义由 `app/graph/builder.py` 决定，而不是由节点自己决定。

### 4.1 `module_results`

Reducer：`_merge_dict_updates`

规则：

- 浅层字典 merge
- 并行节点分别返回 `{ "module_results": { "<module>": ... } }`
- 最终结果是四个模块键合并后的字典

实现约束：

- 模块节点返回 payload 时，必须只包含自己的键
- 不要在模块节点里返回整个 `module_results` 快照，否则容易覆盖并行结果

### 4.2 `diagnostics`

Reducer：`_merge_diagnostics`

规则：

- 聚合四个列表字段：`degraded_modules`、`excluded_modules`、`warnings`、`errors`
- 去重但保持首次出现顺序

当前实现事实：

- 四个模块节点目前只会写 `degraded_modules` 和 `warnings`
- `excluded_modules` 与 `errors` 还没有被正式使用

### 4.3 `sources`

Reducer：`_merge_sources`

规则：

- 去重键为 `(type, name, str(url))`
- 合并后再按固定优先级排序
- 当前排序优先级：`technical -> financial -> news -> event -> macro`

补充说明：

- 各节点局部实现可能使用追加顺序，但 graph 层最终会重新排序
- `assemble_response` 会再做一次去重，保证输出稳定

### 4.4 其他字段

除 reducer 字段外，其余字段按串行写入使用：

- 一个字段只应由单个节点负责生产
- 后续节点如果不负责该字段，不得回写 `None` 或空对象清空它

---

## 5. 节点执行契约

### 5.1 输入形式

所有节点都必须支持：

- `TradePilotState`
- 可被 `TradePilotState.model_validate(...)` 校验通过的 `dict`

原因：

- 单元测试大量直接传 `dict`
- graph runtime 实际上传递的是 dict 风格 payload

### 5.2 输出形式

存在两种输出层次：

1. 节点函数本体返回 `TradePilotState`
2. builder wrapper 将其裁剪成最小回写 payload

例如：

- `_wrap_node(..., "decision_synthesis")` 只把 `decision_synthesis` 回写到 graph
- `_wrap_module_node(..., "technical")` 只回写：
  - `module_results.technical`
  - `diagnostics`
  - 可选 `sources`

实现要求：

- 节点函数可以返回完整状态，便于本地测试
- graph builder 必须控制真正写回 graph 的字段范围

### 5.3 同步/异步边界

当前节点函数都是同步函数，但 provider 接口是异步的。现有做法：

- 节点内通过 `_run_awaitable(...)`
- 无运行中 event loop 时使用 `asyncio.run`
- 已存在 event loop 时用单线程 `ThreadPoolExecutor` 包装 `asyncio.run`

这是一种“在同步 graph 中消费异步 provider”的适配层，而不是最终形态。

目标实现建议：

- 继续保持 graph 节点对外同步，或统一切换为异步 graph
- 但不要在多个节点里重复定义 `_run_awaitable`，应在后续 runtime 公共层收敛

---

## 6. 错误处理契约

### 6.1 请求校验错误

来源：

- FastAPI body 校验失败
- `AnalyzeRequest` 不满足 schema

对外行为：

- 返回 HTTP 400
- 统一错误码 `invalid_request`

见 `app/api/main.py:handle_request_validation_error`

### 6.2 节点前置条件错误

典型场景：

- `prepare_context` 缺少 `normalized_ticker`
- `generate_trade_plan` 缺少 `decision_synthesis`
- `assemble_response` 缺少 `analysis_time`

当前行为：

- 节点直接 `raise ValueError`
- graph invoke 失败
- API 统一返回 HTTP 500 / `internal_error`

实现含义：

- 这些错误被视为程序错误或运行时契约破坏，不是用户可恢复错误

### 6.3 provider 失败

当前四个分析节点的处理策略并不完全相同：

- `run_technical` / `run_fundamental` / `run_sentiment`
  - provider 出错或返回空结果时，降级为 placeholder `DEGRADED`
- `run_event`
  - 同时要求 `company_events_provider` 和 `macro_calendar_provider`
  - 抓到异常后回退到 degraded placeholder

这意味着当前实现优先保证链路可继续，而不是把 provider 异常上抛。

### 6.4 持久化失败

来源：

- `persist_analysis` 调用 repository 抛错

当前行为：

1. 节点内部把 `persistence` 标记为 `FAILED`
2. 紧接着抛出 `RuntimeError("analysis report persistence failed")`
3. graph 中断，API 返回：
   - 若根因是 `RepositoryUnavailableError`，返回 503 / `upstream_unavailable`
   - 其他情况返回 500 / `internal_error`

关键约束：

- 当前 API 不会把“响应已生成但持久化失败”的半成功结果返回给客户端

---

## 7. 当前实现与目标实现

### 7.1 当前实现已经固定的部分

- graph 拓扑和节点顺序已固定
- 四模块默认都是核心模块
- `decision_synthesis` 与 `trade_plan` 已具备稳定 schema
- provider-backed 与 placeholder 模式可共存
- `AnalysisResponse` 的对外字段已经稳定

### 7.2 当前实现仍是占位或过渡态的部分

| 主题 | 当前实现 | 目标实现 |
|---|---|---|
| `provider_payloads` | schema 已预留，但没有节点写入 | 各 provider 标准化结果应显式入 state |
| 模块细节 | `module_results` 只有统一摘要，不含各子模块明细 | 后续需要更丰富但仍受控的内部契约 |
| diagnostics | 主要记录 degraded warning | 需要扩展到 excluded / timeout / invalid_field / fallback 原因 |
| event 模块 | 聚合逻辑较轻量，未完整映射 design 中的风险旗标 | 需要对齐设计文档的事件型 blocking flags |
| persistence 失败恢复 | 失败即整条请求失败 | 后续若要半成功返回，需要单独设计 API 语义 |
| provider 调用适配 | 每个节点各自定义 `_run_awaitable` | 应抽到共享 runtime/provider 层 |

---

## 8. 后续 coding agent 的落地规则

修改 runtime 相关代码时，优先遵守以下顺序：

1. 先改 `app/schemas/graph_state.py` 或 `app/schemas/api.py`，明确字段语义。
2. 再改节点实现，保证单节点在本地测试可独立工作。
3. 再改 `app/graph/builder.py`，只处理 graph 级拓扑与 reducer。
4. 最后补 `tests/graph/` 与 `tests/api/`，验证链路级行为。

不要做的事：

- 不要让模块节点直接写别的模块结果
- 不要在 `generate_trade_plan` 里回读原始 provider 数据
- 不要把 API 错误语义分散到节点里，各节点只负责抛出明确异常
- 不要让 public API 直接暴露未收敛的内部状态字段

---

## 9. 最小验证清单

对 runtime 代码的任何改动，至少应验证：

1. `tests/graph/test_builder.py`
2. `tests/graph/nodes/test_validate_request.py`
3. `tests/graph/nodes/test_prepare_context.py`
4. `tests/graph/nodes/test_synthesize_decision.py`
5. `tests/graph/nodes/test_generate_trade_plan.py`
6. `tests/graph/nodes/test_assemble_response.py`
7. `tests/graph/nodes/test_persist_analysis.py`
8. `tests/api/test_main.py`

如果改动涉及状态字段或 schema，还应补：

- `tests/schemas/test_graph_state_models.py`
- `tests/schemas/test_api_response_models.py`
