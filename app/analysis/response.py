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
        state.module_reports.technical,
        state.decision_synthesis.actionability_state,
    )
    fundamental = _build_fundamental_analysis(
        state.module_results.fundamental,
        state.module_reports.fundamental,
        module_contributions[ModuleName.FUNDAMENTAL].contribution,
    )
    sentiment = _build_sentiment_expectations(
        state.module_results.sentiment,
        state.module_reports.sentiment,
    )
    event = _build_event_driven_analysis(
        state.module_results.event,
        state.module_reports.event,
        state.decision_synthesis.blocking_flags,
    )
    return technical, fundamental, sentiment, event


def _build_technical_analysis(
    result: AnalysisModuleResult | None,
    report: dict | None,
    actionability_state: TechnicalSetupState,
) -> TechnicalAnalysis:
    summary = _build_summary(
        result,
        fallback="Technical analysis is operating in placeholder mode until market-data providers are integrated.",
    )
    direction = _map_direction(result.direction if result else None)
    return TechnicalAnalysis(
        technical_signal=direction,
        trend=_map_direction(_report_direction(report, "trend") or (result.direction if result else None)),
        key_support=_report_float_list(report, "key_support"),
        key_resistance=_report_float_list(report, "key_resistance"),
        volume_pattern=_report_volume_pattern(report) or VolumePattern.NEUTRAL,
        momentum=_report_str(report, "summary") or summary,
        entry_trigger=_report_str(report, "entry_trigger"),
        target_price=_report_float(report, "target_price"),
        stop_loss_price=_report_float(report, "stop_loss_price"),
        risk_reward_ratio=_report_float(report, "risk_reward_ratio"),
        risk_flags=_report_list(report, "risk_flags") or _build_risk_flags(result),
        setup_state=actionability_state,
        technical_summary=summary,
    )


def _build_fundamental_analysis(
    result: AnalysisModuleResult | None,
    report: dict | None,
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
        growth=_fundamental_snapshot_metric(report, 0) or summary,
        valuation_view=_fundamental_snapshot_metric(report, 1) or summary,
        business_quality=_report_str(report, "summary") or summary,
        key_risks=_report_list(report, "key_risks") or _build_risk_flags(result),
        data_completeness_pct=completeness,
        fundamental_summary=summary,
    )


def _build_sentiment_expectations(
    result: AnalysisModuleResult | None,
    report: dict | None,
) -> SentimentExpectations:
    summary = _build_summary(
        result,
        fallback="Sentiment analysis is operating in placeholder mode until news providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    direction = _map_direction(result.direction if result else None)
    report_key_risks = _report_list(report, "key_risks")
    market_expectation = _report_str(report, "market_expectation") or summary
    news_tone = _report_str(report, "news_tone")
    return SentimentExpectations(
        sentiment_bias=direction,
        news_tone=NewsTone(news_tone) if news_tone in NewsTone._value2member_map_ else _map_news_tone(direction),
        market_expectation=market_expectation,
        key_risks=report_key_risks or _build_risk_flags(result),
        data_completeness_pct=completeness,
        sentiment_summary=summary,
    )


def _build_event_driven_analysis(
    result: AnalysisModuleResult | None,
    report: dict | None,
    blocking_flags: list[str],
) -> EventDrivenAnalysis:
    summary = _build_summary(
        result,
        fallback="Event analysis is operating in placeholder mode until company-event and macro providers are integrated.",
    )
    completeness = _resolve_completeness(result)
    direction = _map_direction(result.direction if result else None)
    report_flags = _report_list(report, "event_risk_flags")
    event_flags = [
        EventRiskFlag(flag)
        for flag in (report_flags or blocking_flags)
        if flag in EventRiskFlag._value2member_map_
    ]
    return EventDrivenAnalysis(
        event_bias=direction,
        upcoming_catalysts=_report_list(report, "upcoming_catalysts"),
        risk_events=_report_list(report, "risk_events") or _build_risk_flags(result),
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


def _report_list(report: dict | None, key: str) -> list[str]:
    if not isinstance(report, dict):
        return []
    value = report.get(key)
    return [str(item) for item in value] if isinstance(value, list) else []


def _report_str(report: dict | None, key: str) -> str | None:
    if not isinstance(report, dict):
        return None
    value = report.get(key)
    return str(value) if isinstance(value, str) else None


def _report_float(report: dict | None, key: str) -> float | None:
    if not isinstance(report, dict):
        return None
    value = report.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _report_float_list(report: dict | None, key: str) -> list[float]:
    if not isinstance(report, dict):
        return []
    value = report.get(key)
    return [float(item) for item in value] if isinstance(value, list) else []


def _report_direction(report: dict | None, key: str) -> AnalysisDirection | None:
    value = _report_str(report, key)
    if value in AnalysisDirection._value2member_map_:
        return AnalysisDirection(value)
    return None


def _report_volume_pattern(report: dict | None) -> VolumePattern | None:
    value = _report_str(report, "volume_pattern")
    if value in VolumePattern._value2member_map_:
        return VolumePattern(value)
    return None


def _fundamental_snapshot_metric(report: dict | None, index: int) -> str | None:
    if not isinstance(report, dict):
        return None
    subresults = report.get("subresults")
    if not isinstance(subresults, dict):
        return None
    snapshot = subresults.get("financial_snapshot")
    if not isinstance(snapshot, dict):
        return None
    metrics = snapshot.get("key_metrics")
    if not isinstance(metrics, list) or len(metrics) <= index:
        return None
    value = metrics[index]
    return str(value) if isinstance(value, str) else None
