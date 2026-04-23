# Foundation: Rule Versioning

## 1. 文档目标

本文档定义两类东西如何在代码中管理：

- 规则常量：阈值、权重、窗口、默认市场、诊断文案、事件分类词等
- 版本元数据：pipeline version、storage schema version、module/report schema version

目标是避免后续实现出现以下问题：

- 同一阈值在多个文件出现多个版本
- 数据库存储版本、graph 版本、规则版本互相脱节
- coding agent 改了规则但不知道该更新哪里

---

## 2. 当前代码中的规则常量分布

基于当前 `app/` 代码，规则常量已经散落在多个文件中：

### 2.1 运行时默认值

- [`app/graph/nodes/prepare_context.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/prepare_context.py:8)
  - `DEFAULT_MARKET = "US"`
  - `DEFAULT_BENCHMARK = "SPY"`
  - `DEFAULT_ANALYSIS_WINDOW_DAYS = (7, 90)`

### 2.2 决策综合权重与代理值

- [`app/graph/nodes/synthesize_decision.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/synthesize_decision.py:20)
  - `CONFIGURED_WEIGHTS`
  - `MODULE_ORDER`
  - `DEGRADED_COMPLETENESS_PROXY`
  - `EXCLUDED_COMPLETENESS_PROXY`

### 2.3 决策阈值

- [`app/analysis/decision.py`](/Users/leo/Dev/TradePilot/app/analysis/decision.py:53)
  - `bias_score >= 0.15`
  - `bias_score <= -0.15`
  - 置信度公式中的 `0.55` / `0.45`
  - 冲突惩罚 `0.2` / `0.1`
  - actionability 阈值 `0.45`

### 2.4 交易计划阈值

- [`app/analysis/trade_plan.py`](/Users/leo/Dev/TradePilot/app/analysis/trade_plan.py:8)
  - `LOW_CONFIDENCE_THRESHOLD = 0.55`
  - `LOW_COMPLETENESS_THRESHOLD = 60.0`

### 2.5 模块级规则词表

- [`app/analysis/sentiment.py`](/Users/leo/Dev/TradePilot/app/analysis/sentiment.py:8)
  - `BULLISH_TERMS`
  - `BEARISH_TERMS`

- [`app/analysis/event.py`](/Users/leo/Dev/TradePilot/app/analysis/event.py:9)
  - `POSITIVE_EVENT_TYPES`
  - `RISK_EVENT_TYPES`
  - 近端事件窗口 `14` 天 / `7` 天

### 2.6 降级诊断文案

- [`app/graph/nodes/run_technical.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_technical.py:18)
- [`app/graph/nodes/run_fundamental.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_fundamental.py:18)
- [`app/graph/nodes/run_sentiment.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_sentiment.py:18)
- [`app/graph/nodes/run_event.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_event.py:18)

这些文件中存在 `*_DEGRADED_SUMMARY`、`*_DEGRADED_REASON`、`*_DEGRADED_WARNING`。

### 2.7 存储与 pipeline 版本

- [`app/repositories/postgresql_analysis_reports.py`](/Users/leo/Dev/TradePilot/app/repositories/postgresql_analysis_reports.py:19)
  - `STORAGE_SCHEMA_VERSION = "v1"`
  - `PIPELINE_VERSION = "langgraph-v1"`
  - `MODULE_REPORT_SCHEMA_VERSION = "v1"`

---

## 3. 当前问题

从实现角度看，当前分布存在四个问题：

1. 数值阈值与业务规则混在函数文件里  
   修改规则时，容易漏掉相邻模块中的同类阈值。

2. 版本号只存在 repository 层  
   这意味着 graph/runtime 规则升级时，没有统一注册点。

3. 诊断文案与状态规则分散  
   同一个模块在测试、诊断、持久化之间会共享字符串，但目前没有集中管理。

4. 词表类规则没有命名空间  
   情绪关键词、事件类型关键词未来会扩展，但现在直接挂在分析函数文件里。

---

## 4. 规则管理总原则

后续实现遵循以下规则：

### 4.1 哪些内容必须抽离为规则常量

以下内容必须抽离，不得继续散落为裸字面量：

