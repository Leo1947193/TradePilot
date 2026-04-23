# Foundation: Implementation Stack

## 1. 文档目标

本文档定义实现阶段的基础约束，回答三个问题：

- 代码必须运行在什么栈上
- coding agent 应该通过什么命令开发、测试、启动
- 不同层之间允许依赖什么，不允许依赖什么

本文档不复述产品设计，只约束真实编码时的技术边界。

---

## 2. 当前仓库固定技术栈

以当前 [`pyproject.toml`](/Users/leo/Dev/TradePilot/pyproject.toml:1) 和 `app/` 实现为准，V1 固定使用以下栈：

| 层 | 当前实现 | 用途 |
| --- | --- | --- |
| 运行时 | `Python >=3.11` | 统一解释器版本 |
| API | `FastAPI` | HTTP 入口、状态码、响应序列化 |
| Schema | `Pydantic v2` + `pydantic-settings` | 请求/响应模型、graph state、provider DTO、环境变量 |
| 编排 | `LangGraph` | 固定执行图与并行分支 |
| 外部数据接入 | `httpx`、`yfinance` | 新闻与市场/财务/公司事件 provider |
| 存储 | `PostgreSQL` + `psycopg` + `psycopg_pool` | 持久化分析结果 |
| 测试 | `pytest`、`pytest-asyncio` | API、graph、schema、provider、repository 测试 |
| 工程命令 | `uv` | 依赖、虚拟环境、命令入口 |

实现要求：

- 不新增第二套环境管理方式；统一使用 `uv`
- 不引入 Celery、Redis、消息队列、ORM、任务调度器这类基础设施，除非需求明确变更
- 不把规则实现迁移到 notebook、SQL procedure 或前端
- 不在 provider 层直接做系统级决策

---

## 3. 当前实现与目标实现的关系

当前代码已经具备可运行骨架，但仍是 V1 基础版：

- 已有：
  - [`app/api/main.py`](/Users/leo/Dev/TradePilot/app/api/main.py:1) 的单入口 API
  - [`app/graph/builder.py`](/Users/leo/Dev/TradePilot/app/graph/builder.py:1) 的固定 LangGraph 流程
  - [`app/schemas/`](/Users/leo/Dev/TradePilot/app/schemas/api.py:1) 的请求、响应、graph state、模块 schema
  - [`app/services/providers/`](/Users/leo/Dev/TradePilot/app/services/providers/interfaces.py:1) 的 provider protocol 与 DTO
  - [`app/repositories/postgresql_analysis_reports.py`](/Users/leo/Dev/TradePilot/app/repositories/postgresql_analysis_reports.py:1) 的 PostgreSQL 持久化实现
- 仍属占位或简化实现：
  - `app/analysis/*.py` 中大部分规则仍是占位级逻辑
  - `app/graph/nodes/run_*.py` 中不少节点以 degrade/fallback 为主
  - 规则阈值和版本号仍分散在模块文件内部
  - 尚未有统一的 LLM provider adapter；若后续接入摘要/抽取类模型能力，不能在业务层直接绑死单一厂商 SDK

因此，coding agent 在后续实现中应遵循：

- 保留现有技术栈和分层
- 优先在现有目录下补全能力
- 只有当单文件已经明显承载多个子职责时，才拆成子包
- 先补齐 schema、node contract、provider contract，再扩展复杂规则
- 若引入 LLM，必须增加 provider-agnostic adapter 层，并保持“改 `.env` 即可切 provider/model，不改业务代码”

---

## 4. 统一命令约定

### 4.1 安装与同步

统一使用 `uv`：

```bash
uv sync
```

禁止在仓库文档、脚本和 CI 指令中混用：

- `pip install`
- `poetry install`
- `conda install`

### 4.2 测试

默认测试命令：

```bash
uv run pytest
```

按层运行时使用：

