from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, TypeVar

from app.analysis.event import analyze_event_inputs
from app.schemas.api import Source, SourceType
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import (
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.interfaces import CompanyEventsProvider, MacroCalendarProvider


EVENT_DEGRADED_SUMMARY = (
    "Event analysis is degraded because provider-backed company event and macro data is not available yet."
)
EVENT_DEGRADED_REASON = "event module placeholder until provider integration is implemented"
EVENT_DEGRADED_WARNING = (
    "Event analysis degraded: provider-backed company event and macro data is not available yet."
)

AwaitableT = TypeVar("AwaitableT")


def run_event(
    state: TradePilotState | dict,
    *,
    company_events_provider: CompanyEventsProvider | None = None,
    macro_calendar_provider: MacroCalendarProvider | None = None,
) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if company_events_provider is not None and macro_calendar_provider is not None:
        return _run_provider_backed_event_analysis(
            validated_state,
            company_events_provider=company_events_provider,
            macro_calendar_provider=macro_calendar_provider,
        )

    event_result = AnalysisModuleResult(
        module=AnalysisModuleName.EVENT,
        status=ModuleExecutionStatus.DEGRADED,
        summary=EVENT_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=EVENT_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.EVENT.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.EVENT.value)

    warnings = list(validated_state.diagnostics.warnings)
    if EVENT_DEGRADED_WARNING not in warnings:
        warnings.append(EVENT_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"event": event_result}
    )
    updated_diagnostics = validated_state.diagnostics.model_copy(
        update={
            "degraded_modules": degraded_modules,
            "warnings": warnings,
        }
    )

    return validated_state.model_copy(
        update={
            "module_results": updated_module_results,
            "diagnostics": updated_diagnostics,
        }
    )


def _run_provider_backed_event_analysis(
    validated_state: TradePilotState,
    *,
    company_events_provider: CompanyEventsProvider,
    macro_calendar_provider: MacroCalendarProvider,
) -> TradePilotState:
    normalized_ticker = validated_state.normalized_ticker
    market = validated_state.context.market
    window = validated_state.context.analysis_window_days
    if not normalized_ticker:
        raise ValueError("normalized_ticker is required for event analysis")
    if not market:
        raise ValueError("context.market is required for event analysis")
    if window is None:
        raise ValueError("context.analysis_window_days is required for event analysis")

    days_ahead = window[1]
    try:
        company_events, macro_events = _run_awaitable(
            _fetch_event_inputs(
                normalized_ticker,
                market,
                days_ahead,
                company_events_provider,
                macro_calendar_provider,
            )
        )
    except Exception:
        return run_event(validated_state)

    event_signal = analyze_event_inputs(
        company_events,
        macro_events,
        analysis_time=validated_state.context.analysis_time,
    )
    event_result = AnalysisModuleResult(
        module=AnalysisModuleName.EVENT,
        status=ModuleExecutionStatus.USABLE,
        summary=event_signal.summary,
        direction=event_signal.direction,
        data_completeness_pct=event_signal.data_completeness_pct,
        low_confidence=event_signal.low_confidence,
        reason=None,
    )

    return validated_state.model_copy(
        update={
            "module_results": validated_state.module_results.model_copy(update={"event": event_result}),
            "sources": _merge_sources(
                validated_state.sources,
                [_to_source(event.source, SourceType.EVENT) for event in company_events]
                + [_to_source(event.source, SourceType.MACRO) for event in macro_events],
            ),
        }
    )


async def _fetch_event_inputs(
    normalized_ticker: str,
    market: str,
    days_ahead: int,
    company_events_provider: CompanyEventsProvider,
    macro_calendar_provider: MacroCalendarProvider,
):
    return await asyncio.gather(
        company_events_provider.get_company_events(normalized_ticker, days_ahead=days_ahead),
        macro_calendar_provider.get_macro_events(market=market, days_ahead=days_ahead),
    )


def _run_awaitable(awaitable: Awaitable[AwaitableT]) -> AwaitableT:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, awaitable).result()


def _merge_sources(existing: list[Source], additions: list[Source]) -> list[Source]:
    merged = list(existing)
    seen = {(source.type, source.name, str(source.url)) for source in merged}
    for source in additions:
        key = (source.type, source.name, str(source.url))
        if key in seen:
            continue
        seen.add(key)
        merged.append(source)
    return merged


def _to_source(source_ref, source_type: SourceType) -> Source:
    if source_ref.url is None:
        raise ValueError("provider source url is required for public sources")
    return Source(type=source_type, name=source_ref.name, url=source_ref.url)
