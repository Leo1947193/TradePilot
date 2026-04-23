from __future__ import annotations

from functools import lru_cache
import re
from pathlib import Path

import pytest

from app.api.main import app


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "docs/zh/implementation/01_runtime/runtime-contract.md"
GRAPH_PATH = ROOT / "docs/zh/implementation/01_runtime/langgraph-graph.md"
RESPONSE_PATH = ROOT / "docs/zh/implementation/01_runtime/response-assembly-and-api-mapping.md"
STACK_PATH = ROOT / "docs/zh/implementation/00_foundation/implementation-stack.md"
QUALITY_PATH = ROOT / "docs/zh/implementation/06_quality/test-strategy.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def openapi_schema() -> dict:
    return app.openapi()


def schema_block(schema_name: str) -> dict:
    schema = openapi_schema()["components"]["schemas"].get(schema_name)
    assert schema is not None, f"Schema {schema_name!r} was not found in OpenAPI."
    return schema


def field_schema(schema_name: str, field_name: str) -> dict:
    schema = schema_block(schema_name)
    properties = schema.get("properties", {})
    assert field_name in properties, f"Field {field_name!r} was not found in schema {schema_name!r}."
    return properties[field_name]


def _resolve_ref(schema_or_ref: dict) -> dict:
    ref = schema_or_ref.get("$ref")
    if ref is None:
        return schema_or_ref
    _, _, component_name = ref.rpartition("/")
    return schema_block(component_name)


def enum_values(schema_name: str, field_name: str) -> list[str]:
    resolved = _resolve_ref(field_schema(schema_name, field_name))
    values = resolved.get("enum")
    assert isinstance(values, list), f"Field {field_name!r} in schema {schema_name!r} is not an enum."
    return values


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
    schema = openapi_schema()
    paths = list(schema["paths"])

    assert paths == ["/api/v1/analyses"]
    assert schema["paths"]["/api/v1/analyses"]["post"]["operationId"] == "create_analysis_api_v1_analyses_post"


def test_analyze_request_remains_ticker_only_and_closed() -> None:
    block = schema_block("AnalyzeRequest")

    assert block["additionalProperties"] is False
    assert block["required"] == ["ticker"]
    assert field_schema("AnalyzeRequest", "ticker")["minLength"] == 1


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
        assert required_field in block["required"]

    assert block["additionalProperties"] is False
    assert field_schema("AnalysisResponse", "analysis_time")["format"] == "date-time"


@pytest.mark.parametrize(
    ("schema_name", "enum_field", "expected_enum"),
    [
        ("TechnicalAnalysis", "technical_signal", ["bullish", "neutral", "bearish"]),
        ("TechnicalAnalysis", "trend", ["bullish", "neutral", "bearish"]),
        ("TechnicalAnalysis", "setup_state", ["actionable", "watch", "avoid"]),
        ("FundamentalAnalysis", "fundamental_bias", ["bullish", "neutral", "bearish", "disqualified"]),
        ("SentimentExpectations", "sentiment_bias", ["bullish", "neutral", "bearish"]),
        ("EventDrivenAnalysis", "event_bias", ["bullish", "neutral", "bearish"]),
        ("DecisionSynthesis", "overall_bias", ["bullish", "neutral", "bearish"]),
        ("DecisionSynthesis", "actionability_state", ["actionable", "watch", "avoid"]),
        ("TradePlan", "overall_bias", ["bullish", "neutral", "bearish"]),
    ],
)
def test_public_enums_stay_lowercase_and_closed(
    schema_name: str,
    enum_field: str,
    expected_enum: list[str],
) -> None:
    assert enum_values(schema_name, enum_field) == expected_enum


def test_decision_synthesis_keeps_range_and_four_module_constraints() -> None:
    block = schema_block("DecisionSynthesis")

    assert field_schema("DecisionSynthesis", "bias_score")["minimum"] == -1.0
    assert field_schema("DecisionSynthesis", "bias_score")["maximum"] == 1.0
    assert field_schema("DecisionSynthesis", "confidence_score")["minimum"] == 0.0
    assert field_schema("DecisionSynthesis", "confidence_score")["maximum"] == 1.0
    assert field_schema("DecisionSynthesis", "module_contributions")["minItems"] == 4
    assert field_schema("DecisionSynthesis", "module_contributions")["maxItems"] == 4
    assert "weight_scheme_used" in block["required"]
    assert "blocking_flags" in block["required"]


