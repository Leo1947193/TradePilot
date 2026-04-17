from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.api import (
    AnalysisResponse,
    DecisionSynthesis,
    EventDrivenAnalysis,
    FundamentalAnalysis,
    SentimentExpectations,
    Source,
)


def make_response_payload() -> dict:
    return {
        "ticker": "AAPL",
        "analysis_time": "2026-04-16T08:30:00Z",
        "technical_analysis": {
            "technical_signal": "bullish",
            "trend": "bullish",
            "key_support": [198.5, 194.0],
            "key_resistance": [205.0, 210.0],
            "volume_pattern": "accumulation",
            "momentum": "Momentum remains constructive on the daily timeframe.",
            "entry_trigger": "Daily close above 205 with volume expansion.",
            "target_price": 214.0,
            "stop_loss_price": 197.0,
            "risk_reward_ratio": 2.3,
            "risk_flags": ["near_resistance"],
            "setup_state": "actionable",
            "technical_summary": "Trend and momentum remain supportive.",
        },
        "fundamental_analysis": {
            "fundamental_bias": "bullish",
            "composite_score": 82.5,
            "growth": "Revenue growth remains above sector median.",
            "valuation_view": "Valuation is fair relative to quality.",
            "business_quality": "High-margin business with durable cash generation.",
            "key_risks": ["services_growth_slowdown"],
            "data_completeness_pct": 96.0,
            "fundamental_summary": "Fundamentals support medium-term upside.",
        },
        "sentiment_expectations": {
            "sentiment_bias": "neutral",
            "news_tone": "positive",
            "market_expectation": "Expectations are constructive but not euphoric.",
            "key_risks": ["crowded_positioning"],
            "data_completeness_pct": 88.0,
            "sentiment_summary": "News flow is modestly supportive.",
        },
        "event_driven_analysis": {
            "event_bias": "neutral",
            "upcoming_catalysts": ["product_launch"],
            "risk_events": ["earnings_next_month"],
            "event_risk_flags": ["macro_event_high_sensitivity"],
            "data_completeness_pct": 75.0,
            "event_summary": "No immediate catalyst dominates the setup.",
        },
        "decision_synthesis": {
            "overall_bias": "bullish",
            "bias_score": 0.42,
            "confidence_score": 0.76,
            "actionability_state": "watch",
            "conflict_state": "mixed",
            "data_completeness_pct": 89.0,
            "weight_scheme_used": {
                "configured_weights": {
                    "technical": 0.35,
                    "fundamental": 0.35,
                    "sentiment": 0.15,
                    "event": 0.15,
                },
                "enabled_modules": ["technical", "fundamental", "sentiment"],
                "disabled_modules": ["event"],
                "enabled_weight_sum": 0.85,
                "available_weight_sum": 0.85,
                "available_weight_ratio": 0.85,
                "applied_weights": {
                    "technical": 0.4118,
                    "fundamental": 0.4118,
                    "sentiment": 0.1764,
                    "event": None,
                },
                "renormalized": True,
            },
            "blocking_flags": ["event_module_unavailable"],
            "module_contributions": [
                {
                    "module": "technical",
                    "enabled": True,
                    "status": "usable",
                    "direction": "bullish",
                    "direction_value": 1,
                    "configured_weight": 0.35,
                    "applied_weight": 0.4118,
                    "contribution": 0.4118,
                    "data_completeness_pct": 95.0,
                    "low_confidence": False,
                },
                {
                    "module": "fundamental",
                    "enabled": True,
                    "status": "usable",
                    "direction": "bullish",
                    "direction_value": 1,
                    "configured_weight": 0.35,
                    "applied_weight": 0.4118,
                    "contribution": 0.4118,
                    "data_completeness_pct": 96.0,
                    "low_confidence": False,
                },
                {
                    "module": "sentiment",
                    "enabled": True,
                    "status": "degraded",
                    "direction": "neutral",
                    "direction_value": 0,
                    "configured_weight": 0.15,
                    "applied_weight": 0.1764,
                    "contribution": 0.0,
                    "data_completeness_pct": 88.0,
                    "low_confidence": True,
                },
                {
                    "module": "event",
                    "enabled": False,
                    "status": "excluded",
                    "direction": "disqualified",
                    "direction_value": 0,
                    "configured_weight": 0.15,
                    "applied_weight": None,
                    "contribution": None,
                    "data_completeness_pct": None,
                    "low_confidence": False,
                },
            ],
            "risks": ["event_coverage_missing"],
        },
        "trade_plan": {
            "overall_bias": "bullish",
            "bullish_scenario": {
                "entry_idea": "Buy a breakout with confirmation.",
                "take_profit": "Scale out into the 214 to 218 zone.",
                "stop_loss": "Exit below 197 on closing weakness.",
            },
            "bearish_scenario": {
                "entry_idea": "Fade failed breakout only if momentum rolls over.",
                "take_profit": "Cover into the 190 to 192 support area.",
                "stop_loss": "Exit above 206 on strength.",
            },
            "do_not_trade_conditions": ["headline_gap_against_setup"],
        },
        "sources": [
            {
                "type": "technical",
                "name": "yfinance",
                "url": "https://finance.yahoo.com/quote/AAPL/history",
            },
            {
                "type": "news",
                "name": "Finnhub",
                "url": "https://finnhub.io/api/v1/company-news?symbol=AAPL",
            },
        ],
    }


