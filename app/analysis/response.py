from __future__ import annotations

from app.schemas.api import (
    Direction,
    EventDrivenAnalysis,
    EventRiskFlag,
    FundamentalAnalysis,
    FundamentalBias,
    ModuleName,
    NewsTone,
    SentimentExpectations,
    TechnicalAnalysis,
    TechnicalSetupState,
    VolumePattern,
)
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisDirection, AnalysisModuleResult, ModuleExecutionStatus


def build_public_module_payloads(
    state: TradePilotState,
) -> tuple[TechnicalAnalysis, FundamentalAnalysis, SentimentExpectations, EventDrivenAnalysis]:
    module_contributions = {item.module: item for item in state.decision_synthesis.module_contributions}

    technical = _build_technical_analysis(
        state.module_results.technical,
        state.decision_synthesis.actionability_state,
    )
    fundamental = _build_fundamental_analysis(
        state.module_results.fundamental,
        module_contributions[ModuleName.FUNDAMENTAL].contribution,
    )
    sentiment = _build_sentiment_expectations(
        state.module_results.sentiment,
    )
    event = _build_event_driven_analysis(
        state.module_results.event,
        state.decision_synthesis.blocking_flags,
    )
    return technical, fundamental, sentiment, event


def _build_technical_analysis(
    result: AnalysisModuleResult | None,
    actionability_state: TechnicalSetupState,
) -> TechnicalAnalysis:
    summary = _build_summary(
        result,
        fallback="Technical analysis is operating in placeholder mode until market-data providers are integrated.",
    )
    direction = _map_direction(result.direction if result else None)
    return TechnicalAnalysis(
        technical_signal=direction,
        trend=direction,
        key_support=[],
        key_resistance=[],
        volume_pattern=VolumePattern.NEUTRAL,
        momentum=summary,
        entry_trigger=None,
        target_price=None,
        stop_loss_price=None,
        risk_reward_ratio=None,
        risk_flags=_build_risk_flags(result),
        setup_state=actionability_state,
        technical_summary=summary,
    )


def _build_fundamental_analysis(
    result: AnalysisModuleResult | None,
    contribution: float | None,
) -> FundamentalAnalysis:
    summary = _build_summary(
        result,
        fallback="Fundamental analysis is operating in placeholder mode until financial-data providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    return FundamentalAnalysis(
        fundamental_bias=_map_fundamental_bias(result.direction if result else None),
        composite_score=round(contribution or 0.0, 4),
        growth=summary,
        valuation_view=summary,
        business_quality=summary,
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
    direction = _map_direction(result.direction if result else None)
    return SentimentExpectations(
        sentiment_bias=direction,
        news_tone=_map_news_tone(direction),
        market_expectation=summary,
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
    direction = _map_direction(result.direction if result else None)
    event_flags = [EventRiskFlag(flag) for flag in blocking_flags if flag in EventRiskFlag._value2member_map_]
    return EventDrivenAnalysis(
        event_bias=direction,
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
    if result.low_confidence:
        flags.append("low_confidence")
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


def _map_direction(direction: AnalysisDirection | None) -> Direction:
    if direction == AnalysisDirection.BULLISH:
        return Direction.BULLISH
    if direction in {AnalysisDirection.BEARISH, AnalysisDirection.DISQUALIFIED}:
        return Direction.BEARISH
    return Direction.NEUTRAL


def _map_fundamental_bias(direction: AnalysisDirection | None) -> FundamentalBias:
    if direction is None:
        return FundamentalBias.NEUTRAL
    return FundamentalBias(direction.value)


def _map_news_tone(direction: Direction) -> NewsTone:
    if direction == Direction.BULLISH:
        return NewsTone.POSITIVE
    if direction == Direction.BEARISH:
        return NewsTone.NEGATIVE
    return NewsTone.NEUTRAL
