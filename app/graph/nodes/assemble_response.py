from __future__ import annotations

from app.analysis.response import build_public_module_payloads
from app.schemas.api import (
    AnalysisResponse,
    Source,
)
from app.schemas.graph_state import TradePilotState


def assemble_response(state: TradePilotState | dict) -> TradePilotState:
    payload = state.model_dump(mode="python") if isinstance(state, TradePilotState) else state
    validated_state = TradePilotState.model_validate(payload)

    if not validated_state.normalized_ticker:
        raise ValueError("normalized_ticker is required to assemble response")
    if validated_state.context.analysis_time is None:
        raise ValueError("context.analysis_time is required to assemble response")
    if validated_state.decision_synthesis is None:
        raise ValueError("decision_synthesis is required to assemble response")
    if validated_state.trade_plan is None:
        raise ValueError("trade_plan is required to assemble response")

    deduplicated_sources = _deduplicate_sources(validated_state.sources)
    (
        technical_analysis,
        fundamental_analysis,
        sentiment_expectations,
        event_driven_analysis,
    ) = build_public_module_payloads(validated_state)

    response = AnalysisResponse(
        ticker=validated_state.normalized_ticker,
        analysis_time=validated_state.context.analysis_time,
        technical_analysis=technical_analysis,
        fundamental_analysis=fundamental_analysis,
        sentiment_expectations=sentiment_expectations,
        event_driven_analysis=event_driven_analysis,
        decision_synthesis=validated_state.decision_synthesis,
        trade_plan=validated_state.trade_plan,
        sources=deduplicated_sources,
    )

    return validated_state.model_copy(update={"response": response, "sources": deduplicated_sources})


def _deduplicate_sources(sources: list[Source | dict]) -> list[Source]:
    deduplicated: list[Source] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        validated_source = Source.model_validate(source)
        key = (
            validated_source.type.value,
            validated_source.name,
            str(validated_source.url),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(validated_source)
    return deduplicated
