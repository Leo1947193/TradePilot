# 数据源契约

## 1. 目标

本文档固定 V1 的数据源接口和默认 provider 选择，避免 coding agent 在实现时自行发明数据来源。

原则：

- 先定义 provider 抽象
- 再定义 V1 默认实现
- 允许后续替换具体供应商，但不允许跳过抽象层

---

## 2. V1 provider 策略

V1 采用“抽象接口 + 默认实现”的方式：

- 抽象接口是必须的
- 默认实现可以先满足最小可运行需求
- 后续替换商业 provider 时，不改分析规则层

---

## 3. Provider 抽象

V1 至少定义以下 provider 接口：

1. `MarketDataProvider`
   负责 OHLCV、基础价格窗口、成交量和基准数据。
2. `FinancialDataProvider`
   负责财务报表摘要、估值所需基础字段。
3. `CompanyEventsProvider`
   负责财报日期和公司级事件窗口。
4. `NewsDataProvider`
   负责新闻标题、发布时间、来源和链接。
5. `MacroCalendarProvider`
   负责 FOMC、CPI、非农等宏观事件日程。

所有 provider 输出都必须标准化为内部 DTO，不允许让分析模块直接消费第三方原始 payload。

---

## 4. V1 默认实现

### 4.1 市场数据

- 默认实现：`yfinance`
- 用途：
  - 日线 / 周线 OHLCV
  - 基础公司信息
  - 简单基准行情

说明：

- V1 允许用 `yfinance` 先打通端到端
- 若后续替换为商业行情源，应保持 `MarketDataProvider` 接口不变

### 4.2 财务数据

- 默认实现：`yfinance`
- 用途：
  - 轻量级财务字段
  - 基础估值字段
  - 财报历史的最小支撑信息

限制：

- V1 不追求机构级财务覆盖率
- 若关键字段缺失，必须走 `degraded/excluded`，不得猜值

### 4.3 公司事件

- 默认实现：`yfinance`
- 用途：
  - 财报日期
  - 公司日历中的最小可得字段

### 4.4 新闻数据

- 默认实现：`Finnhub` 或等价新闻 REST provider
- 配置：通过环境变量注入 API key

要求：

- 至少返回标题、发布时间、来源名称、URL
- 若未配置新闻 API key，情绪模块允许降级，但不得导致整个请求直接失败

### 4.5 宏观日历

- 默认实现：`StaticMacroCalendarProvider`
- 数据来源：仓库内维护的静态日历文件

原因：

- 这样可以先让事件模块具备确定性
- 避免 coding agent 在第一阶段被外部宏观日历集成阻塞

后续若接入实时宏观日历 provider，应只替换 `MacroCalendarProvider` 的实现。

---

## 5. 各模块依赖关系

### 5.1 技术分析模块

依赖：

- `MarketDataProvider`

必需数据：

- 最近 `6-12` 个月日线 OHLCV
- 关键基准标的价格

### 5.2 基本面分析模块

依赖：

- `FinancialDataProvider`
- `MarketDataProvider`

必需数据：

- 最近财报摘要
- 基础估值字段
- 必要时的价格上下文

### 5.3 情绪分析模块

依赖：

- `NewsDataProvider`

可选补充：

- `MarketDataProvider` 仅用于上下文，不用于新闻抓取

### 5.4 事件分析模块

依赖：

- `CompanyEventsProvider`
- `MacroCalendarProvider`
- 可选 `NewsDataProvider`

说明：

- 事件模块先做“时间型事件”识别
- 不依赖情绪模块结果

---

## 6. 缓存策略

V1 先采用进程内 TTL 缓存。

### 6.1 推荐 TTL

- 市场数据：`15m`
- 财务数据：`6h`
- 公司事件：`6h`
- 新闻数据：`15m`
- 宏观静态日历：进程启动时加载，可按日刷新

### 6.2 约束

- 缓存属于 provider 层责任
- 分析模块不直接处理缓存逻辑
- 缓存命中与否不应改变业务语义

---

## 7. 限流与失败策略

### 7.1 限流

provider 适配层必须预留：

- 每 provider 独立速率限制配置
- 简单重试和退避能力

V1 不要求实现复杂令牌桶，但接口设计要预留。

### 7.2 失败处理

数据源失败时按以下原则处理：

- 公共上下文必需 provider 失败：请求报错
- 单模块专属 provider 失败：模块降级
- 新闻 provider 未配置：情绪模块降级
- 宏观静态日历缺失：事件模块降级

---

## 8. 来源映射规则

顶层 `sources.type` 与 provider 的映射固定如下：

| provider 类型 | `sources.type` |
|---|---|
| 市场数据 | `technical` |
| 财务数据 | `financial` |
| 新闻数据 | `news` |
| 宏观日历 | `macro` |
| 公司事件 | `event` |

每个 provider 输出必须至少携带：

- `name`
- `url` 或稳定引用标识
- `fetched_at`

---

## 9. 环境变量

V1 预留以下环境变量：

- `NEWS_API_KEY`
- `MARKET_DATA_PROVIDER`
- `NEWS_PROVIDER`
- `MACRO_CALENDAR_PATH`
- `REQUEST_TIMEOUT_SECONDS`

说明：

- `yfinance` 相关 provider 可不要求 API key
- provider 名称用来切换实现，而不是让业务代码分支判断

---

## 10. coding agent 的默认实施策略

coding agent 开工时应按以下顺序处理数据源：

1. 先写 provider 抽象接口
2. 再写 `yfinance` 实现
3. 再写静态宏观日历实现
4. 再写新闻 provider
5. 最后把来源信息挂到顶层 `sources`

禁止直接在分析模块里散写第三方 SDK 调用。
