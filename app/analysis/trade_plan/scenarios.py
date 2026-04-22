from __future__ import annotations

from app.analysis.trade_plan.schemas import TradePlanInput
from app.schemas.api import Direction, TechnicalSetupState, TradeScenario


def build_bullish_scenario(plan_input: TradePlanInput) -> TradeScenario:
    decision = plan_input.decision
    if decision.overall_bias == Direction.BULLISH and decision.actionability_state == TechnicalSetupState.ACTIONABLE:
        return TradeScenario(
            entry_idea="Primary path favors long entries on a confirmed breakout or a constructive pullback retest.",
            take_profit="Scale out into strength near 2R and trail the remainder while the bullish bias stays intact.",
            stop_loss="Exit the long thesis on a failed breakout or a decisive loss of the trigger level.",
        )

    return TradeScenario(
        entry_idea=(
            f"Bullish scenario remains in {decision.actionability_state.value} mode; wait for clearer long confirmation before considering entry."
        ),
        take_profit="Keep bullish targets conditional until the system allows a clearer long setup.",
        stop_loss="Do not arm a live bullish stop-loss until a valid long trigger is present.",
    )


def build_bearish_scenario(plan_input: TradePlanInput) -> TradeScenario:
    decision = plan_input.decision
    if decision.overall_bias == Direction.BEARISH and decision.actionability_state == TechnicalSetupState.ACTIONABLE:
        return TradeScenario(
            entry_idea="Primary path favors short entries on a confirmed breakdown or a failed rebound into resistance.",
            take_profit="Scale out into weakness near 2R and trail the remainder while the bearish bias stays intact.",
            stop_loss="Exit the short thesis on a failed breakdown or a decisive reclaim of the trigger level.",
        )

    return TradeScenario(
        entry_idea=(
            f"Bearish scenario remains in {decision.actionability_state.value} mode; wait for clearer short confirmation before considering entry."
        ),
        take_profit="Keep bearish targets conditional until the system allows a clearer short setup.",
        stop_loss="Do not arm a live bearish stop-loss until a valid short trigger is present.",
    )
