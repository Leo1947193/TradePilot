from __future__ import annotations

from datetime import datetime, timezone

from app.rules.messages import PREPARE_CONTEXT_NORMALIZED_TICKER_REQUIRED_ERROR
from app.rules.runtime import DEFAULT_ANALYSIS_WINDOW_DAYS, DEFAULT_BENCHMARK, DEFAULT_MARKET
from app.schemas.graph_state import GraphContext, TradePilotState


def prepare_context(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)
    normalized_ticker = validated_state.normalized_ticker

    if normalized_ticker is None or not normalized_ticker.strip():
        raise ValueError(PREPARE_CONTEXT_NORMALIZED_TICKER_REQUIRED_ERROR)

    existing_context = validated_state.context
    prepared_context = GraphContext(
        analysis_time=existing_context.analysis_time or datetime.now(timezone.utc),
        market=existing_context.market or DEFAULT_MARKET,
        benchmark=existing_context.benchmark or DEFAULT_BENCHMARK,
        analysis_window_days=existing_context.analysis_window_days or DEFAULT_ANALYSIS_WINDOW_DAYS,
    )

    return validated_state.model_copy(update={"context": prepared_context})
