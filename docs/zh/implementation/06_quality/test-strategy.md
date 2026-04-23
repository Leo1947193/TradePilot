# 测试策略实现契约

## 1. 文档目标

本文档定义 implementation 阶段的测试分层、每层职责、推荐落点与编写顺序。

目标不是复述设计，而是让后续 coding agent 明确：

- 改哪一层代码，要补哪一层测试
- 哪些行为必须先由契约测试锁死
- 哪些测试应覆盖当前实现事实，哪些测试应用于目标态演进

---

## 2. 当前测试现状

当前仓库已经有 6 组测试资产：

1. schema / model 测试  
   位置：`tests/schemas/*`
2. provider 契约与工厂测试  
   位置：`tests/services/providers/*`
3. graph node 测试  
   位置：`tests/graph/nodes/*`
4. graph 拓扑测试  
   位置：`tests/graph/test_builder.py`
5. repository / DB 测试  
   位置：`tests/repositories/*`、`tests/db/*`
6. 文档契约测试  
   位置：`tests/test_contract_documents.py`

当前已经做对的部分：

- graph 主链路顺序有测试锁定
- 主要 public schema 有边界测试
- 各 node 的 fail-fast / degraded 回退已有覆盖
- repository 写入 payload 与事务顺序已有覆盖

当前缺口：

- 四个分析模块的规则单元测试仍偏少，更多是 node 层行为测试
- 缺少 golden case 驱动的回归测试组织方式
- 缺少 API 级错误语义与 graph 级 diagnostics 的系统联动测试
- 缺少 observability / diagnostics 的稳定性测试

---

## 3. 推荐测试分层

后续实现统一按 6 层组织。

### 3.1 L1: 纯规则单元测试

作用：

- 锁定纯函数输入输出
- 覆盖阈值、排序、边界、去重、压制链

适用目录：

- `app/analysis/**`
- 未来拆出的 `app/analysis/*/*.py`

要求：

- 不依赖 graph state
- 不依赖 provider
- 不依赖数据库
- 单个 case 只验证一个规则分支

典型对象：

- technical/fundamental/sentiment/event 聚合器
- synthesis scoring / conflict / actionability
- trade plan condition builder / scenario builder

### 3.2 L2: schema 与契约测试

作用：

- 锁定 Pydantic schema 和 OpenAPI 契约
- 防止字段名、枚举、范围、required 集合漂移

当前目录：

- `tests/schemas/*`
- `tests/test_contract_documents.py`

要求：

- 任何 public schema 变化，先改文档契约，再改实现
- 任何 `DecisionSynthesis` / `TradePlan` 字段增删，必须补 schema 边界测试

### 3.3 L3: provider / adapter 测试

作用：

- 锁定 provider 接口和 DTO 转换语义
- 覆盖超时、空结果、部分可用、配置缺失

当前目录：

- `tests/services/providers/*`

要求：

- provider 失败只能回退为模块 degraded / excluded，不得直接污染 schema
- adapter 层若新增 normalization，必须补 trading-day / timezone / staleness 边界

### 3.4 L4: node 契约测试

作用：

- 锁定单节点输入前置条件、副作用、错误语义、diagnostics 更新

当前目录：

- `tests/graph/nodes/*`

要求：

- 每个 node 至少覆盖：成功、缺关键输入、provider 失败回退、diagnostics 幂等
- diagnostics 的去重行为必须可测，不允许依赖人工阅读日志判断

### 3.5 L5: graph / API 集成测试

作用：

- 锁定 LangGraph 主链路顺序、并行边界、HTTP 状态码映射

当前目录：

- `tests/graph/test_builder.py`
- `tests/api/test_main.py`

要求：

- graph 测试验证拓扑与 end-to-end 最小成功路径
- API 测试验证 `400/404/422/500/503` 的外部可见行为
- 不在 API 测试里重复细测模块算法

### 3.6 L6: persistence / migration 测试

作用：

- 锁定数据库 schema、migration、repository 写入约束

当前目录：

- `tests/repositories/*`
- `tests/db/*`

要求：

- migration 需验证可重复执行性或至少验证当前版本创建结果
- repository 需验证主表、模块表、来源表 payload 的字段映射

---

## 4. 改动到测试层的映射规则

后续 coding agent 改代码时，至少按下表补测试：

| 改动类型 | 最低必须补的测试 |
|---|---|
| 调整分析阈值 / 打分规则 | L1 + L4 |
| 改 public schema / response | L2 + L5 |
| 改 provider DTO / fallback | L3 + L4 |
| 改 graph 节点输入输出 | L4 + L5 |
| 改持久化 payload / schema | L6，必要时加 L5 |
| 改 implementation 文档中的契约段落 | `tests/test_contract_documents.py` |

原则：

- 先锁契约，再改实现
- 不要只补 end-to-end 测试而跳过更近的规则层

---

## 5. `06_quality` 对前五层文档的约束

### 5.1 对 `00_foundation`

- 测试运行方式统一使用 `uv`
- 测试目录不另起体系，继续沿用 `tests/`

### 5.2 对 `01_runtime`

- graph 执行顺序、降级边界、状态码映射必须有直接测试
- node fail-fast 契约必须通过 node 测试锁定

### 5.3 对 `02_data`

- provider contract、time policy、persistence flow 都要对应测试资产

### 5.4 对 `03_analysis` / `04_synthesis` / `05_trade_plan`

- 每份实现文档中提到的“固定顺序”“短期不要改名”“边界阈值”都应落成单元或 node 级测试

---

## 6. 推荐编写顺序

按“最能支撑后续 coding agent 写代码”的原则，测试应按以下顺序补齐：

1. public schema / 文档契约测试
2. graph topology / node 前置条件测试
3. synthesis 与 trade plan 的纯规则单元测试
4. 四分析模块的聚合器与子模块规则测试
5. provider adapter 边界测试
6. persistence / migration 回归测试
7. golden case 驱动的跨层回归测试

原因：

- 前三步先把外部契约和系统骨架锁死
- 这样 coding agent 才能在不破坏主链路的前提下继续填充算法细节

---

## 7. 当前阶段必须补强的测试空白

进入真实编码阶段后，优先补这几类测试：

- synthesis 的方向压制链测试
- trade plan richer anchor 输入解析测试
- event 风险标记到 `blocking_flags` 的映射测试
- `source_trace` / `evidence` 持久化与响应组装测试
- diagnostics 中 `degraded/excluded/errors/warnings` 的稳定性测试

---

## 8. 测试实现要求

- 优先写确定性测试，不依赖当前时间和外部网络
- 测试数据尽量小，避免用超长 market/news fixture
- 一条测试只锁一个行为，不把多个规则揉进同一个断言块
- 断言优先对结构化字段，不依赖完整自然语言摘要
- 对必须稳定的字符串 id，例如 `confidence_score_below_0_55`，允许直接断言完整值

---

## 9. 不建议的做法

- 只补 happy path，不补 degraded / excluded / failed
- 用 API 集成测试替代规则单元测试
- 把 implementation 文档测试写成全文匹配
- 在一个测试里同时锁多个模块、多层责任和多种失败语义

---

## 10. 完成标准

当某一实现层被认为“可支撑 coding agent 落码”时，至少应满足：

- 外部契约已有测试锁定
- 对应 node 的成功与失败语义已有测试锁定
- 核心规则已有纯函数级边界测试
- degraded / excluded / failed 三类非 happy path 至少覆盖到一层直接测试
