# 响应组装与 API 映射

## 1. 文档目标

本文定义从内部 graph state 到公共 HTTP 响应的映射契约，覆盖两层：

1. `assemble_response` 如何把内部状态组装成 `AnalysisResponse`
2. `app/api/main.py` 如何把 graph 结果映射为 HTTP 成功/失败响应

相关代码：

- `app/graph/nodes/assemble_response.py`
- `app/analysis/response.py`
- `app/api/main.py`
- `app/schemas/api.py`
- `tests/graph/nodes/test_assemble_response.py`
- `tests/api/test_main.py`

---

## 2. 内部到公共响应的组装入口

组装入口是：

- 节点：`app/graph/nodes/assemble_response.py:assemble_response`
- helper：`app/analysis/response.py:build_public_module_payloads`

运行顺序：

```text
TradePilotState
-> 校验必需字段
-> sources 去重
-> build_public_module_payloads(state)
-> 生成 AnalysisResponse
-> 将 response 与去重后的 sources 回写 state
```

当前 `AnalysisResponse` 顶层字段固定为：

- `ticker`
- `analysis_time`
- `technical_analysis`
- `fundamental_analysis`
- `sentiment_expectations`
- `event_driven_analysis`
- `decision_synthesis`
- `trade_plan`
- `sources`

---

## 3. 顶层字段映射

| 响应字段 | 内部来源 | 备注 |
|---|---|---|
| `ticker` | `state.normalized_ticker` | 必须已大写规范化 |
| `analysis_time` | `state.context.analysis_time` | 必须存在且带时区 |
| `technical_analysis` | `build_public_module_payloads(state)[0]` | 来自 `module_results.technical` + `decision_synthesis.actionability_state` |
| `fundamental_analysis` | `build_public_module_payloads(state)[1]` | 来自 `module_results.fundamental` + contribution |
| `sentiment_expectations` | `build_public_module_payloads(state)[2]` | 来自 `module_results.sentiment` |
| `event_driven_analysis` | `build_public_module_payloads(state)[3]` | 来自 `module_results.event` + `decision_synthesis.blocking_flags` |
| `decision_synthesis` | `state.decision_synthesis` | 直接透传 |
| `trade_plan` | `state.trade_plan` | 直接透传 |
| `sources` | `deduplicated_sources` | 基于 `state.sources` 去重后输出 |

关键约束：

- `assemble_response` 不能重新计算系统级方向或交易计划
- 对外 response 中的 `decision_synthesis` 和 `trade_plan` 是内部对象的直接公开版本

---

## 4. 四个模块公共子对象映射

### 4.1 `technical_analysis`

来源：

- `module_results.technical`
- `decision_synthesis.actionability_state`

当前映射规则：

| 公共字段 | 当前来源 |
|---|---|
| `technical_signal` | `module_results.technical.direction` 映射为 `Direction` |
| `trend` | 同 `technical_signal` |
| `key_support` | 固定空数组 |
| `key_resistance` | 固定空数组 |
| `volume_pattern` | 固定 `neutral` |
| `momentum` | summary 文本 |
| `entry_trigger` | `None` |
| `target_price` | `None` |
| `stop_loss_price` | `None` |
| `risk_reward_ratio` | `None` |
| `risk_flags` | 由 `status` / `low_confidence` / `reason` 派生 |
| `setup_state` | 直接使用系统级 `actionability_state` |
| `technical_summary` | summary 文本 |

实现含义：

- 当前 public technical payload 仍是占位输出
- 真正的支撑阻力、量价、触发器尚未从内部状态暴露出来

### 4.2 `fundamental_analysis`

来源：

- `module_results.fundamental`
- `decision_synthesis.module_contributions[fundamental].contribution`

当前映射规则：

| 公共字段 | 当前来源 |
|---|---|
| `fundamental_bias` | 方向映射 |
| `composite_score` | contribution，缺失时为 `0.0` |
| `growth` | summary |
| `valuation_view` | summary |
| `business_quality` | summary |
| `key_risks` | 统一 risk flags |
| `data_completeness_pct` | result 或 proxy 值 |
| `fundamental_summary` | summary |

实现含义：

- 设计中的盈利动量、财务健康、估值锚点尚未拆分成独立 public 字段
- 当前 public 层只是把统一 summary 复用到多个文案字段

### 4.3 `sentiment_expectations`

来源：

- `module_results.sentiment`

当前映射规则：

| 公共字段 | 当前来源 |
|---|---|
| `sentiment_bias` | 方向映射 |
| `news_tone` | 由 `Direction` 转换为 `positive/neutral/negative` |
| `market_expectation` | summary |
| `key_risks` | 统一 risk flags |
| `data_completeness_pct` | result 或 proxy |
| `sentiment_summary` | summary |

### 4.4 `event_driven_analysis`

来源：

- `module_results.event`
- `decision_synthesis.blocking_flags`

当前映射规则：

| 公共字段 | 当前来源 |
|---|---|
| `event_bias` | 方向映射 |
| `upcoming_catalysts` | 固定空数组 |
| `risk_events` | 统一 risk flags |
| `event_risk_flags` | 从 `blocking_flags` 中筛出能映射到 `EventRiskFlag` 的值 |
| `data_completeness_pct` | result 或 proxy |
| `event_summary` | summary |

实现含义：

- 当前 public event payload 还没有真正输出结构化催化剂列表
- 只有系统级 blocking flag 被映射成标准枚举

---

## 5. summary 与 risk flag 的公共映射规则

