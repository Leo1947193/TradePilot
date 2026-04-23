# 可观测性与诊断实现契约

## 1. 文档目标

本文档定义 implementation 阶段必须保留的诊断对象、错误可见性和联调检查项。

本项目当前还没有正式日志体系，因此本文优先定义：

- `TradePilotState.diagnostics` 的语义
- degraded / excluded / failed 的边界
- 后续日志与 trace 应如何围绕这些结构展开

---

## 2. 当前可观测性事实

当前仓库里，最稳定的诊断对象不是日志，而是 state：

- `diagnostics.degraded_modules`
- `diagnostics.excluded_modules`
- `diagnostics.warnings`
- `diagnostics.errors`
- `persistence.status`
- `persistence.error`

这些字段已经被 schema、node tests、repository payload 共同使用。

这意味着当前阶段的诊断主轴应是：

1. 先把 state 诊断语义写死
2. 后续日志再围绕 state 输出，而不是反过来让日志成为事实来源

---

## 3. 三类非 happy path 的边界

### 3.1 `degraded`

表示：

- 模块继续产出结果
- 结果可被综合层消费
- 但数据源、完整度或规则能力不足

当前实例：

- `run_technical` 在 provider 缺失或失败时返回 degraded
- `run_fundamental`、`run_sentiment`、`run_event` 也是同一模式

要求：

- degraded 必须写模块结果
- degraded 必须进入 `diagnostics.degraded_modules`
- degraded 原因应通过 `summary/reason/warnings` 至少暴露一层

### 3.2 `excluded`

表示：

- 模块被显式纳入请求或主链路
- 但本次结果不应计入综合打分

当前代码里 `excluded` schema 已存在，但真实写入路径还较少。

要求：

- excluded 必须进入 `diagnostics.excluded_modules`
- excluded 不得伪装成 degraded
- excluded 的原因必须结构化，不能只留自然语言摘要

### 3.3 `failed`

表示：

- 节点执行失败，主链路中断，不返回成功响应

当前最清晰的例子是 `persist_analysis`：

- repository 抛错后，节点内部会把 `persistence.status` 设为 `failed`
- 随后抛 `RuntimeError`
- API 层把这类异常映射到 `503` 或 `500`

要求：

- failed 不得被当作模块级可消费结果
- failed state 可以用于节点内部诊断，但不会作为成功 graph 输出返回 API

---

## 4. `diagnostics` 字段职责

### 4.1 `degraded_modules`

职责：

- 记录哪些模块以 degraded 方式完成
- 支撑 synthesis 风险提示与后续联调排查

要求：

- 模块名使用稳定 id：`technical`、`fundamental`、`sentiment`、`event`
- 去重且顺序稳定

### 4.2 `excluded_modules`

职责：

- 记录哪些模块被明确排除
- 让综合层和排查工具知道“缺结果是有意的”

要求：

- 不用它来记录 provider 超时或代码异常

### 4.3 `warnings`

职责：

- 记录非阻断但影响结果质量的提示

当前例子：

- `Technical analysis degraded: provider-backed market data is not available yet.`

要求：

- warning 面向调试与联调
- 允许自然语言
- 但同一 warning 必须幂等去重

### 4.4 `errors`

职责：

- 记录节点内已识别、但未必立刻抛出的结构化错误

当前现状：

- schema 已有字段，但真实使用仍较少

目标要求：

- 后续若引入 recoverable error，应优先写入 `errors`
- `errors` 中建议使用稳定 machine-readable id，而不是长句

---

## 5. 节点级诊断要求

后续每个 graph node 都应明确回答 4 个问题：

1. 成功时写哪些 diagnostics？
2. degraded / excluded 时写哪些 diagnostics？
3. fail-fast 时抛什么异常？
4. 该异常在 API 层是否对外可见？

### 5.1 当前需要继续保持的节点行为

- `validate_request`
  - 直接失败，不写模块级 degraded
- `prepare_context`
  - 直接失败，不静默回退
- `run_technical` / `run_fundamental` / `run_sentiment` / `run_event`
  - 优先 degraded 回退
  - 写 `degraded_modules` 与 `warnings`
- `synthesize_decision`
  - 产出系统级风险列表，不修改 persistence
- `generate_trade_plan`
  - 缺 `decision_synthesis` 时直接失败
- `assemble_response`
  - 缺上游必需字段时直接失败
- `persist_analysis`
  - 节点内部记录 failed，再抛异常

---

## 6. 日志与 trace 的目标态要求

当前代码没有统一日志框架，后续引入日志时建议最少包含：

- `request_id`
- `normalized_ticker`
- `node_name`
- `module_name`
- `status`
- `degraded_modules`
- `excluded_modules`
- `persistence.status`

原则：

- 日志只镜像 state 诊断，不创造第二套语义
- 任何核心诊断字段都必须能回映到 state 或 persisted payload

---

## 7. API 层错误可见性

当前 API 层对异常的对外可见规则应继续保持：

- `400`
  - 请求结构错误
- `404`
  - ticker 无法映射到受支持标的
- `422`
  - 无法建立最小分析上下文
- `503`
  - persistence 不可用
- `500`
  - 内部未预期失败

要求：

- 不把模块 degraded 暴露成 HTTP error
- 模块 degraded 应体现在成功响应内容与 diagnostics / risks 中

---

## 8. 联调检查清单

后续联调时，每次至少检查：

1. 四模块结果是否都存在
2. degraded / excluded 模块是否进入 diagnostics
3. `DecisionSynthesis.risks` 是否反映关键质量问题
4. `TradePlan.do_not_trade_conditions` 是否与综合层约束一致
5. `sources` 是否去重且与 provider 输入一致
6. 持久化成功时 `persistence.status = succeeded`
7. 持久化失败时 API 是否返回 `503/500`，而不是假成功

---

## 9. 建议新增的诊断测试

进入 richer 实现阶段后，优先新增：

- diagnostics 去重与顺序测试
- excluded 模块进入综合层时的权重测试
- recoverable error 写入 `diagnostics.errors` 的测试
- persistence failed 与 API 状态码映射测试
- `source_trace/evidence` 在 response 与 DB 中的一致性测试

---

## 10. 不建议的做法

- 只依赖日志判断模块是否 degraded
- 用模糊自然语言代替稳定错误 id
- 让模块失败静默掉，不写 diagnostics 也不抛错
- 在多个节点里对同一错误重复发明不同命名

---

## 11. 完成标准

当 observability / diagnostics 被认为“足够支撑真实编码与联调”时，至少应满足：

- degraded、excluded、failed 三类边界清晰
- diagnostics 字段职责固定
- 节点异常与 API 错误可见性有稳定映射
- 后续日志体系有明确的 state 对齐基线
