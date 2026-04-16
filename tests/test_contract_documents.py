from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs/zh/api/openapi.yaml"
RUNTIME_PATH = ROOT / "docs/zh/implementation/runtime-contract.md"
GRAPH_PATH = ROOT / "docs/zh/implementation/langgraph-graph.md"
STACK_PATH = ROOT / "docs/zh/implementation/implementation-stack.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def schema_block(schema_name: str) -> str:
    openapi_text = read_text(OPENAPI_PATH)
    pattern = re.compile(
        rf"^    {re.escape(schema_name)}:\n(.*?)(?=^    [A-Za-z][A-Za-z0-9]+:|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(openapi_text)
    assert match, f"Schema {schema_name!r} was not found in OpenAPI."
    return match.group(1)


def markdown_section(path: Path, heading_pattern: str) -> str:
    text = read_text(path)
    pattern = re.compile(
        rf"^{heading_pattern}\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match, f"Section matching {heading_pattern!r} was not found in {path.name}."
    return match.group(1)


def test_openapi_declares_only_one_business_endpoint() -> None:
    text = read_text(OPENAPI_PATH)
    paths = re.findall(r"^  (/api/v1/[^\s:]+):$", text, flags=re.MULTILINE)

    assert paths == ["/api/v1/analyses"]
    assert "operationId: createAnalysis" in text


def test_analyze_request_remains_ticker_only_and_closed() -> None:
    block = schema_block("AnalyzeRequest")

    assert "additionalProperties: false" in block
    assert re.search(r"required:\n\s+- ticker", block)
    assert "minLength: 1" in block
    assert "description: 股票代码。服务端应先 trim 再校验。" in block


def test_analysis_response_keeps_fixed_top_level_shape() -> None:
    block = schema_block("AnalysisResponse")

    for required_field in (
        "ticker",
        "analysis_time",
        "technical_analysis",
        "fundamental_analysis",
        "sentiment_expectations",
        "event_driven_analysis",
        "decision_synthesis",
        "trade_plan",
        "sources",
    ):
        assert f"- {required_field}" in block

    assert "additionalProperties: false" in block
    assert "format: date-time" in block
    assert "example: '2026-04-16T08:30:00Z'" in block


@pytest.mark.parametrize(
    ("schema_name", "enum_field", "expected_enum"),
    [
        ("TechnicalAnalysis", "technical_signal", "enum: [bullish, neutral, bearish]"),
        ("TechnicalAnalysis", "trend", "enum: [bullish, neutral, bearish]"),
        ("TechnicalAnalysis", "setup_state", "enum: [actionable, watch, avoid]"),
        ("FundamentalAnalysis", "fundamental_bias", "enum: [bullish, neutral, bearish, disqualified]"),
        ("SentimentExpectations", "sentiment_bias", "enum: [bullish, neutral, bearish]"),
        ("EventDrivenAnalysis", "event_bias", "enum: [bullish, neutral, bearish]"),
        ("DecisionSynthesis", "overall_bias", "enum: [bullish, neutral, bearish]"),
        ("DecisionSynthesis", "actionability_state", "enum: [actionable, watch, avoid]"),
        ("TradePlan", "overall_bias", "enum: [bullish, neutral, bearish]"),
    ],
)
def test_public_enums_stay_lowercase_and_closed(
    schema_name: str,
    enum_field: str,
    expected_enum: str,
) -> None:
    block = schema_block(schema_name)

    assert f"{enum_field}:" in block
    assert expected_enum in block


def test_decision_synthesis_keeps_range_and_four_module_constraints() -> None:
    block = schema_block("DecisionSynthesis")

    assert "minimum: -1" in block
    assert "maximum: 1" in block
    assert "confidence_score:" in block
    assert re.search(r"confidence_score:\n\s+type: number\n\s+minimum: 0\n\s+maximum: 1", block)
    assert "module_contributions:" in block
    assert "minItems: 4" in block
    assert "maxItems: 4" in block
    assert "weight_scheme_used:" in block
    assert "blocking_flags:" in block


def test_trade_plan_requires_both_directional_scenarios() -> None:
    block = schema_block("TradePlan")
    scenario_block = schema_block("TradeScenario")

    for required_field in (
        "overall_bias",
        "bullish_scenario",
        "bearish_scenario",
        "do_not_trade_conditions",
    ):
        assert f"- {required_field}" in block

    for required_field in ("entry_idea", "take_profit", "stop_loss"):
        assert f"- {required_field}" in scenario_block


def test_source_schema_requires_type_name_and_uri() -> None:
    block = schema_block("Source")

    for required_field in ("type", "name", "url"):
        assert f"- {required_field}" in block

    assert "format: uri" in block
    assert "enum: [technical, financial, news, macro, event]" in block


def test_error_response_structure_is_stable_across_status_codes() -> None:
    openapi_text = read_text(OPENAPI_PATH)
    response_block = re.search(
        r"responses:\n(.*?)(?=^components:)",
        openapi_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert response_block, "Response block was not found in OpenAPI."
    response_text = response_block.group(1)

    for status_code in ("'200':", "'400':", "'404':", "'422':", "'503':", "'500':"):
        assert status_code in response_text

    error_response = schema_block("ErrorResponse")
    error_object = schema_block("ErrorObject")
    error_detail = schema_block("ErrorDetail")

    assert "required:" in error_response
    assert "- error" in error_response

    for required_field in ("code", "message"):
        assert f"- {required_field}" in error_object

    for required_field in ("field", "reason"):
        assert f"- {required_field}" in error_detail


def test_runtime_status_code_boundaries_match_spec() -> None:
    status_section = markdown_section(RUNTIME_PATH, r"## 6\. 状态码边界")

    expected_markers = {
        "200": "分析结果已成功持久化到 `PostgreSQL`",
        "400": "存在不允许的额外字段",
        "404": "ticker 无法映射到受支持的标的",
        "422": "无法建立最小分析上下文",
        "503": "`PostgreSQL` 在请求内不可用或写入超时",
        "500": "响应组装违反内部契约",
    }

    for status_code, marker in expected_markers.items():
        assert f"### 6.{('1' if status_code == '200' else {'400': '2', '404': '3', '422': '4', '503': '5', '500': '6'}[status_code])} 返回 `{status_code}" in status_section
        assert marker in status_section


def test_runtime_allows_degradation_only_for_four_analysis_modules() -> None:
    degradation_section = markdown_section(RUNTIME_PATH, r"## 7\. 降级规则")

    for module_name in ("technical", "fundamental", "sentiment", "event"):
        assert f"- {module_name}" in degradation_section

    for node_name in (
        "validate_request",
        "prepare_context",
        "assemble_response",
        "persist_analysis",
    ):
        assert f"- `{node_name}`" in degradation_section

    assert "不允许静默跳过" in read_text(GRAPH_PATH)


def test_runtime_retry_policy_is_whitelisted_to_external_fetches() -> None:
    retry_section = markdown_section(RUNTIME_PATH, r"## 5\. 重试策略")

    assert "只有外部数据获取允许自动重试" in retry_section
    assert "最多 `1` 次重试" in retry_section

    for forbidden_case in (
        "`4xx` 参数错误",
        "PostgreSQL 写入失败",
        "内部规则异常",
    ):
        assert forbidden_case in retry_section


def test_graph_execution_order_and_parallel_boundary_are_fixed() -> None:
    text = read_text(GRAPH_PATH)

    expected_flow = """validate_request
  -> prepare_context
  -> [run_technical, run_fundamental, run_sentiment, run_event]
  -> synthesize_decision
  -> generate_trade_plan
  -> assemble_response
  -> persist_analysis"""

    assert expected_flow in text
    assert "以下四个节点必须并行执行：" in text
    assert "`synthesize_decision` 必须等四个分析分支都结束" in text
    assert "`generate_trade_plan` 只能消费决策综合结果" in text


def test_docs_keep_testing_strategy_aligned_with_contract_first_scope() -> None:
    stack_text = read_text(STACK_PATH)

    assert "1. API 契约测试" in stack_text
    assert "2. Graph 流程测试" in stack_text
    assert "3. 规则单元测试" in stack_text
    assert "使用 `uv` 管理依赖与虚拟环境" in stack_text
