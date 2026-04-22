from __future__ import annotations

from app.analysis.event.schemas import (
    CompanyCatalystRecord,
    CompanyCatalystsResult,
    EventSourceTraceEntry,
)
from app.services.providers.dtos import CompanyEvent

POSITIVE_EVENT_TYPES = ("approval", "launch", "partnership", "merger", "acquisition")
NEGATIVE_EVENT_TYPES = ("lawsuit", "recall", "regulatory", "fda")
BINARY_EVENT_TYPES = ("earnings", "vote", "decision")


def analyze_company_catalysts(
    company_events: list[CompanyEvent],
    *,
    analysis_time,
    holding_horizon_days: int = 90,
) -> CompanyCatalystsResult:
    upcoming_catalysts: list[str] = []
    risk_events: list[str] = []
    event_risk_flags: list[str] = []
    records: list[CompanyCatalystRecord] = []
    confirmed_positive_catalysts = 0
    confirmed_negative_events = 0
    binary_event_count = 0

    for event in company_events:
        days_until = (event.scheduled_at - analysis_time).total_seconds() / 86400
        if days_until < 0 or days_until > holding_horizon_days:
            continue

        event_type = event.event_type.lower()
        direction_hint = "unknown"
        event_state = "scheduled"

        if any(term in event_type for term in POSITIVE_EVENT_TYPES):
            direction_hint = "positive"
            upcoming_catalysts.append(event.title)
            confirmed_positive_catalysts += 1
        elif any(term in event_type for term in NEGATIVE_EVENT_TYPES):
            direction_hint = "negative"
            risk_events.append(event.title)
            confirmed_negative_events += 1
            if 0 <= days_until <= 7 and any(term in event_type for term in ("regulatory", "fda")):
                event_risk_flags.append("regulatory_decision_imminent")
        elif any(term in event_type for term in BINARY_EVENT_TYPES):
            direction_hint = "binary"
            binary_event_count += 1
            if 0 <= days_until <= 7:
                event_risk_flags.append("binary_event_imminent")

        records.append(
            CompanyCatalystRecord(
                event_type=event.event_type,
                title=event.title,
                scheduled_at=event.scheduled_at,
                category=event.category,
                event_state=event_state,
                direction_hint=direction_hint,
                days_until=days_until,
                source_trace=(
                    EventSourceTraceEntry(
                        dataset="company_catalyst_events",
                        source=event.source.name,
                        source_url=event.source.url,
                        fetched_at=event.source.fetched_at,
                    ),
                ),
            )
        )

    return CompanyCatalystsResult(
        upcoming_catalysts=_dedupe(upcoming_catalysts),
        risk_events=_dedupe(risk_events),
        event_risk_flags=_dedupe(event_risk_flags),
        confirmed_positive_catalysts=confirmed_positive_catalysts,
        confirmed_negative_events=confirmed_negative_events,
        binary_event_count=binary_event_count,
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
