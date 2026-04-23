from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.analysis.event.schemas import (
    CompanyCatalystRecord,
    CompanyCatalystsResult,
    EventDirectionHint,
    EventSourceTraceEntry,
    EventStatus,
)
from app.services.providers.dtos import CompanyEvent

_POSITIVE_EVENT_TYPES = ("launch", "partnership", "investor_day", "capital_markets_day")
_NEGATIVE_EVENT_TYPES = ("lawsuit", "recall", "investigation", "penalty")
_REGULATORY_EVENT_TYPES = ("regulatory", "fda", "approval", "court")
_BINARY_EVENT_TYPES = ("vote", "decision", "merger", "acquisition", "earnings")


def analyze_company_catalysts(
    company_events_or_payload: list[CompanyEvent] | Mapping[str, Any],
    *,
    analysis_time: datetime | None = None,
    holding_horizon_days: int = 90,
) -> CompanyCatalystsResult:
    payload = _coerce_payload(
        company_events_or_payload,
        analysis_time=analysis_time,
        holding_horizon_days=holding_horizon_days,
    )

    resolved_analysis_time = payload["analysis_time"]
    resolved_horizon = payload["holding_horizon_days"]
    upcoming_catalysts: list[str] = []
    risk_events: list[str] = []
    event_risk_flags: list[str] = []
    records: list[CompanyCatalystRecord] = []
    confirmed_positive_catalysts = 0
    confirmed_negative_events = 0
    binary_event_count = 0

    for raw_event in payload["company_catalyst_events"]:
        title = str(raw_event.get("title") or raw_event.get("event_id") or "").strip()
        event_type = str(raw_event.get("event_type") or "").strip().lower()
        scheduled_at = raw_event.get("expected_date")
        if not title or not event_type or not isinstance(scheduled_at, datetime):
            continue

        days_until = (scheduled_at - resolved_analysis_time).total_seconds() / 86400
        if days_until < 0 or days_until > resolved_horizon:
            continue

        event_state = _normalize_event_state(raw_event, event_type=event_type, title=title)
        direction_hint = _normalize_direction_hint(raw_event, event_type=event_type, title=title)

        if direction_hint == EventDirectionHint.POSITIVE and event_state == EventStatus.CONFIRMED:
            upcoming_catalysts.append(title)
            confirmed_positive_catalysts += 1
        elif direction_hint == EventDirectionHint.NEGATIVE and event_state == EventStatus.CONFIRMED:
            risk_events.append(title)
            confirmed_negative_events += 1
        elif direction_hint == EventDirectionHint.BINARY:
            binary_event_count += 1

        risk_flag = _resolve_risk_flag(
            event_type=event_type,
            event_state=event_state,
            direction_hint=direction_hint,
            days_until=days_until,
        )
        if risk_flag is not None:
            event_risk_flags.append(risk_flag)
            risk_events.append(title)

        records.append(
            CompanyCatalystRecord(
                event_type=event_type,
                title=title,
                scheduled_at=scheduled_at,
                category=raw_event.get("category"),
                event_state=event_state.value,
                direction_hint=direction_hint.value,
                days_until=days_until,
                source_trace=(
                    _build_source_trace(raw_event, analysis_time=resolved_analysis_time),
                ),
            )
        )

    records.sort(key=lambda item: (item.days_until, item.title))

    return CompanyCatalystsResult(
        upcoming_catalysts=_dedupe(upcoming_catalysts),
        risk_events=_dedupe(risk_events),
        event_risk_flags=_dedupe(event_risk_flags),
        confirmed_positive_catalysts=confirmed_positive_catalysts,
        confirmed_negative_events=confirmed_negative_events,
        binary_event_count=binary_event_count,
        data_completeness_pct=100.0 if records else 0.0,
        low_confidence=_resolve_low_confidence(records=records),
        records=tuple(records),
    )


