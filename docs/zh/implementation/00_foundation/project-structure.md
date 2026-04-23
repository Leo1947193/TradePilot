# Foundation: Project Structure

## 1. 文档目标

本文档定义“代码该放哪一层、每层负责什么、测试如何镜像实现结构”。

重点不是描述理想架构图，而是为 coding agent 提供可执行的放置规则，避免：

- 在错误目录里写代码
- 把临时逻辑塞进 API 层
- 在多个层重复定义同一份结构

---

## 2. 当前仓库结构总览

当前仓库核心实现目录如下：

```text
app/
  api/
  analysis/
  db/
  graph/
    nodes/
  repositories/
  schemas/
  services/
    providers/

tests/
  api/
  db/
  graph/
    nodes/
  repositories/
  schemas/
  services/
    providers/

docs/zh/
  design/
  prd/
  implementation/
    00_foundation/
    01_runtime/
    02_data/
```

这套结构已经和设计中的主分层基本对齐，因此 foundation 层的原则是：

- 保留现有主目录
- 在主目录内部逐步细化
- 不做跨层重排式重构

若后续引入多厂商 LLM adapter，再新增：

- `app/services/llm/`
- `tests/services/llm/`

---

## 3. 目录职责定义

### 3.1 `app/api/`

当前文件：

- [`app/api/main.py`](/Users/leo/Dev/TradePilot/app/api/main.py:1)

职责：

- 声明 FastAPI app
- 管理 lifespan
- 从 `app.state` 读取 provider / repository
- 调用 graph builder
- 统一映射错误为 HTTP 响应

禁止放入：

- 技术分析、基本面分析、情绪分析、事件分析规则
- SQL
- provider 具体解析逻辑

判断方法：

- 如果逻辑需要知道 `/api/v1/analyses`、状态码、`JSONResponse`，它应放在这一层
- 否则应下沉

### 3.2 `app/graph/`

当前文件：

- [`app/graph/builder.py`](/Users/leo/Dev/TradePilot/app/graph/builder.py:1)
- [`app/graph/nodes/`](/Users/leo/Dev/TradePilot/app/graph/nodes/validate_request.py:1)

职责：

- 定义固定节点拓扑
- 管理节点之间的状态流转
- 作为 analysis、provider、repository 之间的编排层

`builder.py` 只负责：

- 声明图
- 注册节点
- 定义边
- 定义 state merge 规则

`graph/nodes/*.py` 只负责单节点职责：

- 读取 `TradePilotState`
- 调用对应 analysis / provider / repository
- 返回更新后的 state

禁止放入：

- 跨多个 node 共享的复杂规则实现
- provider DTO 定义
- HTTP 细节

### 3.3 `app/analysis/`

当前文件：

- [`app/analysis/technical.py`](/Users/leo/Dev/TradePilot/app/analysis/technical.py:1)
- [`app/analysis/fundamental.py`](/Users/leo/Dev/TradePilot/app/analysis/fundamental.py:1)
- [`app/analysis/sentiment.py`](/Users/leo/Dev/TradePilot/app/analysis/sentiment.py:1)
- [`app/analysis/event.py`](/Users/leo/Dev/TradePilot/app/analysis/event.py:1)
- [`app/analysis/decision.py`](/Users/leo/Dev/TradePilot/app/analysis/decision.py:1)
- [`app/analysis/trade_plan.py`](/Users/leo/Dev/TradePilot/app/analysis/trade_plan.py:1)
- [`app/analysis/response.py`](/Users/leo/Dev/TradePilot/app/analysis/response.py:1)

职责：

- 承载确定性业务规则
- 从标准化输入计算结构化输出
- 不直接处理 HTTP、SQL、连接池

当前状态：

- 这一层以“单文件单模块”方式存在
- 适合继续补全 V1

目标状态：

- 当某模块出现多个稳定子职责时，再拆成子包

例如，后续允许演进为：

```text
app/analysis/technical/
  __init__.py
  multi_timeframe.py
  momentum.py
  volume_price.py
  patterns.py
  risk_metrics.py
  aggregate.py
```

但在 foundation 阶段不要求立即重构。优先补足规则与测试。

### 3.4 `app/schemas/`

当前文件：

- [`app/schemas/api.py`](/Users/leo/Dev/TradePilot/app/schemas/api.py:1)
- [`app/schemas/graph_state.py`](/Users/leo/Dev/TradePilot/app/schemas/graph_state.py:1)
- [`app/schemas/modules.py`](/Users/leo/Dev/TradePilot/app/schemas/modules.py:1)

职责：

- 对外 API schema
- graph state schema
- 模块级共享 schema / enum

放置规则：

- 任何需要跨层共享的数据形状，优先进入 `schemas/`
- schema 应是稳定的结构约束，不应夹带业务动作

禁止放入：

- 外部 API 调用
- SQL
- 文案生成流程

### 3.5 `app/services/providers/`

当前文件：

