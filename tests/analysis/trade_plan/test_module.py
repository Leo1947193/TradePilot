from __future__ import annotations

from collections.abc import Callable

from app.analysis.trade_plan import build_trade_plan_from_decision
from app.schemas.api import DecisionSynthesis, TradePlan


def test_build_trade_plan_from_decision_preserves_public_trade_plan_shape(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="bearish",
            bias_score=0.75,
            confidence_score=0.82,
            actionability_state="actionable",
        )
    )

    signal = build_trade_plan_from_decision(decision)

    assert isinstance(signal.trade_plan, TradePlan)
    assert signal.trade_plan.overall_bias == "bearish"
    assert signal.trade_plan.bullish_scenario.entry_idea
    assert signal.trade_plan.bearish_scenario.entry_idea == (
        "Primary path favors short entries on a confirmed breakdown or a failed rebound into resistance."
    )
    assert signal.trade_plan.do_not_trade_conditions == []