def test_analysis_response_accepts_documented_success_shape() -> None:
    response = AnalysisResponse.model_validate(make_response_payload())

    assert response.analysis_time == datetime(2026, 4, 16, 8, 30, tzinfo=timezone.utc)
    assert response.decision_synthesis.module_contributions[3].applied_weight is None
    assert response.decision_synthesis.module_contributions[3].contribution is None
    assert response.decision_synthesis.module_contributions[3].data_completeness_pct is None

    assert response.model_dump(mode="json") == make_response_payload()


def test_response_models_accept_documented_lowercase_enums() -> None:
    response = AnalysisResponse.model_validate(make_response_payload())
    payload = response.model_dump(mode="json")

    assert payload["technical_analysis"]["technical_signal"] == "bullish"
    assert payload["technical_analysis"]["setup_state"] == "actionable"
    assert payload["fundamental_analysis"]["fundamental_bias"] == "bullish"
    assert payload["sentiment_expectations"]["news_tone"] == "positive"
    assert payload["event_driven_analysis"]["event_risk_flags"] == ["macro_event_high_sensitivity"]
    assert payload["decision_synthesis"]["conflict_state"] == "mixed"
    assert payload["trade_plan"]["overall_bias"] == "bullish"
    assert payload["sources"][0]["type"] == "technical"


def test_source_url_must_be_a_valid_uri() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Source.model_validate(
            {
                "type": "news",
                "name": "Finnhub",
                "url": "not-a-uri",
            }
        )

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "url_parsing",
            "loc": ("url",),
            "msg": "Input should be a valid URL, relative URL without a base",
            "input": "not-a-uri",
            "ctx": {"error": "relative URL without a base"},
        }
    ]


@pytest.mark.parametrize(
    ("model_class", "field_name", "invalid_value", "expected_error_type"),
    [
        (DecisionSynthesis, "bias_score", -1.01, "greater_than_equal"),
        (DecisionSynthesis, "bias_score", 1.01, "less_than_equal"),
        (DecisionSynthesis, "confidence_score", -0.01, "greater_than_equal"),
        (DecisionSynthesis, "confidence_score", 1.01, "less_than_equal"),
        (FundamentalAnalysis, "data_completeness_pct", -0.01, "greater_than_equal"),
        (SentimentExpectations, "data_completeness_pct", 100.01, "less_than_equal"),
        (EventDrivenAnalysis, "data_completeness_pct", 100.01, "less_than_equal"),
    ],
)
def test_response_models_enforce_documented_numeric_bounds(
    model_class: type,
    field_name: str,
    invalid_value: float,
    expected_error_type: str,
) -> None:
    if model_class is DecisionSynthesis:
        payload = deepcopy(make_response_payload()["decision_synthesis"])
    elif model_class is FundamentalAnalysis:
        payload = deepcopy(make_response_payload()["fundamental_analysis"])
    elif model_class is SentimentExpectations:
        payload = deepcopy(make_response_payload()["sentiment_expectations"])
    else:
        payload = deepcopy(make_response_payload()["event_driven_analysis"])

    payload[field_name] = invalid_value

    with pytest.raises(ValidationError) as exc_info:
        model_class.model_validate(payload)

    assert exc_info.value.errors(include_url=False)[0]["loc"] == (field_name,)
    assert exc_info.value.errors(include_url=False)[0]["type"] == expected_error_type


def test_decision_synthesis_requires_exactly_four_module_contributions() -> None:
    payload = deepcopy(make_response_payload()["decision_synthesis"])
    payload["module_contributions"] = payload["module_contributions"][:3]

    with pytest.raises(ValidationError) as exc_info:
        DecisionSynthesis.model_validate(payload)

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "too_short",
            "loc": ("module_contributions",),
            "msg": "List should have at least 4 items after validation, not 3",
            "input": payload["module_contributions"],
            "ctx": {"field_type": "List", "min_length": 4, "actual_length": 3},
        }
    ]


def test_nullable_weights_and_contributions_are_required_but_may_be_none() -> None:
    payload = deepcopy(make_response_payload()["decision_synthesis"])
    excluded_module = payload["module_contributions"][3]

    synthesis = DecisionSynthesis.model_validate(payload)

    assert synthesis.weight_scheme_used.applied_weights.event is None
    assert synthesis.module_contributions[3].applied_weight is None
    assert synthesis.module_contributions[3].contribution is None
    assert synthesis.module_contributions[3].data_completeness_pct is None

    excluded_module.pop("applied_weight")

    with pytest.raises(ValidationError) as exc_info:
        DecisionSynthesis.model_validate(payload)

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "missing",
            "loc": ("module_contributions", 3, "applied_weight"),
            "msg": "Field required",
            "input": excluded_module,
        }
    ]
