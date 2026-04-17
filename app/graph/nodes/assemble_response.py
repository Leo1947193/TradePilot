from __future__ import annotations

from app.schemas.api import (
    AnalysisResponse,
    Direction,
    EventDrivenAnalysis,
    EventRiskFlag,
    FundamentalAnalysis,
    FundamentalBias,
    NewsTone,
    SentimentExpectations,
    Source,
    TechnicalAnalysis,
    TechnicalSetupState,
    VolumePattern,
)
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisModuleResult, ModuleExecutionStatus


def assemble_response(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if not validated_state.normalized_ticker:
        raise ValueError("normalized_ticker is required to assemble response")
    if validated_state.context.analysis_time is None:
        raise ValueError("context.analysis_time is required to assemble response")
    if validated_state.decision_synthesis is None:
        raise ValueError("decision_synthesis is required to assemble response")
    if validated_state.trade_plan is None:
        raise ValueError("trade_plan is required to assemble response")

    deduplicated_sources = _deduplicate_sources(validated_state.sources)

    response = AnalysisResponse(
        ticker=validated_state.normalized_ticker,
        analysis_time=validated_state.context.analysis_time,
        technical_analysis=_build_technical_analysis(
            validated_state.module_results.technical,
            validated_state.decision_synthesis.actionability_state,
        ),
        fundamental_analysis=_build_fundamental_analysis(
            validated_state.module_results.fundamental,
        ),
        sentiment_expectations=_build_sentiment_expectations(
            validated_state.module_results.sentiment,
        ),
        event_driven_analysis=_build_event_driven_analysis(
            validated_state.module_results.event,
            validated_state.decision_synthesis.blocking_flags,
        ),
        decision_synthesis=validated_state.decision_synthesis,
        trade_plan=validated_state.trade_plan,
        sources=deduplicated_sources,
    )

    return validated_state.model_copy(update={"response": response, "sources": deduplicated_sources})


def _build_technical_analysis(
    result: AnalysisModuleResult | None,
    actionability_state: TechnicalSetupState,
) -> TechnicalAnalysis:
    summary = _build_summary(
        result,
        fallback="Technical analysis is operating in placeholder mode until market-data providers are integrated.",
    )
    return TechnicalAnalysis(
        technical_signal=Direction.NEUTRAL,
        trend=Direction.NEUTRAL,
        key_support=[],
        key_resistance=[],
        volume_pattern=VolumePattern.NEUTRAL,
        momentum="Momentum is unavailable in the current placeholder implementation.",
        entry_trigger=None,
        target_price=None,
        stop_loss_price=None,
        risk_reward_ratio=None,
        risk_flags=_build_risk_flags(result),
        setup_state=actionability_state,
        technical_summary=summary,
    )


def _build_fundamental_analysis(result: AnalysisModuleResult | None) -> FundamentalAnalysis:
    summary = _build_summary(
        result,
        fallback="Fundamental analysis is operating in placeholder mode until financial-data providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    return FundamentalAnalysis(
        fundamental_bias=FundamentalBias.NEUTRAL,
        composite_score=0.0,
        growth="Growth assessment is unavailable in the current placeholder implementation.",
        valuation_view="Valuation assessment is unavailable in the current placeholder implementation.",
        business_quality="Business-quality assessment is unavailable in the current placeholder implementation.",
        key_risks=_build_risk_flags(result),
        data_completeness_pct=completeness,
        fundamental_summary=summary,
    )


def _build_sentiment_expectations(result: AnalysisModuleResult | None) -> SentimentExpectations:
    summary = _build_summary(
        result,
        fallback="Sentiment analysis is operating in placeholder mode until news providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    return SentimentExpectations(
        sentiment_bias=Direction.NEUTRAL,
        news_tone=NewsTone.NEUTRAL,
        market_expectation="Market-expectation analysis is unavailable in the current placeholder implementation.",
        key_risks=_build_risk_flags(result),
        data_completeness_pct=completeness,
        sentiment_summary=summary,
    )


def _build_event_driven_analysis(
    result: AnalysisModuleResult | None,
    blocking_flags: list[str],
) -> EventDrivenAnalysis:
    summary = _build_summary(
        result,
        fallback="Event analysis is operating in placeholder mode until company-event and macro providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    event_flags = [EventRiskFlag(flag) for flag in blocking_flags if flag in EventRiskFlag._value2member_map_]
    return EventDrivenAnalysis(
        event_bias=Direction.NEUTRAL,
        upcoming_catalysts=[],
        risk_events=_build_risk_flags(result),
        event_risk_flags=event_flags,
        data_completeness_pct=completeness,
        event_summary=summary,
    )


def _build_summary(result: AnalysisModuleResult | None, fallback: str) -> str:
    if result is None:
        return fallback
    if result.summary and result.reason:
        return f"{result.summary} Reason: {result.reason}."
    if result.summary:
        return result.summary
    if result.reason:
        return result.reason
    return fallback


def _build_risk_flags(result: AnalysisModuleResult | None) -> list[str]:
    flags: list[str] = []
    if result is None:
        return flags
    if result.status == ModuleExecutionStatus.DEGRADED:
        flags.append("module_degraded")
    if result.reason:
        flags.append(result.reason)
    return flags


def _resolve_completeness(result: AnalysisModuleResult | None) -> float:
    if result is None:
        return 0.0
    if result.data_completeness_pct is not None:
        return result.data_completeness_pct
    if result.status == ModuleExecutionStatus.DEGRADED:
        return 70.0
    if result.status == ModuleExecutionStatus.EXCLUDED:
        return 0.0
    if result.status == ModuleExecutionStatus.USABLE:
        return 100.0
    return 0.0


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
