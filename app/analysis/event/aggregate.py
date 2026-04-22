from __future__ import annotations

from app.analysis.event.schemas import (
    CompanyCatalystsResult,
    EventAggregateResult,
    EventSignal,
    MacroSensitivityResult,
    ScheduledEventsResult,
)
from app.schemas.modules import AnalysisDirection


def aggregate_event_signals(
    *,
    scheduled_events: ScheduledEventsResult,
    macro_sensitivity: MacroSensitivityResult,
    company_catalysts: CompanyCatalystsResult,
) -> EventAggregateResult:
    risk_events = _dedupe(
        scheduled_events.risk_events
        + macro_sensitivity.risk_events
        + company_catalysts.risk_events
    )
    event_risk_flags = _dedupe(
        scheduled_events.event_risk_flags
        + macro_sensitivity.event_risk_flags
        + company_catalysts.event_risk_flags
    )
    upcoming_catalysts = _dedupe(
        scheduled_events.upcoming_catalysts + company_catalysts.upcoming_catalysts
    )

    positive_score = (
        scheduled_events.confirmed_positive_catalysts
        + company_catalysts.confirmed_positive_catalysts
    )
    negative_score = (
        scheduled_events.confirmed_negative_events
        + company_catalysts.confirmed_negative_events
    )

    event_bias = _resolve_event_bias(
        positive_score=positive_score,
        negative_score=negative_score,
        event_risk_flags=event_risk_flags,
    )
    low_confidence_modules = _low_confidence_modules(
        scheduled_events=scheduled_events,
        macro_sensitivity=macro_sensitivity,
        company_catalysts=company_catalysts,
    )
    summary = _build_summary(
        scheduled_events=scheduled_events,
        macro_sensitivity=macro_sensitivity,
        event_bias=event_bias,
        positive_score=positive_score,
        negative_score=negative_score,
    )
    legacy_signal = EventSignal(
        direction=_resolve_legacy_direction(
            scheduled_events=scheduled_events,
            macro_sensitivity=macro_sensitivity,
            positive_score=positive_score,
        ),
        summary=_build_legacy_summary(
            scheduled_events=scheduled_events,
            macro_sensitivity=macro_sensitivity,
            positive_score=positive_score,
        ),
        data_completeness_pct=100.0,
        low_confidence=False,
    )

    return EventAggregateResult(
        event_bias=event_bias,
        upcoming_catalysts=upcoming_catalysts,
        risk_events=risk_events,
        event_risk_flags=event_risk_flags,
        data_completeness_pct=100.0,
        low_confidence=bool(low_confidence_modules),
        low_confidence_modules=low_confidence_modules,
        weight_scheme_used="event_risk_aggregation_v1",
        subresults={
            "legacy_signal": legacy_signal,
            "scheduled_events": scheduled_events,
            "macro_sensitivity": macro_sensitivity,
            "company_catalysts": company_catalysts,
        },
        summary=summary,
    )


def _resolve_event_bias(
    *,
    positive_score: int,
    negative_score: int,
    event_risk_flags: list[str],
) -> AnalysisDirection:
    if negative_score > positive_score:
        return AnalysisDirection.BEARISH
    if positive_score > negative_score and "binary_event_imminent" not in event_risk_flags:
        return AnalysisDirection.BULLISH
    return AnalysisDirection.NEUTRAL


def _low_confidence_modules(
    *,
    scheduled_events: ScheduledEventsResult,
    macro_sensitivity: MacroSensitivityResult,
    company_catalysts: CompanyCatalystsResult,
) -> list[str]:
    modules: list[str] = []
    if scheduled_events.low_confidence:
        modules.append("scheduled_events")
    if macro_sensitivity.low_confidence:
        modules.append("macro_sensitivity")
    if company_catalysts.low_confidence:
        modules.append("company_catalysts")
    return modules


def _build_summary(
    *,
    scheduled_events: ScheduledEventsResult,
    macro_sensitivity: MacroSensitivityResult,
    event_bias: AnalysisDirection,
    positive_score: int,
    negative_score: int,
) -> str:
    risk_score = len(scheduled_events.risk_events) + len(macro_sensitivity.risk_events)
    bias_label = event_bias.value
    return (
        f"Event analysis found {len(scheduled_events.records)} company events and "
        f"{len(macro_sensitivity.records)} macro events within the holding window. "
        f"Near-term risks: {risk_score}; positive catalysts: {positive_score}; resulting bias: {bias_label}."
    )


def _resolve_legacy_direction(
    *,
    scheduled_events: ScheduledEventsResult,
    macro_sensitivity: MacroSensitivityResult,
    positive_score: int,
) -> AnalysisDirection:
    risk_score = len(scheduled_events.risk_events) + len(macro_sensitivity.risk_events)
    if risk_score > positive_score and risk_score > 0:
        return AnalysisDirection.BEARISH
    if positive_score > risk_score:
        return AnalysisDirection.BULLISH
    return AnalysisDirection.NEUTRAL


def _build_legacy_summary(
    *,
    scheduled_events: ScheduledEventsResult,
    macro_sensitivity: MacroSensitivityResult,
    positive_score: int,
) -> str:
    direction = _resolve_legacy_direction(
        scheduled_events=scheduled_events,
        macro_sensitivity=macro_sensitivity,
        positive_score=positive_score,
    )
    bias_label = direction.value
    risk_score = len(scheduled_events.risk_events) + len(macro_sensitivity.risk_events)
    return (
        f"Event analysis found {len(scheduled_events.records)} company events and "
        f"{len(macro_sensitivity.records)} macro events within the holding window. "
        f"Near-term risks: {risk_score}; positive catalysts: {positive_score}; resulting bias: {bias_label}."
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
