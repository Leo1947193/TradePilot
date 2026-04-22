from __future__ import annotations

from app.analysis.event.schemas import (
    EventSourceTraceEntry,
    MacroSensitivityEvent,
    MacroSensitivityResult,
)
from app.services.providers.dtos import MacroCalendarEvent


def analyze_macro_sensitivity(
    macro_events: list[MacroCalendarEvent],
    *,
    analysis_time,
    holding_horizon_days: int = 90,
) -> MacroSensitivityResult:
    records: list[MacroSensitivityEvent] = []
    risk_events: list[str] = []
    event_risk_flags: list[str] = []

    for event in macro_events:
        days_until = (event.scheduled_at - analysis_time).total_seconds() / 86400
        if days_until < 0 or days_until > holding_horizon_days:
            continue

        high_sensitivity = 0 <= days_until <= 7 and (event.importance or "").lower() == "high"
        if high_sensitivity:
            risk_events.append(event.event_name)
            event_risk_flags.append("macro_event_high_sensitivity")

        records.append(
            MacroSensitivityEvent(
                event_name=event.event_name,
                category=event.category,
                scheduled_at=event.scheduled_at,
                importance=event.importance,
                days_until=days_until,
                high_sensitivity=high_sensitivity,
                source_trace=(
                    EventSourceTraceEntry(
                        dataset="macro_events",
                        source=event.source.name,
                        source_url=event.source.url,
                        fetched_at=event.source.fetched_at,
                    ),
                ),
            )
        )

    return MacroSensitivityResult(
        risk_events=_dedupe(risk_events),
        event_risk_flags=_dedupe(event_risk_flags),
        macro_event_exposure="high" if event_risk_flags else "normal",
        data_completeness_pct=100.0,
        low_confidence=len(records) == 0,
        records=tuple(records),
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
