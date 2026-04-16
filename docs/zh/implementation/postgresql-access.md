# PostgreSQL 访问与迁移约定

## 1. 目标

本文档回答 coding agent 在实现 PostgreSQL 持久化时最容易猜错的几个问题：

- 用什么 Python 驱动访问 PostgreSQL
- 连接池怎么建
- SQL 通过什么方式组织
- schema migration 用什么方案
- repository 的最小接口长什么样

本文件是 [implementation-stack.md](./implementation-stack.md) 和 [postgresql-schema.md](./postgresql-schema.md) 的补充实现约定。

---

## 2. 固定选型

V1 固定采用以下方案：

- PostgreSQL 驱动：`psycopg v3`
- 连接池：`psycopg_pool.ConnectionPool`
- 查询方式：纯 SQL，不使用 ORM
- migration 方式：顺序编号 SQL 文件 + 轻量 migration runner

明确不采用：

- `asyncpg`
- `SQLAlchemy ORM`
- `Alembic`
- 自定义 DSL 迁移格式

原因：

- V1 是同步单接口 API，优先选择同步数据库访问，减少并发模型混用
- `psycopg v3` 足够成熟，事务控制清晰，和原生 SQL 配合直接
- 当前表结构稳定度还不需要 ORM 和 Alembic 带来的额外复杂度
- 对 coding agent 来说，原生 SQL + 明确 migration 目录最不容易写偏

---

## 3. 数据库访问模式

### 3.1 同步访问

V1 默认使用同步数据库访问。

即：

- FastAPI 路由可以是同步函数，或异步函数中调用线程池包装的同步 graph 执行
- graph 内部的 `persist_analysis` 使用同步 repository
- 不在同一个主链路里混用 `asyncpg`、异步连接池或异步事务接口

理由：

- 当前请求模式是同步单次分析
- provider 已经有外部 IO，数据库层不再额外引入第二套并发复杂度
- 同步事务更容易保证一次分析写入的原子性

### 3.2 连接池

V1 使用单个进程级 PostgreSQL 连接池：

- 类型：`psycopg_pool.ConnectionPool`
- 生命周期：应用启动时初始化，应用关闭时释放

最小要求：

- 必须配置 `max_size`
- 必须配置 `timeout`
- 必须开启连接健康检查或在获取失败时抛出受控错误

推荐配置字段：

- `postgres_dsn`
- `postgres_min_pool_size`
- `postgres_max_pool_size`
- `postgres_connect_timeout_seconds`

---

## 4. SQL 组织方式

V1 固定使用“repository 内嵌参数化 SQL”。

要求：

- SQL 必须使用参数绑定
- 不允许字符串拼接用户输入
- repository 只做数据写入 / 读取映射
- 业务规则不得写进 SQL

可以接受：

- 在 repository 文件内定义多行 SQL 常量
- 把复杂查询拆成独立私有函数

不推荐：

- 把零散 SQL 字符串散落到 graph 节点
- 在 API 层直接执行 SQL
- 为了几条插入语句引入 ORM 模型系统

---

## 5. Migration 方案

### 5.1 目录结构

V1 固定采用以下目录：

```text
app/
├── db/
│   ├── pool.py
│   ├── migrate.py
│   └── migrations/
│       ├── 0001_init_analysis_reports.sql
│       ├── 0002_add_indexes.sql
│       └── ...
```

### 5.2 Migration 文件格式

每个 migration 是一个独立 `.sql` 文件，按递增编号命名：

- `0001_init_analysis_reports.sql`
- `0002_add_indexes.sql`
- `0003_add_pipeline_version.sql`

要求：

- 每个 migration 文件只承载一个逻辑变更
- 必须可重复按顺序执行
- 不允许修改已发布 migration 文件；如需变更，新增下一个 migration

### 5.3 Migration 追踪表

数据库内必须有 migration 追踪表：

- 表名：`schema_migrations`

建议字段：

- `version` `text primary key`
- `applied_at` `timestamptz not null default now()`

### 5.4 Migration Runner

V1 使用轻量 Python runner 执行 migration：

- 模块：`app.db.migrate`
- 命令：`uv run python -m app.db.migrate up`

最小职责：

1. 创建 `schema_migrations`
2. 扫描 `app/db/migrations/*.sql`
3. 按编号排序
4. 跳过已执行版本
5. 在事务中执行未执行 migration
6. 写入 `schema_migrations`

明确不做：

- 自动生成 migration
- downgrade / rollback 脚本框架
- 复杂分支迁移图

V1 的原则是：

- migration 由 coding agent 显式编写
- runner 只负责按顺序执行

---

## 6. Repository 最小接口

V1 至少定义一个主 repository：

- `AnalysisReportRepository`

最小接口建议：

```python
class AnalysisReportRepository:
    def save_analysis_report(self, payload: PersistAnalysisPayload) -> SavedAnalysisReport: ...
    def get_analysis_report(self, report_id: UUID) -> PersistedAnalysisReport | None: ...
    def list_reports_by_ticker(self, ticker: str, limit: int = 20) -> list[PersistedAnalysisReport]: ...
    def get_latest_report_by_ticker(self, ticker: str) -> PersistedAnalysisReport | None: ...
```

其中：

- `save_analysis_report(...)`
  - 必须在单事务内写 `analysis_reports`、`analysis_module_reports`、`analysis_sources`
- `get_analysis_report(...)`
  - 返回一条完整历史分析
- `list_reports_by_ticker(...)`
  - 用于历史查询
- `get_latest_report_by_ticker(...)`
  - 只是查询逻辑，不代表覆盖式存储

### 6.1 `PersistAnalysisPayload`

`save_analysis_report(...)` 的输入建议至少包含：

- `request_id`
- `request_payload`
- `normalized_ticker`
- `context`
- `module_results`
- `decision_synthesis`
- `trade_plan`
- `response`
- `sources`
- `diagnostics`
- `analysis_time`

要求：

- payload 是持久化边界对象，不直接等于 API 模型
- repository 负责把该对象映射到 3 张表

### 6.2 返回值

`save_analysis_report(...)` 的返回值建议至少包含：

- `report_id`
- `request_id`
- `persisted_at`

这些字段将被 `persist_analysis` 节点写回 graph state。

---

## 7. 事务约定

`save_analysis_report(...)` 必须满足：

- 单事务提交
- 主表、模块表、来源表一起成功或一起失败
- 失败时抛出受控持久化异常

插入顺序固定为：

1. `analysis_reports`
2. `analysis_module_reports`
3. `analysis_sources`

不允许：

- 先写主表再在事务外补模块表
- 用多次独立提交拼接一条分析记录
- 持久化失败后仍返回 `200`

---

## 8. coding agent 默认结论

除非用户明确要求修改，否则 coding agent 应默认：

- 使用 `psycopg v3`
- 使用 `psycopg_pool.ConnectionPool`
- 使用纯 SQL repository
- 使用 `app/db/migrations/*.sql` 顺序 migration 文件
- 使用 `uv run python -m app.db.migrate up` 作为 migration 执行命令