```bash
uv run pytest tests/schemas
uv run pytest tests/graph
uv run pytest tests/api
uv run pytest tests/services/providers
uv run pytest tests/repositories
uv run pytest tests/db
```

### 4.3 本地启动 API

```bash
uv run uvicorn app.api.main:app --reload
```

### 4.4 运行数据库迁移

当前仓库已有迁移脚本入口 [`app/db/migrate.py`](/Users/leo/Dev/TradePilot/app/db/migrate.py:1)。推荐命令约定：

```bash
uv run python -m app.db.migrate
```

如果后续为迁移增加 CLI 参数，也应继续通过 `uv run python -m ...` 暴露，而不是引入独立 shell 脚本体系。

---

## 5. 环境变量与配置准入

当前配置入口固定在 [`app/config.py`](/Users/leo/Dev/TradePilot/app/config.py:1)。

现有环境变量：

- `POSTGRES_DSN`
- `POSTGRES_MIN_POOL_SIZE`
- `POSTGRES_MAX_POOL_SIZE`
- `POSTGRES_CONNECT_TIMEOUT_SECONDS`
- `NEWS_API_KEY`
- `MARKET_DATA_PROVIDER`
- `NEWS_PROVIDER`
- `MACRO_CALENDAR_PATH`
- `REQUEST_TIMEOUT_SECONDS`

若引入 LLM 能力，统一新增：

- `LLM_PROVIDER`
- `LLM_MODEL`
- 按厂商拆分的凭证变量，例如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`

实现约束：

- 新增运行时配置，先放入 `Settings`，不要散落读取 `os.environ`
- 配置名统一使用大写 snake case 环境变量，对应 `Settings` 使用小写字段
- provider 选择类开关必须通过 `Settings` 控制，不能硬编码在路由或 graph builder
- `LLM_PROVIDER` 负责选择厂商，`LLM_MODEL` 负责选择该厂商下的具体模型；切换模型时应只改 `.env`
- 未被当前 `LLM_PROVIDER` 选中的厂商凭证，不应阻塞应用启动或 adapter 构建
- 不允许在 graph node、analysis 模块或 prompt 模板中直接判断 `"openai"` / `"anthropic"` / `"gemini"` 之类厂商名
- 任何新增配置都必须同步补：
  - `app/config.py`
  - 对应测试
  - implementation 文档中受影响章节

---

## 6. 分层依赖政策

### 6.1 允许的依赖方向

推荐依赖方向如下：

```text
api
  -> graph
  -> schemas
  -> config

graph/nodes
  -> analysis
  -> schemas
  -> providers/interfaces
  -> repositories/interfaces

analysis
  -> schemas
  -> provider dtos

providers
  -> dtos
  -> third-party sdk/http client

repositories
  -> repository payload types
  -> schemas
  -> db
