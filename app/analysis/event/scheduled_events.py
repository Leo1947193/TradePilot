from __future__ import annotations

from datetime import datetime
from math import floor
from typing import Any

from app.analysis.event.schemas import (
    EarningsWindowState,
    EventDirectionHint,
    EventSourceTraceEntry,
    EventStatus,
    ScheduledCatalyst,
    ScheduledEventRecord,
    ScheduledEventsResult,
    ScheduledRiskEvent,
)
from app.services.providers.dtos import CompanyEvent

ACTIONABLE_STATUSES = {EventStatus.SCHEDULED, EventStatus.CONFIRMED}
POSITIVE_EVENT_TYPES = (
    "approval",
    "conference",
    "investor_day",
    "launch",
    "partnership",
    "product",
)
RISK_EVENT_TYPES = (
    "earnings",
    "fda",
    "lawsuit",
    "merger_vote",
    "recall",
    "regulatory",
)


def analyze_scheduled_events(
    company_events: list[CompanyEvent | dict[str, Any] | Any],
    *,
    analysis_time: datetime,
    holding_horizon_days: int = 90,
) -> ScheduledEventsResult:
    normalized_events = normalize_scheduled_company_events(company_events, analysis_time=analysis_time)
    actionable_events = tuple(
        event
        for event in normalized_events
        if event.event_status in ACTIONABLE_STATUSES
        and event.scheduled_at >= analysis_time
        and event.days_until <= holding_horizon_days
    )

    earnings_events = tuple(event for event in actionable_events if _is_earnings_event(event.event_type))
    days_to_next_earnings = int(earnings_events[0].days_until) if earnings_events else None

    scheduled_catalysts = tuple(
        ScheduledCatalyst(
            event_id=event.event_id or "",
            event_type=event.event_type,
            title=event.title,
            scheduled_at=event.scheduled_at,
            event_status=event.event_status,
            direction_hint=event.direction_hint,
            source_url=event.url,
        )
        for event in actionable_events
        if event.direction_hint == EventDirectionHint.POSITIVE
    )
    near_term_scheduled_risks = tuple(
        ScheduledRiskEvent(
            event_id=event.event_id or "",
            event_type=event.event_type,
            title=event.title,
            scheduled_at=event.scheduled_at,
            event_status=event.event_status,
            risk_label=_risk_label(event),
            source_url=event.url,
        )
        for event in actionable_events
        if _is_near_term_risk(event)
    )

    warnings: list[str] = []
    if any(
        event.event_status not in ACTIONABLE_STATUSES and event.scheduled_at >= analysis_time
        for event in normalized_events
    ):
        warnings.append("Ignored non-actionable scheduled events due to event_status.")

    source_trace = _dedupe_source_trace(normalized_events)
    return ScheduledEventsResult(
        upcoming_catalysts=[item.title for item in scheduled_catalysts],
        risk_events=[item.title for item in near_term_scheduled_risks],
        event_risk_flags=_build_event_risk_flags(near_term_scheduled_risks),
        confirmed_positive_catalysts=len(scheduled_catalysts),
        confirmed_negative_events=sum(
            1 for event in actionable_events if event.direction_hint == EventDirectionHint.NEGATIVE
        ),
        days_to_next_earnings=days_to_next_earnings,
        earnings_window_state=_earnings_window_state(days_to_next_earnings),
        scheduled_catalysts=scheduled_catalysts,
        near_term_scheduled_risks=near_term_scheduled_risks,
        data_completeness_pct=100.0,
        low_confidence=len(normalized_events) == 0,
        records=normalized_events,
        normalized_events=normalized_events,
        source_trace=source_trace,
        warnings=tuple(warnings),
    )


def normalize_scheduled_company_events(
    company_events: list[CompanyEvent | dict[str, Any] | Any],
    *,
    analysis_time: datetime,
) -> tuple[ScheduledEventRecord, ...]:
    normalized = [
        _normalize_single_company_event(event, analysis_time=analysis_time)
        for event in company_events
    ]
    normalized.sort(key=lambda event: (event.scheduled_at, event.event_type, event.event_id or ""))
    return tuple(normalized)