- [`interfaces.py`](/Users/leo/Dev/TradePilot/app/services/providers/interfaces.py:1)
- [`dtos.py`](/Users/leo/Dev/TradePilot/app/services/providers/dtos.py:1)
- [`factory.py`](/Users/leo/Dev/TradePilot/app/services/providers/factory.py:1)
- [`yfinance_provider.py`](/Users/leo/Dev/TradePilot/app/services/providers/yfinance_provider.py:1)
- [`finnhub_news_provider.py`](/Users/leo/Dev/TradePilot/app/services/providers/finnhub_news_provider.py:1)
- [`static_macro_calendar.py`](/Users/leo/Dev/TradePilot/app/services/providers/static_macro_calendar.py:1)

职责：

- 定义 provider protocol
- 把第三方响应转换为内部 DTO
- 处理 provider 级超时、认证、数据字段映射

禁止放入：

- 综合评分
- 交易计划生成
- repository 写入

目录内建议继续维持三层：

1. `interfaces.py`
2. `dtos.py`
3. `*_provider.py` / `factory.py`

新增 provider 时遵循同样结构，不要把 DTO 写回 analysis 层。

### 3.5A `app/services/llm/`（引入多模型能力时）

该目录当前尚未落地；后续若要支持通过 `.env` 切换不同厂商和模型，应新增为 `providers/` 的同级目录，而不是混入 `app/services/providers/`。

建议结构：

```text
app/services/llm/
  interfaces.py
  dtos.py
  factory.py
  openai_adapter.py
  anthropic_adapter.py
  gemini_adapter.py
```

职责：

- 定义面向业务层的 LLM 抽象能力接口
- 把不同厂商 SDK / HTTP 请求映射到统一输入输出 DTO
- 读取 `Settings` 中的 `llm_provider` / `llm_model` 并构建对应 adapter
- 统一处理认证、超时、厂商响应差异和最小 usage / metadata 归一化

禁止放入：

- 技术/基本面/情绪/事件评分逻辑
- 决策综合与交易计划分支
- graph state 组装

目录内建议维持与 data provider 类似的结构：

1. `interfaces.py`
2. `dtos.py`
3. `*_adapter.py` / `factory.py`

实现要求：

- 上层代码只依赖接口和 DTO，不直接依赖具体厂商 SDK
- `.env` 中切换 `LLM_PROVIDER` 与 `LLM_MODEL` 后，不应要求修改 graph node、analysis 模块或 prompt 调用点
- 若某能力只对单一厂商成立，也应先在 adapter 层吸收差异，再决定是否扩展公共接口

### 3.6 `app/repositories/`

当前文件：

- [`analysis_reports.py`](/Users/leo/Dev/TradePilot/app/repositories/analysis_reports.py:1)
- [`postgresql_analysis_reports.py`](/Users/leo/Dev/TradePilot/app/repositories/postgresql_analysis_reports.py:1)

职责：

- 定义持久化协议
- 把结构化 payload 映射到数据库记录
- 查询已持久化报告

禁止放入：

- 业务规则判断
- provider 调用
- HTTP 错误处理

### 3.7 `app/db/`

当前文件：

- [`pool.py`](/Users/leo/Dev/TradePilot/app/db/pool.py:1)
- [`migrate.py`](/Users/leo/Dev/TradePilot/app/db/migrate.py:1)
- [`migrations/*.sql`](/Users/leo/Dev/TradePilot/app/db/migrations/0001_init_analysis_reports.sql:1)

职责：

- 管理连接池
- 管理 migration 发现与执行
- 保存 SQL 迁移文件

规则：

- DDL 进入 `migrations/`
- 连接池逻辑留在 `pool.py`
- 不把 SQL 字符串塞进 graph node 或 API 层

---

## 4. 当前实现到目标实现的演进建议

### 4.1 当前应保留的骨架

以下结构已经是后续实现的稳定基础，不建议重命名：

- `app/api/main.py`
- `app/graph/builder.py`
- `app/graph/nodes/*.py`
- `app/schemas/*.py`
- `app/services/providers/*.py`
- `app/repositories/*.py`
- `app/db/*.py`

### 4.2 可以逐步细化的部分

优先允许细化的目录只有两类：

1. `app/analysis/`
2. `tests/graph/nodes/`、`tests/services/providers/` 等镜像测试目录

也就是说，后续若拆分复杂模块，优先：

- 先拆 `analysis`
- 再同步拆其测试

而不是先改 graph 拓扑或 API 入口。

### 4.3 不建议当前做的结构性动作

- 不要把所有 analysis 逻辑重新塞进 graph node
- 不要按“服务对象”而不是“分层职责”重组主目录
- 不要新增 `utils/` 作为兜底垃圾桶目录
- 不要把字符串常量随意放在顶层 `constants.py`

---

## 5. 推荐的文件放置规则

下面的规则用于判断“新代码该建在哪个文件”。

### 5.1 新增分析规则

放置位置：