def test_trade_plan_requires_both_directional_scenarios() -> None:
    block = schema_block("TradePlan")
    scenario_block = schema_block("TradeScenario")

    for required_field in (
        "overall_bias",
        "bullish_scenario",
        "bearish_scenario",
        "do_not_trade_conditions",
    ):
        assert required_field in block["required"]

    for required_field in ("entry_idea", "take_profit", "stop_loss"):
        assert required_field in scenario_block["required"]


def test_source_schema_requires_type_name_and_uri() -> None:
    block = schema_block("Source")

    for required_field in ("type", "name", "url"):
        assert required_field in block["required"]

    assert field_schema("Source", "url")["format"] == "uri"
    assert enum_values("Source", "type") == ["technical", "financial", "news", "macro", "event"]


def test_error_response_structure_is_stable_across_status_codes() -> None:
    response_block = openapi_schema()["paths"]["/api/v1/analyses"]["post"]["responses"]

    for status_code in ("200", "400", "404", "422", "503", "500"):
        assert status_code in response_block

    error_response = schema_block("ErrorResponse")
    error_object = schema_block("ErrorObject")
    error_detail = schema_block("ErrorDetail")

    assert error_response["required"] == ["error"]

    for required_field in ("code", "message"):
        assert required_field in error_object["required"]

    for required_field in ("field", "reason"):
        assert required_field in error_detail["required"]


def test_runtime_status_code_boundaries_match_spec() -> None:
    success_section = markdown_section(RESPONSE_PATH, r"## 7\. API 成功路径映射")
    error_section = markdown_section(RESPONSE_PATH, r"## 8\. API 错误路径映射")

    assert "graph 产出的 `response` 是唯一成功返回体" in success_section
    assert "### 8.1 400 `invalid_request`" in error_section
    assert "### 8.2 503 `upstream_unavailable`" in error_section
    assert "### 8.3 500 `internal_error`" in error_section
    assert "analysis persistence is unavailable" in error_section
    assert "analysis pipeline failed unexpectedly" in error_section


def test_runtime_allows_degradation_only_for_four_analysis_modules() -> None:
    error_section = markdown_section(RUNTIME_PATH, r"## 6\. 错误处理契约")
    graph_section = markdown_section(GRAPH_PATH, r"## 7\. 当前 graph 的执行语义")

    for module_name in ("run_technical", "run_fundamental", "run_sentiment", "run_event"):
        assert module_name in error_section

    assert "降级为 placeholder `DEGRADED`" in error_section
    assert "回退到 degraded placeholder" in error_section
    assert "当前 API 不会把“响应已生成但持久化失败”的半成功结果返回给客户端" in error_section
    assert "节点若抛异常，则 graph 直接失败" in graph_section


def test_runtime_retry_policy_is_whitelisted_to_external_fetches() -> None:
    foundation_text = read_text(STACK_PATH)
    graph_section = markdown_section(GRAPH_PATH, r"## 7\. 当前 graph 的执行语义")

    assert "自动重试框架" in foundation_text
    assert "没有启用：" in graph_section
    assert "- retries" in graph_section
    assert "不要让 graph 自行猜测重跑" in read_text(GRAPH_PATH)


def test_graph_execution_order_and_parallel_boundary_are_fixed() -> None:
    text = read_text(GRAPH_PATH)
    for marker in (
        "V --> C[prepare_context]",
        "C --> T[run_technical]",
        "C --> F[run_fundamental]",
        "C --> S[run_sentiment]",
        "C --> E[run_event]",
        "T --> D[synthesize_decision]",
        "D --> P[generate_trade_plan]",
        "P --> A[assemble_response]",
        "A --> R[persist_analysis]",
    ):
        assert marker in text

    assert "四个分析模块之间没有显式依赖，必须允许并行。" in text
    assert "`synthesize_decision` 必须等待四个模块都完成。" in text
    assert "`trade_plan` 必须依赖综合结论，不能提前生成。" in text


def test_docs_keep_testing_strategy_aligned_with_contract_first_scope() -> None:
    stack_text = read_text(STACK_PATH)
    quality_text = read_text(QUALITY_PATH)

    assert "1. API 契约测试" in stack_text
    assert "2. Graph 流程测试" in stack_text
    assert "3. Schema/状态模型测试" in stack_text
    assert "统一使用 `uv`" in stack_text
    assert "L1: 纯规则单元测试" in quality_text