```

### 6.2 禁止的依赖

禁止以下耦合：

- `app/analysis/*` 导入 `fastapi`
- `app/analysis/*` 直接导入 `psycopg`、`ConnectionPool`
- `app/services/providers/*` 导入 graph node 或 decision/trade plan 逻辑
- `app/analysis/*`、`app/graph/*`、`app/api/*` 直接导入具体 LLM 厂商 SDK
- `app/api/*` 直接拼接 SQL
- `app/schemas/*` 导入 provider 实现、repository 实现或 FastAPI app 对象

若后续接入 LLM，边界要求如下：

- 统一在 `app/services/llm/` 封装厂商适配与 model 选择
- 业务层只依赖 `app/services/llm/interfaces.py` 中的抽象能力，不依赖厂商请求/响应结构
- LLM 仅用于摘要、解释、抽取等非系统级决策环节；综合评分、冲突处理、交易计划分支仍保持确定性规则实现

判断标准：

- 如果一段代码需要知道 HTTP 状态码，它不应放在 `analysis/`
- 如果一段代码需要知道 SQL 或连接池，它不应放在 `graph/nodes/`
- 如果一段代码需要知道第三方 API 细节，它不应放在 `schemas/`

---

## 7. 同步/异步边界

当前实现是“异步 API + 同步 graph invoke + 异步 provider protocol”的混合结构：

- FastAPI 路由是 `async`
- [`build_analysis_graph(...).invoke(...)`](/Users/leo/Dev/TradePilot/app/api/main.py:163) 走同步调用
- provider protocol 是 `async`
- 部分 node 通过 `asyncio.run()` 或线程池桥接异步 provider

这意味着当前阶段的约束是：

- graph node 仍以同步函数为主，避免在每个 node 上引入新的并发模型
- provider 接口保持 `async`，因为新闻/http 数据源天然适合 async client
- 如果 node 需要消费 async provider，优先复用现有桥接模式，不要在同一个调用链中混入多种事件循环管理方式

目标状态：

- 在引入更清晰的 runtime contract 前，不要擅自把单个 node 改为完全不同的执行模型
- 如果未来统一迁移到 async graph，应作为 runtime 层级变更单独设计，不在业务模块中局部演化

---

## 8. 第三方依赖准入规则

新增依赖前必须满足：

1. 现有标准库或现有依赖无法合理完成任务
2. 该依赖直接服务于当前 V1 范围内需求
3. 能补齐最小测试
4. 能明确落在哪一层

默认不引入：

- ORM
- 分布式任务队列
- 缓存中间件
- 大型数值计算框架
- 自动重试框架
- 日志聚合 SDK

如果需要新依赖，必须在实现文档或 PR 说明中写清：

- 为什么现有栈不够
- 增加在哪一层
- 对测试和部署的影响

---

## 9. 文件与模块命名约定

命名统一使用 snake_case：

- Python 文件：`run_technical.py`
- 文档：`implementation-stack.md`
- SQL 迁移：`0001_init_analysis_reports.sql`

目录职责：

- `app/api/` 只放 API 入口和依赖注入
- `app/graph/` 只放图定义与节点
- `app/analysis/` 只放规则计算和组装逻辑
- `app/services/providers/` 只放外部数据适配
- `app/repositories/` 只放持久化协议与实现
- `app/schemas/` 只放结构模型
- `app/db/` 只放连接池和 migration

---

## 10. 测试分层约定

当前仓库已经体现 contract-first 的测试分层，后续必须延续：

1. API 契约测试  
   对应 `tests/api/`

2. Graph 流程测试  
   对应 `tests/graph/`

3. Schema/状态模型测试  
   对应 `tests/schemas/`

4. Provider 契约测试  
   对应 `tests/services/providers/`

5. Repository/数据库测试  
   对应 `tests/repositories/`、`tests/db/`

实现要求：

- 新增公开 schema，先补 schema test
- 新增 graph node 逻辑，补 node test
- 新增 provider，实现与 DTO/协议测试一起提交
- 持久化字段变更必须补 repository 和 migration 测试

---

## 11. Coding Agent 执行清单

开始写代码前，先检查：

1. 变更属于哪一层
2. 是否已有现成 schema / helper / protocol 可复用
3. 是否需要新增配置或依赖
4. 是否会影响命令入口、测试入口或 migration

提交代码前，至少完成：

1. `uv run pytest` 或最小相关测试集
2. 删除自己引入的未使用导入
3. 确认没有越层依赖
4. 若新增规则常量或版本号，同步更新 `rule-versioning.md`

---

## 12. 当前建议的最小工程纪律

- 所有实现优先保持确定性和可测试性
- 尽量把“不稳定外部调用”限制在 provider 层
- 尽量把“组合决策”限制在 decision/trade plan 层
- 不要在 graph state 中塞入未经 schema 约束的大量自由结构
- 不要让字符串字面量阈值继续无序扩散到多个文件

Foundation 层的目标不是让目录更漂亮，而是让后续 coding agent 写代码时知道：

- 该把代码写在哪里
- 该依赖什么
- 该用什么命令验证
- 哪些实现方式在本仓库中属于越界
