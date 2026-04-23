# TradePilot

TradePilot 是一个面向美股分析场景的 contract-first 后端服务。它接收一个股票代码，沿固定的 LangGraph 主链路执行技术面、基本面、情绪面、事件面分析，综合生成结构化结论与交易计划，并把结果持久化到 Docker Compose 管理的 PostgreSQL。

当前仓库重点是：

- 稳定的单入口 API：`POST /api/v1/analyses`
- 确定性分析与决策综合
- 可测试的 graph / schema / repository 分层
- 可扩展的数据 provider 与 LLM adapter 基础设施

项目当前不包含：

- 前端页面
- 自动交易执行
- WebSocket / SSE / 后台异步任务
- 多业务接口扩展

## 1. 核心能力

- 输入：单个股票代码 `ticker`
- 输出：结构化 JSON，包括：
  - `technical_analysis`
  - `fundamental_analysis`
  - `sentiment_expectations`
  - `event_driven_analysis`
  - `decision_synthesis`
  - `trade_plan`
  - `sources`
- 执行顺序固定为：
  - `validate_request`
  - `prepare_context`
  - `run_technical / run_fundamental / run_sentiment / run_event`
  - `synthesize_decision`
  - `generate_trade_plan`
  - `assemble_response`
  - `persist_analysis`

## 2. 技术栈

- Python `>= 3.11`
- FastAPI
- Pydantic v2
- LangGraph
- PostgreSQL + psycopg + psycopg_pool
- httpx
- yfinance
- uv
- pytest

## 3. 目录结构

主要目录如下：

```text
app/
  analysis/            确定性分析规则
  api/                 FastAPI 入口
  db/                  连接池与 migration
  graph/               LangGraph builder 与 nodes
  repositories/        持久化协议与 PostgreSQL 实现
  rules/               稳定规则常量
  schemas/             API / graph / module schema
  services/
    providers/         市场、财务、新闻、宏观 provider
    llm/               LLM adapter（当前已接入 MiniMax）

tests/
  analysis/
  api/
  golden/
  graph/
  repositories/
  schemas/
  services/

docs/zh/
  prd/
  design/
  implementation/
```

## 4. 快速开始

### 4.1 安装依赖

推荐先安装 `uv`，然后在项目根目录执行：

```bash
uv sync
```

### 4.2 创建并填写 `.env`

项目通过根目录 `.env` 读取配置。数据库默认走 Docker Compose 内的 `db` 服务，推荐直接使用分项配置：

```env
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_USER=tradepilot
POSTGRES_PASSWORD=tradepilot
POSTGRES_DB=tradepilot
```

如果你已经有一条现成连接串，也可以继续使用：

```env
POSTGRES_DSN=postgresql://tradepilot:tradepilot@db:5432/tradepilot
```

如果你要启用新闻 provider：

```env
NEWS_PROVIDER=finnhub
NEWS_API_KEY=your_finnhub_key
```

如果你要启用静态宏观日历 provider：

```env
MACRO_CALENDAR_PATH=/absolute/path/to/macro_calendar.json
```

如果你要启用 LLM adapter，并切到 MiniMax：

```env
LLM_PROVIDER=minimax
LLM_MODEL=minimax-m2.7
MINIMAX_API_KEY=your_minimax_key
```

可选项：

```env
MARKET_DATA_PROVIDER=yfinance
REQUEST_TIMEOUT_SECONDS=8.0
MINIMAX_BASE_URL=https://api.minimax.io/v1
```

说明：

- 推荐使用大写环境变量名；`POSTGRES_DSN` 仍兼容，但会优先覆盖 `POSTGRES_HOST/PORT/USER/PASSWORD/DB`
- 若未显式提供 `POSTGRES_DSN`，应用会按上述五个字段自动拼接 PostgreSQL 连接串
- Docker Compose 内部必须使用 `db` 作为数据库主机名，不能写成容器内无效的 `localhost`
- 如果 persistence repository 不可用，API 会返回 `503`

### 4.3 启动 Docker 容器

先启动 PostgreSQL 和 API 容器：

```bash
docker compose up -d --build
```

### 4.4 执行数据库迁移

数据库迁移应在应用容器内执行，这样能直接复用容器内的数据库配置：

```bash
docker compose exec app uv run python -m app.db.migrate up
```

如果成功，会输出：

```text
Applied migrations: 0001
```

### 4.5 本地调试模式

如果你只想本地运行 Python 进程、继续复用容器内 PostgreSQL，可以执行：

```bash
uv run uvicorn app.api.main:app --reload
```

默认本地地址：

```text
http://127.0.0.1:8000
```