def _coerce_payload(
    company_events_or_payload: list[CompanyEvent] | Mapping[str, Any],
    *,
    analysis_time: datetime | None,
    holding_horizon_days: int,
) -> dict[str, Any]:
    if isinstance(company_events_or_payload, Mapping):
        payload = dict(company_events_or_payload)
        resolved_analysis_time = payload.get("analysis_time")
        if not isinstance(resolved_analysis_time, datetime):
            raise ValueError("analysis_time is required")
        return {
            "analysis_time": resolved_analysis_time,
            "holding_horizon_days": int(payload.get("holding_horizon_days") or holding_horizon_days),
            "company_catalyst_events": [dict(record) for record in payload.get("company_catalyst_events", ())],
        }

    if analysis_time is None:
        raise ValueError("analysis_time is required when passing company event DTOs directly")

    return {
        "analysis_time": analysis_time,
        "holding_horizon_days": holding_horizon_days,
        "company_catalyst_events": [
            {
                "event_id": event.title,
                "event_type": event.event_type,
                "title": event.title,
                "expected_date": event.scheduled_at,
                "category": event.category,
                "source": {
                    "name": event.source.name,
                    "url": event.source.url,
                    "fetched_at": event.source.fetched_at,
                },
            }
            for event in company_events_or_payload
        ],
    }


def _normalize_event_state(
    raw_event: Mapping[str, Any],
    *,
    event_type: str,
    title: str,
) -> EventStatus:
    explicit = str(raw_event.get("event_state") or raw_event.get("event_status") or "").strip().lower()
    if explicit in {status.value for status in EventStatus}:
        return EventStatus(explicit)

    lowered_title = title.lower()
    if "rumor" in lowered_title or "rumor" in event_type:
        return EventStatus.RUMORED
    if _matches_any(event_type, _REGULATORY_EVENT_TYPES + _BINARY_EVENT_TYPES):
        return EventStatus.PENDING
    return EventStatus.CONFIRMED


def _normalize_direction_hint(
    raw_event: Mapping[str, Any],
    *,
    event_type: str,
    title: str,
) -> EventDirectionHint:
    explicit = str(raw_event.get("direction_hint") or "").strip().lower()
    if explicit in {hint.value for hint in EventDirectionHint}:
        return EventDirectionHint(explicit)

    lowered_title = title.lower()
    if "rumor" in lowered_title or "rumor" in event_type:
        return EventDirectionHint.UNKNOWN
    if _matches_any(event_type, _REGULATORY_EVENT_TYPES + _BINARY_EVENT_TYPES):
        return EventDirectionHint.BINARY
    if _matches_any(event_type, _POSITIVE_EVENT_TYPES):
        return EventDirectionHint.POSITIVE
    if _matches_any(event_type, _NEGATIVE_EVENT_TYPES):
        return EventDirectionHint.NEGATIVE
    return EventDirectionHint.NEUTRAL


def _resolve_risk_flag(
    *,
    event_type: str,
    event_state: EventStatus,
    direction_hint: EventDirectionHint,
    days_until: float,
) -> str | None:
    if event_state not in {EventStatus.PENDING, EventStatus.SCHEDULED} or not (0 <= days_until <= 7):
        return None
    if _matches_any(event_type, _REGULATORY_EVENT_TYPES):
        return "regulatory_decision_imminent"
    if direction_hint == EventDirectionHint.BINARY or _matches_any(event_type, _BINARY_EVENT_TYPES):
        return "binary_event_imminent"
    return None


def _build_source_trace(raw_event: Mapping[str, Any], *, analysis_time: datetime) -> EventSourceTraceEntry:
    source = raw_event.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("company catalyst source is required")

    fetched_at = source.get("fetched_at")
    if not isinstance(fetched_at, datetime):
        raise ValueError("company catalyst source fetched_at is required")

    staleness_days = max((analysis_time.date() - fetched_at.date()).days, 0)
    return EventSourceTraceEntry(
        dataset="company_catalyst_events",
        source=str(source.get("name") or "unknown"),
        source_url=source.get("url"),
        fetched_at=fetched_at,
        staleness_days=staleness_days,
    )


def _resolve_low_confidence(*, records: list[CompanyCatalystRecord]) -> bool:
    if not records:
        return True
    return all(record.event_state == EventStatus.RUMORED.value for record in records)


def _matches_any(value: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in value for candidate in candidates)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