- 权重
- 阈值
- 默认窗口
- 默认市场与 benchmark
- completeness 代理值
- 事件窗口天数
- 规则词表
- 会进入 diagnostics / persistence / API 的稳定 reason code 或 warning 文案
- 存储版本号与 pipeline version

### 4.2 哪些内容可以保留在局部函数

以下内容可以暂时保留局部：

- 单函数内部、不会复用的短暂中间变量
- 不进入状态、不进入持久化、也不参与条件判断的展示文案片段

判断标准：

- 如果值会影响分支、评分、状态、持久化字段或测试断言，它就不是“局部实现细节”

---

## 5. 推荐目录：新增 `app/rules/`

Foundation 层建议新增：

```text
app/rules/
  __init__.py
  versions.py
  runtime.py
  decision.py
  trade_plan.py
  technical.py
  fundamental.py
  sentiment.py
  event.py
  messages.py
```

职责建议如下：

### 5.1 `versions.py`

集中管理版本元数据：

- `PIPELINE_VERSION`
- `STORAGE_SCHEMA_VERSION`
- `MODULE_REPORT_SCHEMA_VERSION`
- 如果未来需要：
  - `DECISION_RULESET_VERSION`
  - `TRADE_PLAN_RULESET_VERSION`
  - `TECHNICAL_RULESET_VERSION`
  - `SENTIMENT_LEXICON_VERSION`

### 5.2 `runtime.py`

集中管理与 graph/runtime 上下文有关的固定值：

- 默认市场
- 默认 benchmark
- 默认分析窗口
- provider 默认 limit / days_ahead

### 5.3 `decision.py`

集中管理决策综合相关常量：

- 模块基础权重
- completeness 代理值
- bias score 阈值
- confidence penalty / bonus
- actionability 阈值

### 5.4 `trade_plan.py`

集中管理交易计划守门阈值：

- `LOW_CONFIDENCE_THRESHOLD`
- `LOW_COMPLETENESS_THRESHOLD`
- 未来的 RR 下限、事件避让窗口等

### 5.5 `technical.py` / `fundamental.py` / `sentiment.py` / `event.py`

集中管理模块内部规则常量：

- 技术模块窗口、均线、最小 bar 数
- 基本面模块的 margin / PE / completeness 阈值
- 情绪模块词表、最小新闻数、样本窗口
- 事件模块事件分类词表、近端风险窗口、宏观事件敏感窗口

### 5.6 `messages.py`

只管理稳定的、可复用的系统文案与 reason code：

- `technical` / `fundamental` / `sentiment` / `event` 的 degrade warning
- diagnostics 中会被测试或持久化消费的文案

不建议把所有普通摘要文案都塞进 `messages.py`；只集中稳定、可复用、可断言的文本。

---

## 6. 推荐代码组织方式

### 6.1 优先使用模块级常量，不要滥用动态配置

对当前 V1，规则更适合代码常量，而不是数据库配置或环境变量配置。

原因：

- 这些规则属于产品定义的一部分
- 当前项目强调确定性与 contract-first
- 规则改动应通过代码审阅、测试和版本升级管理

因此：

- 默认不要把规则阈值做成环境变量
- 默认不要放进数据库“可热更新”

### 6.2 使用不可变结构表达成组规则

对于成组常量，推荐用只读字典或 `dataclass(frozen=True)`。

示例：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionThresholds:
    bullish_bias_score: float = 0.15
    bearish_bias_score: float = -0.15
    actionable_confidence_floor: float = 0.45
    low_confidence_penalty: float = 0.1
    mixed_conflict_penalty: float = 0.1
    conflicted_penalty: float = 0.2


