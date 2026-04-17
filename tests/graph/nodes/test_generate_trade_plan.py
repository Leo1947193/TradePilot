from __future__ import annotations

import pytest

from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.schemas.api import DecisionSynthesis, TradePlan


def make_decision_payload(**overrides: object) -> dict:
    payload = {
        "overall_bias": "neutral",
        "bias_score": 0.0,
        "confidence_score": 0.0,
        "actionability_state": "avoid",
        "conflict_state": "aligned",
        "data_completeness_pct": 70.0,
        "weight_scheme_used": {
            "configured_weights": {
                "technical": 0.5,
                "fundamental": 0.1,
                "sentiment": 0.2,
                "event": 0.2,
            },
            "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
            "disabled_modules": [],
            "enabled_weight_sum": 1.0,
            "available_weight_sum": 1.0,
            "available_weight_ratio": 1.0,
            "applied_weights": {
                "technical": 0.5,
                "fundamental": 0.1,
                "sentiment": 0.2,
                "event": 0.2,
            },
            "renormalized": False,
        },
        "blocking_flags": [],
        "module_contributions": [
            {
                "module": "technical",
                "enabled": True,
                "status": "degraded",
                "direction": "neutral",
                "direction_value": 0,
                "configured_weight": 0.5,
                "applied_weight": 0.5,
                "contribution": 0.0,
                "data_completeness_pct": 70.0,
                "low_confidence": True,
            },
            {
                "module": "fundamental",
                "enabled": True,
                "status": "degraded",
                "direction": "neutral",
                "direction_value": 0,
                "configured_weight": 0.1,
                "applied_weight": 0.1,
                "contribution": 0.0,
                "data_completeness_pct": 70.0,
                "low_confidence": True,
            },
            {
                "module": "sentiment",
                "enabled": True,
                "status": "degraded",
                "direction": "neutral",
                "direction_value": 0,
                "configured_weight": 0.2,
                "applied_weight": 0.2,
                "contribution": 0.0,
                "data_completeness_pct": 70.0,
                "low_confidence": True,
            },
            {
                "module": "event",
                "enabled": True,
                "status": "degraded",
                "direction": "neutral",
                "direction_value": 0,
                "configured_weight": 0.2,
                "applied_weight": 0.2,
                "contribution": 0.0,
                "data_completeness_pct": 70.0,
                "low_confidence": True,
            },
        ],
        "risks": ["当前仅有降级模块结果，综合结论不具备可执行性"],
    }
    payload.update(overrides)
    return payload


def test_generate_trade_plan_writes_valid_trade_plan() -> None:
    state = generate_trade_plan(
        {
            "request": {"ticker": "AAPL"},
            "request_id": "req_123",
            "decision_synthesis": make_decision_payload(),
        }
    )

    assert isinstance(state.trade_plan, TradePlan)
    assert state.trade_plan is not None
    assert state.trade_plan.bullish_scenario.entry_idea
    assert state.trade_plan.bearish_scenario.entry_idea


def test_generate_trade_plan_uses_actionable_bias_for_primary_scenario() -> None:
    state = generate_trade_plan(
        {
            "request": {"ticker": "AAPL"},
            "request_id": "req_actionable",
            "decision_synthesis": make_decision_payload(
                overall_bias="bullish",
                confidence_score=0.82,
                actionability_state="actionable",
            ),
        }
    )

    assert state.trade_plan is not None
    assert state.trade_plan.bullish_scenario.entry_idea == (
        "Primary path favors long entries on a confirmed breakout or a constructive pullback retest."
    )
    assert state.trade_plan.do_not_trade_conditions == []


def test_generate_trade_plan_copies_overall_bias_without_recomputing() -> None:
    state = generate_trade_plan(
        {
            "request": {"ticker": "AAPL"},
            "request_id": "req_456",
            "decision_synthesis": make_decision_payload(
                overall_bias="bearish",
                bias_score=0.75,
                actionability_state="watch",
            ),
        }
    )

    assert state.trade_plan is not None
    assert state.trade_plan.overall_bias == "bearish"


def test_generate_trade_plan_fails_fast_without_decision_synthesis() -> None:
    with pytest.raises(ValueError, match="decision_synthesis is required to generate trade plan"):
        generate_trade_plan(
            {
                "request": {"ticker": "AAPL"},
                "request_id": "req_missing",
            }
        )


def test_generate_trade_plan_populates_deterministic_do_not_trade_conditions() -> None:
    state = generate_trade_plan(
        {
            "request": {"ticker": "AAPL"},
            "request_id": "req_789",
            "sources": [
                {
                    "type": "technical",
                    "name": "placeholder",
                    "url": "https://example.com/source",
                }
            ],
            "decision_synthesis": make_decision_payload(
                blocking_flags=["macro_event_high_sensitivity", "macro_event_high_sensitivity"],
                conflict_state="conflicted",
                data_completeness_pct=55.0,
            ),
        }
    )

    assert state.trade_plan is not None
    assert state.trade_plan.do_not_trade_conditions == [
        "confidence_score_below_0_55",
        "actionability_state_avoid",
        "macro_event_high_sensitivity",
        "conflict_state_conflicted",
        "data_completeness_below_60",
    ]
    assert state.sources[0].name == "placeholder"
    assert state.decision_synthesis == DecisionSynthesis.model_validate(make_decision_payload(
        blocking_flags=["macro_event_high_sensitivity", "macro_event_high_sensitivity"],
        conflict_state="conflicted",
        data_completeness_pct=55.0,
    ))
