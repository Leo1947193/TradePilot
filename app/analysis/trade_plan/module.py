from __future__ import annotations

from app.analysis.trade_plan.constraints import collect_do_not_trade_conditions
from app.analysis.trade_plan.scenarios import build_bearish_scenario, build_bullish_scenario
from app.analysis.trade_plan.schemas import TradePlanInput, TradePlanSignal
from app.schemas.api import DecisionSynthesis, TradePlan


def build_trade_plan_from_decision(decision: DecisionSynthesis) -> TradePlanSignal:
    return build_trade_plan(TradePlanInput(decision=decision))


def build_trade_plan(plan_input: TradePlanInput) -> TradePlanSignal:
    decision = plan_input.decision
    trade_plan = TradePlan(
        overall_bias=decision.overall_bias,
        bullish_scenario=build_bullish_scenario(plan_input),
        bearish_scenario=build_bearish_scenario(plan_input),
        do_not_trade_conditions=collect_do_not_trade_conditions(plan_input),
    )
    return TradePlanSignal(trade_plan=trade_plan)
