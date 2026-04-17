from __future__ import annotations

from dataclasses import dataclass

from app.schemas.api import DecisionSynthesis, Direction, TechnicalSetupState, TradePlan, TradeScenario


LOW_CONFIDENCE_THRESHOLD = 0.55
LOW_COMPLETENESS_THRESHOLD = 60.0


@dataclass(frozen=True)
class TradePlanSignal:
    trade_plan: TradePlan


def build_trade_plan_from_decision(decision: DecisionSynthesis) -> TradePlanSignal:
    do_not_trade_conditions: list[str] = []

    if decision.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        do_not_trade_conditions.append("confidence_score_below_0_55")

    if decision.actionability_state == TechnicalSetupState.AVOID:
        do_not_trade_conditions.append("actionability_state_avoid")

    do_not_trade_conditions.extend(decision.blocking_flags)

    if decision.conflict_state == "conflicted":
        do_not_trade_conditions.append("conflict_state_conflicted")

    if decision.data_completeness_pct < LOW_COMPLETENESS_THRESHOLD:
        do_not_trade_conditions.append("data_completeness_below_60")

    trade_plan = TradePlan(
        overall_bias=decision.overall_bias,
        bullish_scenario=_build_bullish_scenario(decision),
        bearish_scenario=_build_bearish_scenario(decision),
        do_not_trade_conditions=_deduplicate(do_not_trade_conditions),
    )
    return TradePlanSignal(trade_plan=trade_plan)


def _build_bullish_scenario(decision: DecisionSynthesis) -> TradeScenario:
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


def _build_bearish_scenario(decision: DecisionSynthesis) -> TradeScenario:
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


def _deduplicate(items: list[str]) -> list[str]:
    ordered_unique: list[str] = []
    for item in items:
        if item not in ordered_unique:
            ordered_unique.append(item)
    return ordered_unique
