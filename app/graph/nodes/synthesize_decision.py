from __future__ import annotations

from app.analysis.synthesis import build_decision_synthesis
from app.schemas.graph_state import TradePilotState


def synthesize_decision(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)
    decision_synthesis = build_decision_synthesis(validated_state.module_results)

    return validated_state.model_copy(update={"decision_synthesis": decision_synthesis})
