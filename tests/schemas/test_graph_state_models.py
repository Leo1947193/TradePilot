from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.graph_state import PersistenceStatus, TradePilotState


def make_decision_synthesis_payload() -> dict:
    return {
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
    }


def make_trade_plan_payload() -> dict:
    return {
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
    }


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
        "decision_synthesis": make_decision_synthesis_payload(),
        "trade_plan": make_trade_plan_payload(),
        "sources": [
            {
                "type": "technical",
                "name": "yfinance",
                "url": "https://finance.yahoo.com/quote/AAPL/history",
            }
        ],
    }


def test_trade_pilot_state_requires_request_and_request_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TradePilotState.model_validate({})

    errors = exc_info.value.errors(include_url=False)
    assert errors[0]["loc"] == ("request",)
    assert errors[0]["type"] == "missing"
    assert errors[1]["loc"] == ("request_id",)
    assert errors[1]["type"] == "missing"


def test_trade_pilot_state_defaults_optional_sections_to_empty_state() -> None:
    state = TradePilotState.model_validate(
        {
            "request": {"ticker": "  AAPL  "},
            "request_id": "req_123",
        }
    )

    assert state.request.ticker == "AAPL"
    assert state.normalized_ticker is None
    assert state.context.analysis_time is None
    assert state.context.analysis_window_days is None
    assert state.provider_payloads.market is None
    assert state.module_results.technical is None
    assert state.module_reports.technical is None
    assert state.decision_synthesis is None
    assert state.trade_plan is None
    assert state.response is None
    assert state.sources == []
    assert state.persistence.status == PersistenceStatus.PENDING
    assert state.persistence.record_id is None
    assert state.diagnostics.degraded_modules == []
    assert state.diagnostics.excluded_modules == []
    assert state.diagnostics.warnings == []
    assert state.diagnostics.errors == []


def test_trade_pilot_state_accepts_public_contract_shapes() -> None:
    state = TradePilotState.model_validate(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
            "context": {
                "analysis_time": "2026-04-16T08:30:00Z",
                "market": "US",
                "benchmark": "SPY",
                "analysis_window_days": [7, 90],
            },
            "provider_payloads": {
                "market": {"source": "yfinance"},
                "financial": {"source": "yfinance"},
            },
            "module_results": {
                "technical": {"status": "usable"},
                "fundamental": {"status": "usable"},
                "sentiment": {"status": "degraded"},
                "event": {"status": "excluded"},
            },
            "decision_synthesis": make_decision_synthesis_payload(),
            "trade_plan": make_trade_plan_payload(),
            "response": make_response_payload(),
            "sources": make_response_payload()["sources"],
            "persistence": {
                "status": "succeeded",
                "record_id": "report_1",
                "persisted_at": "2026-04-16T08:31:00Z",
                "error": None,
            },
            "diagnostics": {
                "degraded_modules": ["sentiment"],
                "excluded_modules": ["event"],
                "warnings": ["event coverage missing"],
                "errors": [],
            },
        }
    )

    assert state.context.analysis_time == datetime(2026, 4, 16, 8, 30, tzinfo=timezone.utc)
    assert state.context.analysis_window_days == (7, 90)
    assert state.decision_synthesis is not None
    assert state.trade_plan is not None
    assert state.response is not None
    assert state.response.ticker == "AAPL"
    assert state.sources[0].name == "yfinance"
    assert state.persistence.status == PersistenceStatus.SUCCEEDED
    assert state.persistence.persisted_at == datetime(2026, 4, 16, 8, 31, tzinfo=timezone.utc)
    assert state.diagnostics.degraded_modules == ["sentiment"]
