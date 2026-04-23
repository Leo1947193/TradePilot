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
from app.schemas.api import AnalysisResponse, DecisionSynthesis, ModuleContribution, Source
from app.schemas.graph_state import ModuleReports, ModuleResults


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
                Source(type="technical", name="provider-a", url="https://example.com/a"),
                Source(type="technical", name="provider-a", url="https://example.com/a"),
                Source(type="news", name="provider-b", url="https://example.com/b"),
                Source(type="technical", name="provider-a", url="https://example.com/a"),
                Source(type="macro", name="provider-c", url="https://example.com/c"),
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


def test_assemble_response_maps_module_directions_into_public_payloads() -> None:
    base_state = build_pipeline_state()
    pipeline_state = base_state.model_copy(
        update={
            "module_results": ModuleResults.model_validate(
                {
                    "technical": {
                        "module": "technical",
                        "status": "usable",
                        "summary": "Trend remains constructive.",
                        "direction": "bullish",
                        "data_completeness_pct": 90,
                    },
                    "fundamental": {
                        "module": "fundamental",
                        "status": "usable",
                        "summary": "Profitability remains solid.",
                        "direction": "bullish",
                        "data_completeness_pct": 100,
                    },
                    "sentiment": {
                        "module": "sentiment",
                        "status": "usable",
                        "summary": "Coverage leans positive.",
                        "direction": "bullish",
                        "data_completeness_pct": 80,
                    },
                    "event": {
                        "module": "event",
                        "status": "usable",
                        "summary": "Near-term event risk remains elevated.",
                        "direction": "bearish",
                        "data_completeness_pct": 100,
                    },
                }
            ),
            "decision_synthesis": DecisionSynthesis.model_validate(
                {
                    **base_state.decision_synthesis.model_dump(mode="python"),
                    "overall_bias": "bullish",
                    "actionability_state": "watch",
                    "blocking_flags": ["macro_event_high_sensitivity"],
                    "module_contributions": [
                        ModuleContribution(
                            module="technical",
                            enabled=True,
                            status="usable",
                            direction="bullish",
                            direction_value=1,
                            configured_weight=0.5,
                            applied_weight=0.5,
                            contribution=0.5,
                            data_completeness_pct=90,
                            low_confidence=False,
                        ),
                        ModuleContribution(
                            module="fundamental",
                            enabled=True,
                            status="usable",
                            direction="bullish",
                            direction_value=1,
                            configured_weight=0.1,
                            applied_weight=0.1,
                            contribution=0.1,
                            data_completeness_pct=100,
                            low_confidence=False,
                        ),
                        ModuleContribution(
                            module="sentiment",
                            enabled=True,
                            status="usable",
                            direction="bullish",
                            direction_value=1,
                            configured_weight=0.2,
                            applied_weight=0.2,
                            contribution=0.2,
                            data_completeness_pct=80,
                            low_confidence=False,
                        ),
                        ModuleContribution(
                            module="event",
                            enabled=True,
                            status="usable",
                            direction="bearish",
                            direction_value=-1,
                            configured_weight=0.2,
                            applied_weight=0.2,
                            contribution=-0.2,
                            data_completeness_pct=100,
                            low_confidence=False,
                        ),
                    ],
                }
            ),
        }
    )

    state = assemble_response(pipeline_state)

    assert state.response is not None
    assert state.response.technical_analysis.technical_signal == "bullish"
    assert state.response.fundamental_analysis.fundamental_bias == "bullish"
    assert state.response.fundamental_analysis.composite_score == 0.1
    assert state.response.sentiment_expectations.sentiment_bias == "bullish"
    assert state.response.sentiment_expectations.news_tone == "positive"
    assert state.response.event_driven_analysis.event_bias == "bearish"
    assert state.response.event_driven_analysis.event_risk_flags == ["macro_event_high_sensitivity"]


def test_assemble_response_prefers_richer_module_reports_when_available() -> None:
    base_state = build_pipeline_state()
    pipeline_state = base_state.model_copy(
        update={
            "module_results": ModuleResults.model_validate(
                {
                    "technical": {
                        "module": "technical",
                        "status": "usable",
                        "summary": "Trend remains constructive.",
                        "direction": "bullish",
                        "data_completeness_pct": 90,
                    },
                    "fundamental": {
                        "module": "fundamental",
                        "status": "usable",
                        "summary": "Profitability remains solid.",
                        "direction": "bullish",
                        "data_completeness_pct": 100,
                    },
                    "sentiment": {
                        "module": "sentiment",
                        "status": "usable",
                        "summary": "Coverage leans positive.",
                        "direction": "bullish",
                        "data_completeness_pct": 80,
                    },
                    "event": {
                        "module": "event",
                        "status": "usable",
                        "summary": "Near-term event risk remains elevated.",
                        "direction": "bearish",
                        "data_completeness_pct": 100,
                    },
                }
            ),
            "module_reports": ModuleReports.model_validate(
                {
                    "technical": {
                        "trend": "bullish",
                        "key_support": [191.5, 188.0],
                        "key_resistance": [198.0, 202.5],
                        "volume_pattern": "accumulation",
                        "entry_trigger": "Watch for a move above 196.50 to confirm vcp.",
                        "target_price": 208.0,
                        "stop_loss_price": 191.0,
                        "risk_reward_ratio": 2.3,
                        "risk_flags": ["event_overhang"],
                        "summary": "Momentum remains constructive.",
                    },
                    "fundamental": {
                        "summary": "Integrated fundamental view remains constructive.",
                        "key_risks": ["financial_health_disqualify"],
                        "subresults": {
                            "financial_snapshot": {
                                "key_metrics": ["market cap 3000000000", "PE 28.20", "EPS 6.50"]
                            }
                        },
                    },
                    "sentiment": {
                        "news_tone": "positive",
                        "market_expectation": "Expectations are constructive with stable signals.",
                        "key_risks": ["crowded_narrative"],
                    },
                    "event": {
                        "upcoming_catalysts": ["Vision product launch"],
                        "risk_events": ["AAPL earnings"],
                        "event_risk_flags": ["binary_event_imminent"],
                    },
                }
            ),
        }
    )

    state = assemble_response(pipeline_state)

    assert state.response is not None
    assert state.response.technical_analysis.key_support == [191.5, 188.0]
    assert state.response.technical_analysis.entry_trigger == "Watch for a move above 196.50 to confirm vcp."
    assert state.response.fundamental_analysis.growth == "market cap 3000000000"
    assert state.response.fundamental_analysis.valuation_view == "PE 28.20"
    assert state.response.sentiment_expectations.market_expectation == "Expectations are constructive with stable signals."
    assert state.response.sentiment_expectations.key_risks == ["crowded_narrative"]
    assert state.response.event_driven_analysis.upcoming_catalysts == ["Vision product launch"]
    assert state.response.event_driven_analysis.risk_events == ["AAPL earnings"]
    assert state.response.event_driven_analysis.event_risk_flags == ["binary_event_imminent"]