def _normalize_single_company_event(
    event: CompanyEvent | dict[str, Any] | Any,
    *,
    analysis_time: datetime,
) -> ScheduledEventRecord:
    symbol = str(_read_value(event, "symbol"))
    event_type = str(_read_value(event, "event_type"))
    title = str(_read_value(event, "title"))
    scheduled_at = _read_value(event, "scheduled_at")
    category = _read_optional_value(event, "category")
    url = _read_optional_value(event, "url")
    source = _read_value(event, "source")
    event_status = _derive_event_status(event, scheduled_at=scheduled_at, analysis_time=analysis_time)

    trace = EventSourceTraceEntry(
        dataset="company_events",
        source=source.name,
        source_url=source.url,
        fetched_at=source.fetched_at,
        staleness_days=max(0, floor((analysis_time - source.fetched_at).total_seconds() / 86400)),
        missing_fields=tuple(
            field_name
            for field_name, value in (
                ("event_status", _read_optional_value(event, "event_status")),
                ("category", category),
                ("url", url),
            )
            if value in (None, "")
        ),
    )

    return ScheduledEventRecord(
        event_id=_event_id(symbol=symbol, event_type=event_type, title=title, scheduled_at=scheduled_at),
        symbol=symbol,
        event_type=event_type,
        title=title,
        scheduled_at=scheduled_at,
        category=category,
        url=url,
        event_status=event_status,
        event_state=_read_optional_value(event, "event_state"),
        direction_hint=_derive_direction_hint(event_type),
        earnings_session=_derive_earnings_session(title) if _is_earnings_event(event_type) else None,
        days_until=_days_until(scheduled_at, analysis_time),
        source_trace=(trace,),
    )


def _derive_event_status(
    event: CompanyEvent | dict[str, Any] | Any,
    *,
    scheduled_at: datetime,
    analysis_time: datetime,
) -> EventStatus:
    raw_status = _read_optional_value(event, "event_status")
    if raw_status is not None:
        return EventStatus(str(raw_status).lower())
    if scheduled_at < analysis_time:
        return EventStatus.COMPLETED
    return EventStatus.SCHEDULED


def _derive_direction_hint(event_type: str) -> EventDirectionHint:
    normalized_type = event_type.lower()
    if _contains_any(normalized_type, POSITIVE_EVENT_TYPES):
        return EventDirectionHint.POSITIVE
    if _contains_any(normalized_type, RISK_EVENT_TYPES):
        if _is_earnings_event(normalized_type):
            return EventDirectionHint.BINARY
        return EventDirectionHint.NEGATIVE
    return EventDirectionHint.NEUTRAL


def _derive_earnings_session(title: str) -> str | None:
    lowered = title.lower()
    if "before open" in lowered or "pre-market" in lowered:
        return "pre_market"
    if "after close" in lowered or "after market close" in lowered:
        return "post_market"
    return None


def _earnings_window_state(days_to_next_earnings: int | None) -> EarningsWindowState:
    if days_to_next_earnings is None:
        return EarningsWindowState.NONE
    if days_to_next_earnings <= 3:
        return EarningsWindowState.WITHIN_3D
    if days_to_next_earnings <= 14:
        return EarningsWindowState.WITHIN_14D
    return EarningsWindowState.WITHIN_90D


def _is_near_term_risk(event: ScheduledEventRecord) -> bool:
    if event.days_until < 0 or event.days_until > 14:
        return False
    return event.direction_hint in {EventDirectionHint.BINARY, EventDirectionHint.NEGATIVE}


def _risk_label(event: ScheduledEventRecord) -> str:
    if _is_earnings_event(event.event_type):
        return "earnings_within_3d" if event.days_until <= 3 else "binary_event_imminent"
    if "regulatory" in event.event_type.lower() or "fda" in event.event_type.lower():
        return "regulatory_decision_imminent"
    return "binary_event_imminent"


def _event_id(*, symbol: str, event_type: str, title: str, scheduled_at: datetime) -> str:
    return f"{symbol.lower()}::{event_type.lower()}::{scheduled_at.isoformat()}::{_stable_label(title)}"


def _days_until(scheduled_at: datetime, analysis_time: datetime) -> float:
    return float(floor((scheduled_at - analysis_time).total_seconds() / 86400))


def _stable_label(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value.lower()).strip("-")


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def _is_earnings_event(event_type: str) -> bool:
    return "earnings" in event_type.lower()


def _read_value(event: CompanyEvent | dict[str, Any] | Any, field_name: str) -> Any:
    value = _read_optional_value(event, field_name)
    if value is None:
        raise ValueError(f"scheduled company event missing required field: {field_name}")
    return value


def _read_optional_value(event: CompanyEvent | dict[str, Any] | Any, field_name: str) -> Any:
    if isinstance(event, dict):
        return event.get(field_name)
    return getattr(event, field_name, None)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _build_event_risk_flags(near_term_scheduled_risks: tuple[ScheduledRiskEvent, ...]) -> list[str]:
    flags: list[str] = []
    for event in near_term_scheduled_risks:
        flags.append(event.risk_label)
        if event.risk_label == "earnings_within_3d":
            flags.append("binary_event_imminent")
    return _dedupe(flags)


def _dedupe_source_trace(
    normalized_events: tuple[ScheduledEventRecord, ...],
) -> tuple[EventSourceTraceEntry, ...]:
    deduped: list[EventSourceTraceEntry] = []
    for event in normalized_events:
        for trace in event.source_trace:
            if trace not in deduped:
                deduped.append(trace)
    return tuple(deduped)