### 5.1 summary 生成

`_build_summary(...)` 当前规则：

1. `result.summary` 和 `result.reason` 同时存在时，拼成：
   - `"{summary} Reason: {reason}."`
2. 仅有 `summary` 时直接用 `summary`
3. 仅有 `reason` 时直接用 `reason`
4. 两者都没有时使用 fallback 文案

### 5.2 risk flag 生成

`_build_risk_flags(...)` 当前规则：

- `status == degraded` 时追加 `module_degraded`
- `low_confidence == True` 时追加 `low_confidence`
- `reason` 非空时追加 `reason`

这套规则同时被用于：

- `technical_analysis.risk_flags`
- `fundamental_analysis.key_risks`
- `sentiment_expectations.key_risks`
- `event_driven_analysis.risk_events`

这是当前实现的简化点。后续如果模块开始产出更细的结构化风险字段，应逐步替换，而不是继续复用统一 risk flag。

---

## 6. `sources` 映射

### 6.1 内部来源

内部 `sources` 来自 provider-backed 模块节点：

- technical -> `SourceType.TECHNICAL`
- fundamental -> `SourceType.FINANCIAL`
- sentiment -> `SourceType.NEWS`
- event company events -> `SourceType.EVENT`
- event macro events -> `SourceType.MACRO`

### 6.2 对外规则

`assemble_response` 内会调用 `_deduplicate_sources(...)`：

- 按 `(type.value, name, str(url))` 去重
- 保留当前 state 中的首次出现顺序

而 graph 层在并行 merge 后已经按 source type 做过排序，所以正常链路下对外顺序通常稳定为：

```text
technical -> financial -> news -> event -> macro
```

测试基线：

- `tests/graph/nodes/test_assemble_response.py:test_assemble_response_deduplicates_sources_in_first_use_order`

### 6.3 公共约束

- 对外只暴露 public `Source`
- 不暴露 provider 内部 `fetched_at` 等元数据
- `url` 必须存在并满足 `AnyUrl`

---

## 7. API 成功路径映射

HTTP 成功路径位于 `app/api/main.py:create_analysis`。

执行顺序：

1. FastAPI 校验请求 body 为 `AnalyzeRequest`
2. 从 app state / dependency 中取 repository 与 providers
3. 调 `build_analysis_graph(...)`
4. `graph.invoke(...)`
5. 将结果校验为 `TradePilotState`
6. 若 `final_state.response` 存在，则直接返回该对象

重要含义：

- API 层不自行拼装 response
- graph 产出的 `response` 是唯一成功返回体

---

## 8. API 错误路径映射

### 8.1 400 `invalid_request`

来源：

- FastAPI / Pydantic body 校验错误

返回体结构：

```json
{
  "error": {
    "code": "invalid_request",
    "message": "...",
    "details": [
      {
        "field": "ticker",
        "reason": "missing"
      }
    ]
  }
}
```

当前规则：

- 缺字段时 message 形如 `ticker is required`
- 非法 JSON 时 message 为 `request body is not valid JSON`
- 其他字段错误为 `request contains invalid fields`

### 8.2 503 `upstream_unavailable`

来源：

- repository 不可用，且最终在 persistence 阶段触发 `RepositoryUnavailableError`

返回：

```json
{
  "error": {
    "code": "upstream_unavailable",
    "message": "analysis persistence is unavailable"
  }
}
```

关键点：

- 当前 503 不是来自 provider，而是来自 persistence backend
- 只要 persistence 是主链路步骤，这个语义就应保持稳定

### 8.3 500 `internal_error`

来源：

- graph 节点抛出未被转义的运行时错误
- 持久化非“仓库不可用”类失败
- graph 结束后 `final_state.response is None`

返回：

```json
{
  "error": {
    "code": "internal_error",
    "message": "analysis pipeline failed unexpectedly"
  }
}
```

或：

```json
{
  "error": {
    "code": "internal_error",
    "message": "analysis pipeline did not produce a response"
  }
}
```

---

## 9. 当前实现与目标实现差距

| 主题 | 当前实现 | 目标方向 |
|---|---|---|
| technical public payload | 多数字段仍是空数组或 `None` | 应由技术模块真实锚点驱动 |
| fundamental public payload | 多个文案字段复用同一 summary | 应拆为更明确的结构化输出 |
| sentiment public payload | 以 summary 为主 | 应接入 expectation shift / narrative crowding 等细项 |
| event public payload | `upcoming_catalysts` 为空，风险多为统一 flag | 应输出真实催化剂与风险事件列表 |
| public diagnostics | 未对外暴露 | 若未来需要暴露，必须单独定义 API 契约，而不是直接透传内部 state |
| API 成功语义 | persistence 失败时无半成功响应 | 若要调整，必须先重新定义产品语义 |

---

## 10. 后续 coding agent 的落地建议

改 response 或 API 映射时，优先遵守：

1. 先确认 public schema 是否真的需要变。
2. 若 schema 不变，优先只改 `build_public_module_payloads(...)`。
3. 若涉及顶层错误码或错误体，统一改 `app/api/main.py`，不要把 HTTP 语义下沉到 graph 节点。
4. 若模块要暴露更多字段，先在内部 state 或 module schema 中建稳定字段，再做 public 映射。

不要做的事：

- 不要让 API 直接读取 provider DTO
- 不要在 API 层重新 dedupe `sources`
- 不要让 `trade_plan` 回头依赖 public payload 反推内部状态
