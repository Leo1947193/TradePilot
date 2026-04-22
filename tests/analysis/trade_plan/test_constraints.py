from __future__ import annotations

from collections.abc import Callable

from app.analysis.trade_plan.constraints import collect_do_not_trade_conditions
from app.analysis.trade_plan.schemas import TradePlanInput
from app.schemas.api import DecisionSynthesis


def test_collect_do_not_trade_conditions_keeps_stable_order_and_ids(
    make_decision_payload: Callable[..., dict],
) -> None:
    decision = DecisionSynthesis.model_validate(
        make_decision_payload(
            blocking_flags=["macro_event_high_sensitivity", "macro_event_high_sensitivity"],
            conflict_state="conflicted",
            data_completeness_pct=55.0,
        )
    )

    conditions = collect_do_not_trade_conditions(TradePlanInput(decision=decision))

    assert conditions == [
        "confidence_score_below_0_55",
        "actionability_state_avoid",
        "macro_event_high_sensitivity",
        "conflict_state_conflicted",
        "data_completeness_below_60",
    ]
