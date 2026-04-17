from __future__ import annotations

from app.schemas.api import TechnicalSetupState, TradePlan, TradeScenario
from app.schemas.graph_state import TradePilotState


LOW_CONFIDENCE_THRESHOLD = 0.55
LOW_COMPLETENESS_THRESHOLD = 60.0


def generate_trade_plan(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)
    decision = validated_state.decision_synthesis
    if decision is None:
        raise ValueError("decision_synthesis is required to generate trade plan")

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
        bullish_scenario=_build_bullish_scenario(decision.actionability_state.value),
        bearish_scenario=_build_bearish_scenario(decision.actionability_state.value),
        do_not_trade_conditions=_deduplicate(do_not_trade_conditions),
    )

    return validated_state.model_copy(update={"trade_plan": trade_plan})


def _build_bullish_scenario(actionability_state: str) -> TradeScenario:
    return TradeScenario(
        entry_idea=(
            f"Bullish scenario remains in {actionability_state} mode; wait for a confirmed long trigger before considering entry."
        ),
        take_profit="Do not set a live bullish take-profit plan until system-level actionability improves.",
        stop_loss="Do not arm a bullish stop-loss until a valid long setup is available.",
    )


def _build_bearish_scenario(actionability_state: str) -> TradeScenario:
    return TradeScenario(
        entry_idea=(
            f"Bearish scenario remains in {actionability_state} mode; wait for a confirmed short trigger before considering entry."
        ),
        take_profit="Do not set a live bearish take-profit plan until system-level actionability improves.",
        stop_loss="Do not arm a bearish stop-loss until a valid short setup is available.",
    )


def _deduplicate(items: list[str]) -> list[str]:
    ordered_unique: list[str] = []
    for item in items:
        if item not in ordered_unique:
            ordered_unique.append(item)
    return ordered_unique
