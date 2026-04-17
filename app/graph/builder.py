from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.assemble_response import assemble_response
from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.graph.nodes.persist_analysis import persist_analysis
from app.graph.nodes.prepare_context import prepare_context
from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.graph.nodes.validate_request import validate_request
from app.repositories.analysis_reports import AnalysisReportRepository
from app.services.providers.interfaces import (
    CompanyEventsProvider,
    FinancialDataProvider,
    MacroCalendarProvider,
    MarketDataProvider,
)


def _merge_dict_updates(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _merge_diagnostics(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = {
        "degraded_modules": [],
        "excluded_modules": [],
        "warnings": [],
        "errors": [],
    }

    for payload in (left or {}, right or {}):
        for key in merged:
            for item in payload.get(key, []):
                if item not in merged[key]:
                    merged[key].append(item)

    return merged


def _merge_sources(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    source_order = {
        "technical": 0,
        "financial": 1,
        "news": 2,
        "event": 3,
        "macro": 4,
    }
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    for payload in [*(left or []), *(right or [])]:
        key = (payload.get("type"), payload.get("name"), str(payload.get("url")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(payload)

    return sorted(
        merged,
        key=lambda payload: (
            source_order.get(str(payload.get("type")), 99),
            str(payload.get("name")),
            str(payload.get("url")),
        ),
    )


class AnalysisGraphState(TypedDict, total=False):
    request: dict[str, Any]
    normalized_ticker: str | None
    request_id: str
    context: dict[str, Any]
    provider_payloads: dict[str, Any]
    module_results: Annotated[dict[str, Any], _merge_dict_updates]
    decision_synthesis: dict[str, Any] | None
    trade_plan: dict[str, Any] | None
    response: dict[str, Any] | None
    sources: Annotated[list[dict[str, Any]], _merge_sources]
    persistence: dict[str, Any]
    diagnostics: Annotated[dict[str, Any], _merge_diagnostics]


def build_analysis_graph(
    repository: AnalysisReportRepository,
    *,
    market_data_provider: MarketDataProvider | None = None,
    financial_data_provider: FinancialDataProvider | None = None,
    company_events_provider: CompanyEventsProvider | None = None,
    macro_calendar_provider: MacroCalendarProvider | None = None,
):
    graph = StateGraph(AnalysisGraphState)

    graph.add_node("validate_request", _wrap_node(validate_request, "request", "normalized_ticker", "request_id"))
    graph.add_node("prepare_context", _wrap_node(prepare_context, "context"))
    graph.add_node(
        "run_technical",
        _wrap_module_node(
            lambda state: run_technical(state, market_data_provider=market_data_provider),
            "technical",
            include_sources=market_data_provider is not None,
        ),
    )
    graph.add_node(
        "run_fundamental",
        _wrap_module_node(
            lambda state: run_fundamental(state, financial_data_provider=financial_data_provider),
            "fundamental",
            include_sources=financial_data_provider is not None,
        ),
    )
    graph.add_node("run_sentiment", _wrap_module_node(run_sentiment, "sentiment"))
    graph.add_node(
        "run_event",
        _wrap_module_node(
            lambda state: run_event(
                state,
                company_events_provider=company_events_provider,
                macro_calendar_provider=macro_calendar_provider,
            ),
            "event",
            include_sources=company_events_provider is not None and macro_calendar_provider is not None,
        ),
    )
    graph.add_node("synthesize_decision", _wrap_node(synthesize_decision, "decision_synthesis"))
    graph.add_node("generate_trade_plan", _wrap_node(generate_trade_plan, "trade_plan"))
    graph.add_node("assemble_response", _wrap_node(assemble_response, "response", "sources"))
    graph.add_node(
        "persist_analysis",
        _wrap_node(lambda state: persist_analysis(state, repository), "persistence"),
    )

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "prepare_context")
    graph.add_edge("prepare_context", "run_technical")
    graph.add_edge("prepare_context", "run_fundamental")
    graph.add_edge("prepare_context", "run_sentiment")
    graph.add_edge("prepare_context", "run_event")
    graph.add_edge(
        ["run_technical", "run_fundamental", "run_sentiment", "run_event"],
        "synthesize_decision",
    )
    graph.add_edge("synthesize_decision", "generate_trade_plan")
    graph.add_edge("generate_trade_plan", "assemble_response")
    graph.add_edge("assemble_response", "persist_analysis")
    graph.add_edge("persist_analysis", END)

    return graph.compile(name="tradepilot_analysis_graph")


def _wrap_node(node, *keys: str):
    def wrapped(state: AnalysisGraphState) -> dict[str, Any]:
        result = node(state)
        payload = result.model_dump(mode="python")
        return {key: payload[key] for key in keys}

    return wrapped


def _wrap_module_node(node, module_key: str, *, include_sources: bool = False):
    def wrapped(state: AnalysisGraphState) -> dict[str, Any]:
        result = node(state)
        payload = result.model_dump(mode="python")
        output = {
            "module_results": {module_key: payload["module_results"][module_key]},
            "diagnostics": payload["diagnostics"],
        }
        if include_sources:
            output["sources"] = payload["sources"]
        return output

    return wrapped
