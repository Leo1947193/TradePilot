from __future__ import annotations

import pytest

from app.graph.nodes.assemble_response import assemble_response
from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.graph.nodes.prepare_context import prepare_context
from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.graph.nodes.validate_request import validate_request
from app.schemas.api import AnalysisResponse


def build_state_with_plan() -> dict:
    return {
        "request": {"ticker": " aapl "},
        "request_id": "req_123",
    }


def build_pipeline_state() -> object:
    state = validate_request(build_state_with_plan())
    state = prepare_context(state)
    state = run_technical(state)
    state = run_fundamental(state)
    state = run_sentiment(state)
    state = run_event(state)
    state = synthesize_decision(state)
    state = generate_trade_plan(state)
    return state


def test_assemble_response_writes_valid_public_response() -> None:
    state = assemble_response(build_pipeline_state())

    assert isinstance(state.response, AnalysisResponse)
    assert state.response is not None
    assert state.response.ticker == "AAPL"
    assert state.response.decision_synthesis == state.decision_synthesis
    assert state.response.trade_plan == state.trade_plan


def test_assemble_response_deduplicates_sources_in_first_use_order() -> None:
    pipeline_state = build_pipeline_state()
    pipeline_state = pipeline_state.model_copy(
        update={
            "sources": [
                {
                    "type": "technical",
                    "name": "provider-a",
                    "url": "https://example.com/a",
                },
                {
                    "type": "technical",
                    "name": "provider-a",
                    "url": "https://example.com/a",
                },
                {
                    "type": "news",
                    "name": "provider-b",
                    "url": "https://example.com/b",
                },
                {
                    "type": "technical",
                    "name": "provider-a",
                    "url": "https://example.com/a",
                },
                {
                    "type": "macro",
                    "name": "provider-c",
                    "url": "https://example.com/c",
                },
            ]
        }
    )

    state = assemble_response(pipeline_state)

    assert [source.name for source in state.response.sources] == [
        "provider-a",
        "provider-b",
        "provider-c",
    ]
    assert [source.name for source in state.sources] == [
        "provider-a",
        "provider-b",
        "provider-c",
    ]


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("normalized_ticker", "normalized_ticker is required to assemble response"),
        ("analysis_time", "context.analysis_time is required to assemble response"),
        ("decision_synthesis", "decision_synthesis is required to assemble response"),
        ("trade_plan", "trade_plan is required to assemble response"),
    ],
)
def test_assemble_response_fails_fast_when_required_state_is_missing(
    field: str,
    message: str,
) -> None:
    state = build_pipeline_state()

    if field == "normalized_ticker":
        broken_state = state.model_copy(update={"normalized_ticker": None, "response": None})
    elif field == "analysis_time":
        broken_state = state.model_copy(
            update={"context": state.context.model_copy(update={"analysis_time": None}), "response": None}
        )
    elif field == "decision_synthesis":
        broken_state = state.model_copy(update={"decision_synthesis": None, "response": None})
    else:
        broken_state = state.model_copy(update={"trade_plan": None, "response": None})

    with pytest.raises(ValueError, match=message):
        assemble_response(broken_state)


def test_assemble_response_reflects_placeholder_module_summaries() -> None:
    state = assemble_response(build_pipeline_state())

    assert state.response is not None
    assert "Technical analysis is degraded" in state.response.technical_analysis.technical_summary
    assert "Fundamental analysis is degraded" in state.response.fundamental_analysis.fundamental_summary
    assert "Sentiment analysis is degraded" in state.response.sentiment_expectations.sentiment_summary
    assert "Event analysis is degraded" in state.response.event_driven_analysis.event_summary
