from __future__ import annotations

from app.analysis.trade_plan import build_trade_plan_from_decision
from app.schemas.graph_state import TradePilotState


def generate_trade_plan(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)
    decision = validated_state.decision_synthesis
    if decision is None:
        raise ValueError("decision_synthesis is required to generate trade plan")

    trade_plan_signal = build_trade_plan_from_decision(decision)
    return validated_state.model_copy(update={"trade_plan": trade_plan_signal.trade_plan})