DECISION_THRESHOLDS = DecisionThresholds()
```

适用场景：

- 彼此相关的一组数值阈值
- 希望调用点具有可读字段名

### 6.3 保持 import 路径单向

`app/rules/*` 只能被其他层导入，不应反向依赖：

- 不导入 `FastAPI`
- 不导入 `ConnectionPool`
- 不导入 provider 实现

`rules` 应是全仓库最底层的纯常量依赖之一。

---

## 7. 版本号分层规则

本项目至少要区分三类版本：

### 7.1 存储版本

用途：

- 标记数据库记录遵循的持久化结构

当前字段：

- `storage_schema_version`
- `report_schema_version`

触发升级条件：

- 表结构变化
- 持久化 JSON 结构变化
- repository 写入语义变化

### 7.2 pipeline 版本

用途：

- 标记 graph 执行链与节点编排版本

当前字段：

- `pipeline_version`

触发升级条件：

- graph 节点顺序变化
- 核心节点增删
- 降级策略或综合流程发生结构变化

### 7.3 ruleset 版本

用途：

- 标记规则逻辑本身的版本，而不是存储层或 graph 层

当前代码里尚未正式建立，但 foundation 层建议补上。

推荐增加：

- `DECISION_RULESET_VERSION`
- `TRADE_PLAN_RULESET_VERSION`
- 各模块自己的 ruleset version

触发升级条件：

- 权重变化
- 评分阈值变化
- 词表变化
- 分类逻辑变化

---

## 8. 什么时候必须升级版本号

### 8.1 必须升级 `storage_schema_version`

当出现以下任一情况：

- 新增或删除数据库列
- 持久化 JSON 字段 shape 发生不兼容变化
- 老记录无法按同一解释方式读取

### 8.2 必须升级 `pipeline_version`

当出现以下任一情况：

- graph 执行顺序改变
- 新增或删除核心节点
- assemble/persist 不再消费同样的上游契约

### 8.3 必须升级对应 `ruleset version`

当出现以下任一情况：

- 对 bias / confidence / actionability 结论有影响的阈值改变
- 对 bullish / bearish / neutral 归类有影响的规则改变
- 对 do-not-trade 条件有影响的阈值改变
- 对词表命中逻辑有影响的词项改变

如果只是：

- 重构代码但行为不变
- 提取 helper
- 改注释

则不升级 ruleset version。

---

## 9. 推荐的改动流程

当 coding agent 修改规则时，按下面顺序执行：

1. 先确定修改属于哪一层
   - runtime
   - decision
   - trade_plan
   - technical / fundamental / sentiment / event

2. 把阈值放入对应 `app/rules/*.py`

3. 把使用处改为 import 常量，而不是继续写裸字面量

4. 判断是否需要升级版本号

5. 同步更新相关测试
   - schema test
   - node test
   - analysis rule test
   - repository test（如果持久化字段受影响）

6. 如果变更会影响历史记录解释，补充 migration 或兼容说明

---

## 10. 当前代码到目标状态的迁移优先级

优先迁移以下内容：

1. `prepare_context.py` 的默认值
2. `synthesize_decision.py` 的 `CONFIGURED_WEIGHTS` 和 completeness proxy
3. `decision.py` 的 bias/confidence/actionability 阈值
4. `trade_plan.py` 的 do-not-trade 阈值
5. `postgresql_analysis_reports.py` 的版本常量

第二优先级：

6. `sentiment.py` 的词表
7. `event.py` 的事件分类词表与近端窗口
8. `run_*` 节点中的 degrade reason / warning 文案

这样做的原因：

- 第一批直接影响系统级结论
- 第二批主要影响模块内部解释与 diagnostics

---

## 11. 不推荐的做法

- 把所有常量塞进一个巨大的 `app/constants.py`
- 把规则阈值做成环境变量
- 在测试里重新复制一套阈值而不是 import 规则常量
- 同一个阈值在 `analysis/`、`graph/nodes/`、`tests/` 各写一份
- 只修改数值，不判断是否应升级 ruleset version

---

## 12. Coding Agent 检查清单

修改规则相关代码前，先问自己：

1. 这是不是一个会影响行为的稳定常量
2. 它应该属于哪个 rules 模块
3. 它是否会影响已有持久化记录解释
4. 它是否应触发某个 version bump

提交前至少确认：

1. 没有新增裸字面量阈值扩散
2. 同类规则被集中放在一个 `app/rules/*.py`
3. 测试断言优先引用规则常量或稳定契约
4. 版本变更理由能说清楚

Foundation 层对规则管理的要求很简单：

- 规则要集中
- 版本要分层
- 变更要可追踪
- 不能让“改一个阈值”演变成全仓库盲改字符串
