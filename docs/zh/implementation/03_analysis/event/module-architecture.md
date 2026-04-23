# 事件模块实现架构

## 1. 文档目标

本文档定义事件模块在实现阶段的代码拆分、输入输出契约和新增文档边界。

当前实现入口：

- [`app/analysis/event.py`](/Users/leo/Dev/TradePilot/app/analysis/event.py:1)
- [`app/graph/nodes/run_event.py`](/Users/leo/Dev/TradePilot/app/graph/nodes/run_event.py:1)
- [`tests/graph/nodes/test_run_event.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_event.py:1)

---

## 2. 当前实现事实

当前事件模块只有一个轻量函数：

- 输入：`CompanyEvent[]` + `MacroCalendarEvent[]`
- 规则：近 14 天公司风险事件 + 近 7 天高重要性宏观事件 + 简单正面催化剂计数
- 输出：统一 `EventSignal`

当前还没有：

- 财报窗口状态
- 已排程事件分层
- 宏观敏感性标签
- richer 公司催化剂对象
- 受控 `event_risk_flags`

---

## 3. 为什么需要新增 4 份实现文档

design 里只有 `event_analysis_agent/overview.md`，但实现阶段至少需要拆成：

- `earnings-and-scheduled-events.md`
- `macro-sensitivity.md`
- `company-catalysts.md`
- `risk-aggregation.md`

否则 coding agent 无法明确：

- 哪些逻辑属于“公司日历”
- 哪些逻辑属于“宏观敏感性”
- 哪些逻辑属于“公司特定催化剂”
- 哪些逻辑只允许在最终聚合层做

---

## 4. 推荐代码组织

```text
app/analysis/event/
  __init__.py
  schemas.py
  module.py
  aggregate.py
  scheduled_events.py
  macro_sensitivity.py
  company_catalysts.py
```

职责：

- `scheduled_events.py`
  - 财报与已排程事件窗口
- `macro_sensitivity.py`
  - 宏观日程 + 标的敏感性
- `company_catalysts.py`
  - 监管/诉讼/并购/产品节点
- `aggregate.py`
  - `event_bias`、`upcoming_catalysts`、`risk_events`、`event_risk_flags`
- `module.py`
  - 模块总入口

---

## 5. 输入数据契约

当前稳定输入只有：

- `CompanyEvent[]`
- `MacroCalendarEvent[]`

目标实现至少要新增：

- `scheduled_company_events`
- `macro_events`
- `macro_sensitivity_context`
- `company_catalyst_events`

实现要求：

- 事件模块不要直接访问 provider 实现
- `direction_hint`、`event_state`、`event_status` 等 richer 字段应先在 dataset adapter 建模
- 未确认传闻不允许直接产出 bullish/bearish 方向

---

## 6. 输出契约

模块内部聚合结果至少应包含：

- `event_bias`
- `upcoming_catalysts`
- `risk_events`
- `event_risk_flags`
- `data_completeness_pct`
- `low_confidence_modules`

然后映射到当前 `AnalysisModuleResult`：

- `direction <- event_bias`
- `summary`
- `data_completeness_pct`
- `low_confidence`

---

## 7. 与 runtime 的对接方式

`run_event` 后续应收敛为：

1. 拉取标准化事件数据集
2. 调 `analyze_event_module(...)`
3. 映射回 `AnalysisModuleResult`
4. 写入 public source

不要继续在 node 内：

- 直接数事件类型
- 直接拼系统级风险 flag

---

## 8. 编码顺序

推荐顺序：

1. `schemas.py`
2. `aggregate.py`
3. `scheduled_events.py`
4. `macro_sensitivity.py`
5. `company_catalysts.py`

原因：

- 先定受控输出和 risk flag，再扩 richer 事件对象

---

## 9. 测试落点

- `tests/analysis/event/test_scheduled_events.py`
- `tests/analysis/event/test_macro_sensitivity.py`
- `tests/analysis/event/test_company_catalysts.py`
- `tests/analysis/event/test_aggregate.py`
- 现有 [`test_run_event.py`](/Users/leo/Dev/TradePilot/tests/graph/nodes/test_run_event.py:1) 保留 node 契约
