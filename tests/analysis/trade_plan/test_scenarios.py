from __future__ import annotations

from collections.abc import Callable

from app.analysis.trade_plan.scenarios import build_bearish_scenario, build_bullish_scenario
from app.analysis.trade_plan.schemas import TradePlanInput
from app.schemas.api import DecisionSynthesis


def test_build_bullish_scenario_uses_actionable_primary_template(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="bullish",
            confidence_score=0.82,
            actionability_state="actionable",
        )
    )

    scenario = build_bullish_scenario(TradePlanInput(decision=decision))

    assert scenario.entry_idea == (
        "Primary path favors long entries on a confirmed breakout or a constructive pullback retest."
    )


def test_build_bearish_scenario_uses_wait_template_when_not_actionable(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            overall_bias="bearish",
            confidence_score=0.78,
            actionability_state="watch",
        )
    )

    scenario = build_bearish_scenario(TradePlanInput(decision=decision))

    assert scenario.entry_idea == (
        "Bearish scenario remains in watch mode; wait for clearer short confirmation before considering entry."
    )
