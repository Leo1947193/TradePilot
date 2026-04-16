<!-- ==================== 通用部分（各项目勿修改）==================== -->

## 核心原则

- **需求优先**：如果需求不清晰或存在歧义，先提问，再动手。不要猜测意图。
- **简单优先**：始终选择最简单的可行方案。引入复杂性需要明确理由。
- **可读性**：代码必须对人和 AI 都能立即理解。优先清晰，而非炫技。
- **DRY**：不要重复自己。写新代码前，先搜索是否已有现成实现。
- **不引入多余依赖**：除非明确要求或有充分理由，不引入新的库或框架。
- **遵循规范**：遵守当前技术栈对应语言和框架的既定约定。

## 行为边界

**始终执行：**
- 每次改动都要添加或更新测试，即使没有被要求。
- 使用能反映业务概念的命名，而非技术实现细节。
- 保持改动小而专注。每个任务只做一件事。
- 任务完成后，简要说明改了什么、为什么这样改。

**先确认再动手：**
- 重构不在本次任务范围内的代码之前。
- 引入新依赖之前。
- 改动超过 3 个文件之前。
- 修改任何接口、API 契约或数据库 schema 之前。

**绝对不做：**
- 硬编码 secret、API key、凭证或环境特定的值。
- 删除或禁用失败的测试，而不是修复它。
- 修改 vendor/、dist/ 或 build/ 目录下的文件。
- 在未说明的情况下，做超出当前任务范围的改动。

## 代码风格

- 优先显式，而非隐式。
- 注释解释*为什么*，而非*是什么*。避免只是复述代码的注释。
- 保持函数小而单一职责。
- 优先提前返回，而非深层嵌套。

## 改动纪律

- 开始前，简要确认你对任务的理解。
- 做能解决问题的最小改动。
- 如果在工作中发现不相关的问题，标记出来而不是悄悄修掉。
- 不要在没有说明的情况下，重新生成或重组已有的正常运行的代码。

## 安全

- 任何形式的 secret 或凭证都不得提交。
- 对所有用户输入进行校验。永远不要信任外部数据。
- 对安全影响有疑虑时，标记出来并提问。

## Git

- 写清晰、描述性的提交信息。推荐格式：`<类型>: <简短描述>`（例如 `fix: 处理用户查询中的空值情况`）。
- 每个提交代表一个逻辑改动。

<!-- ==================== 项目专用规则（TradePilot）==================== -->

## 项目专用规则

- 将 `docs/zh/api/openapi.yaml` 视为对外 API 的唯一事实来源。
- 若要修改架构或运行时行为，必须同时检查 `docs/zh/design/system-architecture.md`、`docs/zh/implementation/implementation-stack.md`、`docs/zh/implementation/runtime-contract.md` 和 `docs/zh/implementation/data-sources.md`。
- 本项目是 V1 的美股分析后端服务。不要擅自添加前端页面、管理后台或交易执行流程。
- 产品定位是决策支持工具，不是自动交易系统。
- 优先产出确定性、可解释的 JSON 输出，目标持仓周期为 `1 周` 到 `3 个月`。

- V1 固定技术栈：
  - `Python 3.11`
  - `FastAPI` + `Uvicorn`
  - `Pydantic v2`
  - `LangGraph`
  - `PostgreSQL` + `psycopg v3` + `psycopg_pool`
  - `httpx`
  - `pytest` + `pytest-asyncio`
  - 使用 `uv` 管理依赖和虚拟环境
- 除非明确批准，不要引入 `ORM`、`Redis`、`Celery`、`WebSocket`、`SSE`、`Poetry` 或 `pipenv`。

- V1 只暴露一个业务接口：`POST /api/v1/analyses`。
- 请求是同步的，必须在一次响应中返回完整 JSON 结果。
- 未经批准，不要增加 `job_id`、轮询接口、后台任务、流式响应或公开的模块级调试接口。
- 对外 API 只接受文档定义的契约，不要随意增加请求字段。
- 对外 API 枚举值应保持小写。时间值必须使用 `UTC` 和 `ISO 8601`。

- 固定流程为：`validate_request -> prepare_context -> parallel analysis modules -> synthesize_decision -> generate_trade_plan -> assemble_response -> persist_analysis`。
- 四个核心分析模块是 `technical`、`fundamental`、`sentiment` 和 `event`。
- 跨模块权重组合和冲突处理只能发生在决策综合层。
- 交易计划生成必须消费系统级输出，不得重新计算总体方向。

- 严格遵守分层边界：
  - `app/api`：只处理 HTTP 适配、校验和错误映射
  - `app/graph`：只做编排，不写业务评分规则
  - `app/analysis`：负责确定性的分析和评分规则
  - `app/services/providers`：只负责外部数据获取与标准化，绝不直接做交易决策
  - `app/repositories`：只负责持久化，不承载分析逻辑
- 不要在公共响应里暴露 LangGraph state、checkpoint ID、内部运行 ID 或节点内部细节。

- 所有 provider 集成都必须先定义清晰接口，再添加具体实现。
- V1 默认 provider 为：`yfinance` 用于行情 / 财务 / 公司事件基础数据，新闻 REST provider 如 `Finnhub`，以及仓库内维护的静态宏观日历 provider。
- Provider 输出必须先标准化为内部 DTO；分析模块不能直接消费第三方原始 payload。
- 当 provider 缺失或失败时，按文档规定走降级或失败路径，不允许猜测数据。

- 只有四个分析模块允许降级。`validate_request`、`prepare_context`、`assemble_response` 和 `persist_analysis` 失败时必须让请求失败。
- 返回 `200` 的前提是顶层响应有效，且 PostgreSQL 持久化成功。
- 外部数据获取最多允许一次短退避重试；数据库写入失败和内部规则异常不得自动重试。
