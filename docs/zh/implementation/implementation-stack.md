# 实现栈约定

## 1. 目标

本文档固定 V1 的工程实现栈，目的是让 coding agent 在不再猜测技术选型的前提下直接开工。

若后续需要替换任一核心组件，必须同时更新：

- [../api/openapi.yaml](../api/openapi.yaml)
- [../design/system-architecture.md](../design/system-architecture.md)
- 本文档

---

## 2. V1 固定技术栈

### 2.1 语言与运行时

- `Python 3.11`
- 时区统一使用 `UTC`
- 所有时间字段统一使用 `ISO 8601`

### 2.2 Web 与 API 层

- `FastAPI`
- `Uvicorn`
- 请求/响应模型使用 `Pydantic v2`

选型原因：

- 与 [../api/openapi.yaml](../api/openapi.yaml) 的契约天然匹配
- 对同步 JSON API、验证和 OpenAPI 暴露足够直接
- 便于后续接入依赖注入、测试和中间件

### 2.3 Graph 编排层

- `LangGraph`
- 单请求对应一次 graph 执行
- V1 不启用对外可见的多轮会话、线程持久化或人机中断恢复

### 2.4 HTTP 客户端

- `httpx`

用途：

- 调用外部 REST 数据源
- 支持超时、重试封装和异步请求

### 2.5 数据持久化

- `PostgreSQL`
- `psycopg v3`
- `psycopg_pool`

用途：

- 持久化单次分析请求生成的模块结果、决策综合结果、交易计划和顶层报告快照
- 支持历史分析查询、横向对比和事后评估

约束：

- V1 只持久化结果数据，不持久化 LangGraph 线程状态
- V1 不引入 ORM，持久化访问必须通过清晰的 repository / storage 抽象完成
- 具体表结构见 [postgresql-schema.md](./postgresql-schema.md)
- 具体访问与 migration 约定见 [postgresql-access.md](./postgresql-access.md)

### 2.6 测试栈

- `pytest`
- `pytest-asyncio`
- `httpx` 的测试客户端能力

### 2.7 包管理、虚拟环境与开发命令

- `uv`

要求：

- 使用 `uv` 管理依赖与虚拟环境
- 使用 `uv run` 执行项目命令，如启动服务、运行测试和执行脚本
- 使用 `uv sync` 同步开发环境
- 新增或升级依赖时使用 `uv add` / `uv remove`
- 项目依赖清单以 `pyproject.toml` 和 `uv.lock` 为准
- 不手写维护 `requirements.txt` 作为主依赖来源
- 不引入 `poetry`、`pipenv` 或额外任务运行器

推荐命令示例：

- 安装 / 同步依赖：`uv sync`
- 启动服务：`uv run uvicorn app.api.main:app --reload`
- 运行测试：`uv run pytest`
- 执行 migration：`uv run python -m app.db.migrate up`

### 2.8 日志与配置

- 日志：Python 标准库 `logging`
- 配置：环境变量 + Pydantic Settings

V1 不引入额外日志库或配置框架。

---

## 3. V1 不采用的技术

以下能力在 V1 明确不做：

- Redis / Celery / 任务队列
- WebSocket / SSE 流式响应
- ORM
- 前端页面

说明：

- 当前目标是先完成一个稳定的同步分析 API 和结果持久化链路
- 若后续切换到异步任务制，再单独设计任务基础设施

---

## 4. 推荐目录结构

```text
tradepilot/
├── app/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   └── analyses.py
│   │   └── errors.py
│   ├── schemas/
│   │   ├── api.py
│   │   ├── graph_state.py
│   │   └── modules.py
│   ├── graph/
│   │   ├── builder.py
│   │   ├── nodes/
│   │   │   ├── validate_request.py
│   │   │   ├── prepare_context.py
│   │   │   ├── run_technical.py
│   │   │   ├── run_fundamental.py
│   │   │   ├── run_sentiment.py
│   │   │   ├── run_event.py
│   │   │   ├── synthesize_decision.py
│   │   │   ├── generate_trade_plan.py
│   │   │   ├── assemble_response.py
│   │   │   └── persist_analysis.py
│   │   └── policies.py
│   ├── db/
│   │   ├── pool.py
│   │   ├── migrate.py
│   │   └── migrations/
│   ├── services/
│   │   ├── providers/
│   │   │   ├── market_data.py
│   │   │   ├── financial_data.py
│   │   │   ├── news_data.py
│   │   │   ├── macro_calendar.py
│   │   │   └── company_events.py
│   │   ├── adapters/
│   │   └── normalization/
│   ├── analysis/
│   │   ├── technical/
│   │   ├── fundamental/
│   │   ├── sentiment/
│   │   ├── event/
│   │   ├── decision/
│   │   └── trade_plan/
│   ├── repositories/
│   │   └── analysis_reports.py
│   ├── config.py
│   └── sources.py
├── tests/
│   ├── api/
│   ├── graph/
│   ├── analysis/
│   └── fixtures/
├── docs/
└── pyproject.toml
```

