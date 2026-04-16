# API 文档概览

## 1. 目标

`docs/zh/api` 用于定义 TradePilot 对外暴露的 HTTP API 契约。

这些文档基于以下设计文档收敛而成：

- [设计概述](../design/overview.md)
- [系统架构](../design/system-architecture.md)
- [决策综合层](../design/decision_synthesis_layer/overview.md)
- [交易计划生成器](../design/trade_plan_generator/overview.md)

设计文档描述的是内部模块边界和中间结果；本目录描述的是客户端可直接调用和联调的对外接口。

本目录同时提供两种 API 契约表达：

- Markdown 说明文档：便于人类阅读和审查
- [OpenAPI 规范](./openapi.yaml)：便于生成 SDK、Mock 和联调工具配置

若要直接进入编码实现，还应同时阅读：

- [../implementation/implementation-stack.md](../implementation/implementation-stack.md)
- [../implementation/runtime-contract.md](../implementation/runtime-contract.md)
- [../implementation/data-sources.md](../implementation/data-sources.md)
- [../implementation/langgraph-graph.md](../implementation/langgraph-graph.md)

---

## 2. V1 范围

当前 V1 只定义一个业务接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/analyses` | 输入股票代码，返回完整结构化分析结果 |

当前版本**不对外暴露**模块级子 Agent 接口、评分调试接口或原始数据拉取接口。

### 2.1 实现框架说明

项目实现层使用 `LangGraph` 作为编排框架。

对外 API 与内部 graph 之间的关系如下：

- 一次 `POST /api/v1/analyses` 请求，对应一次完整的 graph 执行
- graph 内部负责串联数据校验、上下文准备、并行分析、决策综合和交易计划生成
- V1 只暴露最终业务结果，不暴露内部节点名称、状态快照、检查点或运行时调试信息

这意味着：

- API 契约优先于具体 graph 节点实现
- 允许后续在不破坏对外接口的前提下调整内部节点拆分、执行策略或状态结构

---

## 3. 设计原则

### 3.1 单一输入

V1 请求体只接收 `ticker`，与 PRD 保持一致，不额外开放策略、权重或窗口参数。

### 3.2 确定性输出

同一输入、同一数据快照、同一规则版本下，应返回相同结构和相同枚举语义的 JSON。

### 3.3 对外契约优先于内部实现

内部设计文档中存在大小写和字段粒度差异，例如：

- `bullish` / `bearish` / `neutral`
- `Bullish` / `Bearish` / `Neutral`
- `Disqualified`

对外 HTTP API 统一做以下收敛：

- 枚举统一使用小写
- 顶层字段命名统一使用稳定业务语义
- 仅暴露对客户端有意义的结构化结果，不直接泄露内部子模块实现细节

### 3.4 人类可读与机器可读并存

响应必须同时包含：

- 机器可消费字段，如 `overall_bias`、`actionability_state`
- 人类可读摘要，如 `technical_summary`、`event_summary`
- 可追溯来源，如 `sources`

### 3.5 LangGraph 与接口解耦

虽然系统内部使用 `LangGraph`，但 HTTP API 不直接复用 LangGraph 原生对象作为对外响应。

对外返回必须保持：

- 稳定 JSON 结构
- 稳定字段命名
- 稳定枚举语义

不得把以下内部实现细节直接暴露为公共契约：

- graph state 原始结构
- 节点级中间消息
- 内部运行 ID、checkpoint ID、线程状态
- 仅用于编排的临时字段

---

## 4. 通用约定

### 4.1 协议与格式

- 请求与响应格式均为 `application/json`
- 字符编码统一为 `UTF-8`
- 时间字段统一使用 `ISO 8601` UTC 时间戳

### 4.2 股票代码

- `ticker` 由服务端先做 `trim`
- 对外推荐使用大写，例如 `AAPL`、`MSFT`
- 服务端应拒绝空字符串和明显非法代码

### 4.3 枚举

除特殊说明外，外部 API 的枚举值一律使用小写，例如：

- `bullish`
- `neutral`
- `bearish`
- `actionable`
- `watch`
- `avoid`

### 4.4 错误返回

所有非 `2xx` 响应统一返回：

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": []
  }
}
```

详细字段见 [schemas.md](./schemas.md)。

---

## 5. 阅读顺序

1. 先读 [analyses.md](./analyses.md)，确认唯一业务接口的请求与返回行为
2. 再读 [schemas.md](./schemas.md)，确认字段、枚举和错误契约
3. 最后读 [openapi.yaml](./openapi.yaml)，获取机器可读的正式接口定义
4. 若开始实现，再读 `../implementation` 目录中的 4 份实现级文档
