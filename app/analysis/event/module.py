from __future__ import annotations

from datetime import datetime

from app.analysis.event.aggregate import aggregate_event_signals
from app.analysis.event.company_catalysts import analyze_company_catalysts
from app.analysis.event.macro_sensitivity import analyze_macro_sensitivity
from app.analysis.event.scheduled_events import analyze_scheduled_events
from app.analysis.event.schemas import EventAggregateResult, EventSignal
from app.schemas.modules import AnalysisModuleName, AnalysisModuleResult, ModuleExecutionStatus
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent


def analyze_event_module(
    company_events: list[CompanyEvent],
    macro_events: list[MacroCalendarEvent],
    *,
    analysis_time: datetime,
) -> AnalysisModuleResult:
    aggregate_result = analyze_event_aggregate(
        company_events,
        macro_events,
        analysis_time=analysis_time,
    )
    legacy_signal = aggregate_result.subresults.get("legacy_signal")
    return AnalysisModuleResult(
        module=AnalysisModuleName.EVENT,
        status=ModuleExecutionStatus.USABLE,
        summary=_resolve_module_summary(aggregate_result, legacy_signal),
        direction=_resolve_module_direction(aggregate_result, legacy_signal),
        data_completeness_pct=aggregate_result.data_completeness_pct,
        low_confidence=_resolve_module_low_confidence(aggregate_result, legacy_signal),
        reason=None,
    )


def analyze_event_aggregate(
    company_events: list[CompanyEvent],
    macro_events: list[MacroCalendarEvent],
    *,
    analysis_time: datetime,
) -> EventAggregateResult:
    scheduled_events = analyze_scheduled_events(company_events, analysis_time=analysis_time)
    macro_sensitivity = analyze_macro_sensitivity(macro_events, analysis_time=analysis_time)
    company_catalysts = analyze_company_catalysts(company_events, analysis_time=analysis_time)
    return aggregate_event_signals(
        scheduled_events=scheduled_events,
        macro_sensitivity=macro_sensitivity,
        company_catalysts=company_catalysts,
    )


def analyze_event_inputs(
    company_events: list[CompanyEvent],
    macro_events: list[MacroCalendarEvent],
    *,
    analysis_time: datetime,
) -> EventSignal:
    aggregate_result = analyze_event_aggregate(
        company_events,
        macro_events,
        analysis_time=analysis_time,
    )
    legacy_signal = aggregate_result.subresults.get("legacy_signal")
    return EventSignal(
        direction=_resolve_module_direction(aggregate_result, legacy_signal),
        summary=_resolve_module_summary(aggregate_result, legacy_signal),
        data_completeness_pct=aggregate_result.data_completeness_pct,
        low_confidence=_resolve_module_low_confidence(aggregate_result, legacy_signal),
    )


def _resolve_module_summary(aggregate_result: EventAggregateResult, legacy_signal) -> str:
    summary = getattr(legacy_signal, "summary", None)
    if isinstance(summary, str) and summary:
        return summary
    return aggregate_result.summary


def _resolve_module_direction(aggregate_result: EventAggregateResult, legacy_signal):
    direction = getattr(legacy_signal, "direction", None)
    if direction is not None:
        return direction
    return aggregate_result.event_bias


def _resolve_module_low_confidence(aggregate_result: EventAggregateResult, legacy_signal) -> bool:
    low_confidence = getattr(legacy_signal, "low_confidence", None)
    if isinstance(low_confidence, bool):
        return low_confidence
    return aggregate_result.low_confidence
