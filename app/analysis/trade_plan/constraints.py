from __future__ import annotations

from app.analysis.trade_plan.schemas import TradePlanInput
from app.rules.trade_plan import LOW_COMPLETENESS_THRESHOLD, LOW_CONFIDENCE_THRESHOLD
from app.schemas.api import TechnicalSetupState


def collect_do_not_trade_conditions(plan_input: TradePlanInput) -> list[str]:
    decision = plan_input.decision
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

    return _deduplicate(do_not_trade_conditions)


def _deduplicate(items: list[str]) -> list[str]:
    ordered_unique: list[str] = []
    for item in items:
        if item not in ordered_unique:
            ordered_unique.append(item)
    return ordered_unique