约束：

- `app/api` 只做 HTTP 协议适配
- `app/graph` 只做 graph 编排，不写业务规则
- `app/analysis` 承担实际分析与聚合规则
- `app/services/providers` 只负责外部数据获取与标准化，不直接做决策
- `app/repositories` 负责 PostgreSQL 持久化读写，不直接承载分析规则

---

## 5. Pydantic 模型分层

必须至少区分三类模型：

1. API 模型
   对应 [../api/openapi.yaml](../api/openapi.yaml) 和 HTTP 请求/响应。
2. Graph State 模型
   对应 LangGraph 节点之间传递的内部状态。
3. 模块内部模型
   对应技术、基本面、情绪、事件、决策综合和交易计划的中间结构。

禁止做法：

- 直接把 LangGraph state 当作 HTTP 响应返回
- 让模块内部结构和公共 API 结构完全耦合

---

## 6. 代码组织约束

### 6.1 API 层

- 只接受和返回公共 API 契约
- 不在路由函数里写分析规则
- 不在路由函数里直接访问外部 provider

### 6.2 Graph 层

- 节点必须是小而明确的单职责单元
- 每个节点只读写自己负责的 state 字段
- 节点失败必须转化为受控错误或受控降级，不允许泄漏底层异常到最终响应

### 6.3 分析层

- 所有评分逻辑必须是确定性函数
- 规则阈值必须集中定义
- 模块聚合逻辑不得散落在 API 层或 provider 层

### 6.4 Provider 层

- 先取数，再标准化，再交给分析层
- provider 不得自行生成交易偏向
- provider 输出必须包含来源信息和抓取时间

### 6.5 持久化层

- 只负责把结构化结果写入和读取 `PostgreSQL`
- 不得在 SQL 写入逻辑里夹带业务评分或聚合规则
- 持久化模型可以贴近存储结构，但必须与公共 API 模型解耦
- 固定使用 `psycopg v3 + psycopg_pool`
- 固定使用顺序 SQL migration 文件，而不是 ORM migration

---

## 7. 测试最低要求

coding agent 开工时至少要同时写这三类测试：

1. API 契约测试
   验证 `POST /api/v1/analyses` 的成功和错误响应符合 OpenAPI。
2. Graph 流程测试
   验证 graph 节点顺序、并行分支和降级行为。
3. 规则单元测试
   验证模块分析和决策综合的关键阈值、枚举和边界条件。

---

## 8. 实施顺序

建议 coding agent 按以下顺序实现：

1. `FastAPI + Pydantic` 骨架
2. OpenAPI 对应的请求/响应模型
3. LangGraph 主图和空节点
4. Mock provider 与端到端通路
5. PostgreSQL 连接池、migration runner 和 repository 骨架
6. 顶层响应组装与 PostgreSQL 持久化通路
7. 技术 / 事件 / 情绪 / 基本面模块最小可运行实现
8. 决策综合层与交易计划生成
9. 真实 provider 接入与缓存

---

## 9. 开工前默认结论

除非用户明确要求修改，否则 coding agent 应默认：

- 使用 `FastAPI`
- 使用 `LangGraph`
- 使用 `Pydantic v2`
- 使用 `PostgreSQL`
- 使用 `psycopg v3 + psycopg_pool`
- 使用 `uv`
- 使用 `uv sync` 初始化环境，使用 `uv run` 执行项目命令
- 先实现同步单接口版本
- 先以 mock + 可替换 provider 方式落地，再接真实数据源