- 优先放到对应 `app/analysis/<module>.py`
- 若文件已明显过长且子职责清晰，再拆 `app/analysis/<module>/`

示例：

- 新增技术模块中的 RSI/均线结构判定，放到 `app/analysis/technical.py` 或未来的 `app/analysis/technical/momentum.py`
- 不放到 `run_technical.py`

### 5.2 新增节点级编排

放置位置：

- `app/graph/nodes/<node_name>.py`
- 如需注册到流程，再更新 `app/graph/builder.py`

示例：

- 若新增 `hydrate_sources` 节点，应有独立 node 文件，并在 builder 中连边

### 5.3 新增 provider

放置位置：

- DTO 放 `app/services/providers/dtos.py`
- protocol 放 `interfaces.py`
- 实现放 `*_provider.py`
- 选择逻辑放 `factory.py`

### 5.4 新增持久化能力

放置位置：

- repository protocol 变更放 `analysis_reports.py`
- PostgreSQL 实现放 `postgresql_analysis_reports.py`
- 表结构变更放 `app/db/migrations/*.sql`

### 5.5 新增共享 schema

放置位置：

- 对外返回结构放 `app/schemas/api.py`
- graph state 字段放 `app/schemas/graph_state.py`
- 模块共用结果结构放 `app/schemas/modules.py`

---

## 6. 测试目录必须镜像实现目录

当前测试已经基本镜像实现层次：

| 实现目录 | 对应测试目录 |
| --- | --- |
| `app/api/` | `tests/api/` |
| `app/graph/` | `tests/graph/` |
| `app/schemas/` | `tests/schemas/` |
| `app/services/providers/` | `tests/services/providers/` |
| `app/repositories/` | `tests/repositories/` |
| `app/db/` | `tests/db/` |

要求：

- 新增模块时，测试目录按同层镜像新增
- 不把所有测试堆到 `tests/test_*.py`
- node 测试优先放 `tests/graph/nodes/`

推荐粒度：

- 一个 node 至少一个同名测试文件
- 一个 provider 至少一个同名测试文件
- 一个 schema 文件至少一个对应 schema 测试文件

---

## 7. 文档目录与代码目录的对应关系

后续 `docs/zh/implementation/` 应与实现层次对应，而不是只按设计文档标题平铺。

建议对应关系：

| 文档层 | 主要服务的代码目录 |
| --- | --- |
| `00_foundation/` | 全仓库通用约束 |
| `01_runtime/` | `app/api/`、`app/graph/`、`app/schemas/graph_state.py` |
| `02_data/` | `app/services/providers/`、`app/repositories/`、`app/db/` |
| `03_analysis/` | `app/analysis/`、`app/graph/nodes/run_*.py` |
| `04_synthesis/` | `app/analysis/decision.py`、`app/graph/nodes/synthesize_decision.py` |
| `05_trade_plan/` | `app/analysis/trade_plan.py`、`app/graph/nodes/generate_trade_plan.py` |
| `06_quality/` | `tests/` 全目录 |

这样组织的目的，是让 coding agent 能从文档直接定位代码落点。

---

## 8. 当前建议的目标结构边界

### 8.1 当前结构

当前是可工作的 V1 扁平结构，优点是：

- 节点职责清楚
- 搜索路径短
- 测试可直接镜像

缺点是：

- `app/analysis/*.py` 后续会越来越重
- 阈值和版本号容易分散

### 8.2 目标结构

目标不是大规模迁移，而是以下渐进式收敛：

```text
app/
  analysis/
    technical/      # 当 technical 细分实现足够多时再拆
    fundamental/
    sentiment/
    event/
    decision.py
    trade_plan.py
    response.py
  rules/            # 新增：集中管理规则常量与版本
  graph/
    builder.py
    nodes/
```

其中 `app/rules/` 是 foundation 层明确建议新增的目录，用来承载规则常量和版本元数据；详见 [`rule-versioning.md`](./rule-versioning.md)。

---

## 9. Coding Agent 的结构决策准则

遇到新增代码时，按以下顺序判断：

1. 这是 HTTP / app lifecycle 吗  
   是：放 `app/api/`

2. 这是节点编排或状态流转吗  
   是：放 `app/graph/`

3. 这是纯业务规则吗  
   是：放 `app/analysis/`

4. 这是外部数据拉取与字段映射吗  
   是：放 `app/services/providers/`

5. 这是结构模型吗  
   是：放 `app/schemas/`

6. 这是持久化协议或 SQL 映射吗  
   是：放 `app/repositories/` 或 `app/db/`

如果一段代码同时想做两层的事，通常说明放错地方了。

---

## 10. 结构层面的最小纪律

- 先复用现有层，再考虑新增目录
- 新目录必须有清晰职责，不接受“以后可能会用”的空抽象
- 任何结构重排都要同步考虑测试镜像
- 目录命名优先表达层职责，不表达临时实现细节
- 文档组织应服务代码落地，而不是反过来强迫代码迁移
