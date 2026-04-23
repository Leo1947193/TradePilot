from __future__ import annotations

from collections.abc import Callable

from app.analysis.trade_plan import build_trade_plan_from_decision
from app.schemas.api import DecisionSynthesis


def test_trade_plan_golden_case_actionable_bullish(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="bullish",
            bias_score=0.82,
            confidence_score=0.82,
            actionability_state="actionable",
            risks=[],
        )
    )

    trade_plan = build_trade_plan_from_decision(decision).trade_plan

    assert trade_plan.overall_bias == "bullish"
    assert trade_plan.bullish_scenario.entry_idea == (
        "Primary path favors long entries on a confirmed breakout or a constructive pullback retest."
    )
    assert trade_plan.do_not_trade_conditions == []


def test_trade_plan_golden_case_avoid_neutral(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="neutral",
            bias_score=0.0,
            confidence_score=0.0,
            actionability_state="avoid",
            conflict_state="aligned",
            data_completeness_pct=70.0,
        )
    )

    trade_plan = build_trade_plan_from_decision(decision).trade_plan

    assert trade_plan.overall_bias == "neutral"
    assert trade_plan.bullish_scenario.entry_idea == (
        "Bullish scenario remains in avoid mode; wait for clearer long confirmation before considering entry."
    )
    assert trade_plan.bearish_scenario.entry_idea == (
        "Bearish scenario remains in avoid mode; wait for clearer short confirmation before considering entry."
    )
    assert trade_plan.do_not_trade_conditions == [
        "confidence_score_below_0_55",
        "actionability_state_avoid",
    ]


def test_trade_plan_golden_case_blocking_flags_passthrough(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="bullish",
            bias_score=0.4,
            confidence_score=0.82,
            actionability_state="watch",
            conflict_state="aligned",
            data_completeness_pct=85.0,
            blocking_flags=[
                "macro_event_high_sensitivity",
                "binary_event_imminent",
            ],
        )
    )

    trade_plan = build_trade_plan_from_decision(decision).trade_plan

    assert trade_plan.do_not_trade_conditions == [
        "macro_event_high_sensitivity",
        "binary_event_imminent",
    ]
