# LangGraph 设计契约

## 1. 目标

本文档定义 V1 的 LangGraph 主图结构，回答 coding agent 最关心的问题：

- graph state 长什么样
- 节点怎么拆
- 哪些节点并行
- 哪些节点允许降级

Graph 的业务输出仍需满足：

- [../api/openapi.yaml](../api/openapi.yaml)
- [../design/system-architecture.md](../design/system-architecture.md)

---

## 2. V1 总体结构

V1 主图固定为一张单请求分析图：

```text
validate_request
  -> prepare_context
  -> [run_technical, run_fundamental, run_sentiment, run_event]
  -> synthesize_decision
  -> generate_trade_plan
  -> assemble_response
  -> persist_analysis
```

约束：

- `prepare_context` 之后开始并行
- `synthesize_decision` 必须等四个分析分支都结束
- `generate_trade_plan` 只能消费决策综合结果
- `assemble_response` 负责组装顶层 API 对象
- `persist_analysis` 负责把最终分析结果写入 `PostgreSQL`

---

## 3. Graph State

V1 内部 state 最少包含以下字段：

```text
TradePilotState = {
  request: AnalyzeRequest,
  normalized_ticker: string | null,
  request_id: string,

  context: {
    analysis_time: string | null,
    market: string | null,
    benchmark: string | null,
    analysis_window_days: [number, number] | null
  },

  provider_payloads: {
    market: object | null,
    financial: object | null,
    news: object | null,
    company_events: object | null,
    macro_calendar: object | null
  },

  module_results: {
    technical: object | null,
    fundamental: object | null,
    sentiment: object | null,
    event: object | null
  },

  decision_synthesis: object | null,
  trade_plan: object | null,
  response: object | null,
  sources: object[],

  persistence: {
    status: "pending" | "succeeded" | "failed",
    record_id: string | null,
    persisted_at: string | null,
    error: string | null
  },

  diagnostics: {
    degraded_modules: string[],
    excluded_modules: string[],
    warnings: string[],
    errors: string[]
  }
}
```

---

## 4. 节点职责

### 4.1 `validate_request`

负责：

- 校验请求体
- 标准化 ticker
- 生成 `request_id`

失败行为：

- 直接结束请求

### 4.2 `prepare_context`

负责：

- 准备分析时间
- 确定市场与 benchmark
- 获取最小公共上下文
- 决定是否能进入并行分析

失败行为：

- 返回 `404`、`422` 或 `503`

### 4.3 `run_technical`

负责：

- 拉取并标准化技术分析所需数据
- 生成技术模块聚合结果
- 写入来源信息

允许：

- `degraded`
- `excluded`

### 4.4 `run_fundamental`

负责：

- 拉取并标准化基本面所需数据
- 生成基本面模块聚合结果
- 写入来源信息

允许：

- `degraded`
- `excluded`

### 4.5 `run_sentiment`

负责：

- 拉取并标准化新闻数据
- 生成情绪模块聚合结果
- 写入来源信息

允许：

- `degraded`
- `excluded`

### 4.6 `run_event`

负责：

- 拉取公司事件和宏观日历
- 生成事件模块聚合结果
- 写入来源信息

允许：

- `degraded`
- `excluded`

### 4.7 `synthesize_decision`

负责：

- 标准化四个模块结果
- 生成 `decision_synthesis`

输入：

- `module_results`

输出：

- `decision_synthesis`

### 4.8 `generate_trade_plan`

负责：

- 消费 `decision_synthesis`
- 生成双向 `trade_plan`

禁止：

- 重新计算总体方向

### 4.9 `assemble_response`

负责：

- 映射顶层公共 API 结构
- 校验响应模型
- 去重和排序 `sources`

失败行为：

- 视为内部错误

### 4.10 `persist_analysis`

负责：

- 将请求信息、模块结果、决策综合结果、交易计划和顶层响应快照写入 `PostgreSQL`
- 写入持久化结果标记，如 `record_id` 和 `persisted_at`

输入：

- `request`
- `module_results`
- `decision_synthesis`
- `trade_plan`
- `response`

失败行为：

- 视为依赖失败或内部错误，不允许静默跳过

---

## 5. 并行与同步边界

### 5.1 并行节点

以下四个节点必须并行执行：

- `run_technical`
- `run_fundamental`
- `run_sentiment`
- `run_event`

### 5.2 串行节点

以下节点必须串行：

- `validate_request`
- `prepare_context`
- `synthesize_decision`
- `generate_trade_plan`
- `assemble_response`
- `persist_analysis`

原因：

- 前两者是前置条件
- 后四者依赖并行分支的聚合结果

---

## 6. 错误与降级策略

### 6.1 节点输出规范

分析节点发生非致命失败时，不抛出未处理异常，而是写入：

- 模块状态
- 失败原因
- 可用的部分来源信息

### 6.2 致命失败

以下节点一旦失败，应直接终止 graph：

- `validate_request`
- `prepare_context`
- `assemble_response`
- `persist_analysis`

### 6.3 决策层前置条件

进入 `synthesize_decision` 前，必须保证：

- `module_results` 四个键始终存在
- 每个键要么是模块结果，要么是受控降级结果

禁止让决策层自己猜测某个模块是否“没跑”。

---

## 7. Checkpoint 与结果持久化

V1 固定策略：

- 不启用持久化 checkpointer
- 不保留 LangGraph 线程状态
- graph 执行完成后内存中的 state 随请求结束释放
- 仅最终分析结果与报告快照写入 `PostgreSQL`

说明：

- 这和 V1 同步单请求 API 保持一致
- “结果持久化”不等于“graph 可恢复”
- 后续若切换异步任务制，再单独设计持久化 graph

---

## 8. Graph 与 API 的解耦要求

Graph state 不得直接暴露到 HTTP 响应。

必须通过 `assemble_response` 做显式映射，原因是：

- state 结构服务于编排
- API 结构服务于客户端
- 两者演进速度不同

禁止做法：

- 直接 `return state`
- 让节点直接写最终顶层 JSON

---

## 9. coding agent 的默认建图顺序

coding agent 应按以下顺序实现 graph：

1. 定义 `TradePilotState`
2. 实现 `validate_request`
3. 实现 `prepare_context`
4. 放入四个空分析节点，先返回 mock 结果
5. 实现 `synthesize_decision`
6. 实现 `generate_trade_plan`
7. 实现 `assemble_response`
8. 实现 `persist_analysis`
9. 再逐步替换 mock provider 与 mock 分析逻辑