此时请确保 `.env` 里的数据库主机仍然指向 Docker 暴露给宿主机的地址，例如：

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=tradepilot
POSTGRES_PASSWORD=tradepilot
POSTGRES_DB=tradepilot
```

注意：

- 当前 FastAPI 关闭了默认 Swagger / ReDoc / OpenAPI 路由
- 这是有意设计，不是启动失败

## 5. 如何调用 API

当前只有一个业务接口：

```text
POST /api/v1/analyses
```

请求示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyses \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL"}'
```

成功时会返回结构化 JSON。响应中至少包含：

```json
{
  "ticker": "AAPL",
  "analysis_time": "2026-04-23T12:00:00Z",
  "technical_analysis": {},
  "fundamental_analysis": {},
  "sentiment_expectations": {},
  "event_driven_analysis": {},
  "decision_synthesis": {},
  "trade_plan": {},
  "sources": []
}
```

常见错误：

- `400 invalid_request`
  - 请求体缺字段或有非法字段
- `503 upstream_unavailable`
  - persistence repository 不可用
- `500 internal_error`
  - graph 链路或内部契约失败

## 6. 当前 provider 与 LLM 状态

### 6.1 数据 provider

当前数据 provider 主要是：

- `yfinance`
  - 市场数据
  - 财务快照
  - 公司事件基础数据
- `finnhub`
  - 公司新闻
- `static macro calendar`
  - 本地静态宏观日历

### 6.2 LLM adapter

当前仓库已落地最小 LLM adapter 基础设施，位于：

- [app/services/llm](/Users/leo/Dev/TradePilot/app/services/llm)

已接入厂商：

- `MiniMax`

当前统一能力接口：

- `generate_text(...)`
- `generate_json(...)`

当前还没有把 LLM 接到 graph node 或 analysis 业务流里；它目前只是基础设施层可用。

## 7. 开发教程

### 7.1 跑全量测试

```bash
uv run pytest
```

### 7.2 按层跑测试

Schema：

```bash
uv run pytest tests/schemas
```

Graph：

```bash
uv run pytest tests/graph
```

API：

```bash
uv run pytest tests/api
```

Repository：

```bash
uv run pytest tests/repositories
```

Provider 与 LLM：

```bash
uv run pytest tests/services/providers
uv run pytest tests/services/llm
```

Golden cases：

```bash
uv run pytest tests/golden
```

### 7.3 常见开发顺序

如果你要扩一个分析模块，建议顺序是：

1. 先看 `docs/zh/implementation/`
2. 再改 `app/schemas/` 或 `app/analysis/`
3. 再改对应 `app/graph/nodes/`
4. 最后补测试：
   - `tests/analysis/*`
   - `tests/graph/nodes/*`
   - 必要时补 `tests/golden/*`

如果你要扩 provider：

1. 先看 `app/services/providers/interfaces.py`
2. 再补 DTO / adapter / factory
3. 最后补 `tests/services/providers/*`

如果你要扩 LLM：

1. 先看 `app/services/llm/interfaces.py`
2. 再补对应 `*_adapter.py`
3. 在 `factory.py` 里注册
4. 补 `tests/services/llm/*`

## 8. 重要实现约束

- 不新增业务接口；当前只支持 `POST /api/v1/analyses`
- 不把决策综合和交易计划逻辑塞进 provider
- `persist_analysis` 属于主链路，不是异步补偿步骤
- 四个分析模块允许 degraded；`assemble_response` 和 `persist_analysis` 不允许静默降级
- graph 节点应保持小而同步，业务规则优先放在 `app/analysis/`

## 9. 进一步阅读

如果你要真正继续开发，建议按这个顺序读文档：

1. [docs/zh/prd/ai-prd.md](/Users/leo/Dev/TradePilot/docs/zh/prd/ai-prd.md:1)
2. [docs/zh/design/overview.md](/Users/leo/Dev/TradePilot/docs/zh/design/overview.md:1)
3. [docs/zh/design/system-architecture.md](/Users/leo/Dev/TradePilot/docs/zh/design/system-architecture.md:1)
4. [docs/zh/implementation/00_foundation/implementation-stack.md](/Users/leo/Dev/TradePilot/docs/zh/implementation/00_foundation/implementation-stack.md:1)
5. [docs/zh/implementation/01_runtime/runtime-contract.md](/Users/leo/Dev/TradePilot/docs/zh/implementation/01_runtime/runtime-contract.md:1)
6. [docs/zh/implementation/07_coding-roadmap.md](/Users/leo/Dev/TradePilot/docs/zh/implementation/07_coding-roadmap.md:1)

## 10. 当前状态说明

这个仓库已经具备：

- 可运行的 API 骨架
- 固定的 LangGraph 主图
- PostgreSQL 持久化
- 四个分析模块的结构化拆分
- golden case 与 diagnostics 回归基线
- MiniMax LLM adapter 基础设施

但它仍然是一个持续演进中的 V1 后端，部分 provider-backed 路径和 richer 输出仍在逐步完善中。
